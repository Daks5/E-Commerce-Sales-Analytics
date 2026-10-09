"""Execute only the project's reviewed SQL analyses, with bound filters."""
from datetime import date
from decimal import Decimal
import re
import time
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import create_engine, text, URL
from .config import ROOT, Settings

Analysis = Literal['overview', 'order_cancellation_and_aov', 'monthly_trend',
    'comparable_may_june', 'category_performance', 'category_decline_contribution',
    'state_performance', 'fulfillment_operations', 'status_distribution', 'b2b_segment',
    'sku_rank_within_category', 'daily_running_value', 'promotion_association', 'data_quality']
TITLES = {
    'overview': 'Sales overview', 'order_cancellation_and_aov': 'Orders and average order value',
    'monthly_trend': 'Monthly performance', 'comparable_may_june': 'May vs June · days 1–29',
    'category_performance': 'Product category performance',
    'category_decline_contribution': 'Category contribution to May–June change',
    'state_performance': 'Shipping-region performance', 'fulfillment_operations': 'Fulfillment comparison',
    'status_distribution': 'Order status exposure', 'b2b_segment': 'Retail vs Business (B2B)',
    'sku_rank_within_category': 'Top SKUs within each category',
    'daily_running_value': 'Daily shipped value', 'promotion_association': 'Promotion association',
    'data_quality': 'Data quality',
}
FIXED_PERIOD = {'comparable_may_june', 'category_decline_contribution'}


class QuerySpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    analysis: Analysis
    category: str | None = Field(default=None, max_length=80)
    state: str | None = Field(default=None, max_length=100)
    fulfillment: Literal['Amazon', 'Merchant'] | None = None
    customer_type: Literal['Retail', 'Business (B2B)'] | None = None
    start_date: date | None = None
    end_date: date | None = None
    row_limit: int = Field(default=200, ge=1, le=200, strict=True)

    @model_validator(mode='after')
    def validate_dates(self):
        for value in (self.start_date, self.end_date):
            if value and not date(2022, 3, 31) <= value <= date(2022, 6, 29):
                raise ValueError('Dates must be within the source snapshot: 31 March–29 June 2022.')
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError('Start date must not be after end date.')
        return self


def templates():
    script = (ROOT / 'sql/02_business_analysis.sql').read_text(encoding='utf-8')
    result = {}
    for section in re.split(r'-- @question ', script)[1:]:
        name, query = section.split('\n', 1)
        query = query.strip().rstrip(';')
        if ';' in query or not re.match(r'^(SELECT|WITH)\b', query, re.I):
            raise ValueError('The analysis registry must contain single read queries.')
        result[name.strip()] = query
    if set(result) != set(TITLES):
        raise ValueError('The reviewed SQL analysis registry has changed; review the tools.')
    return result


ORDER_SUMMARY = '''order_summary AS (
 SELECT order_id, MIN(order_date) AS order_date, COUNT(*) AS order_lines,
 SUM(is_cancelled) AS cancelled_lines, MAX(is_cancelled) AS any_cancelled,
 MIN(is_cancelled) AS fully_cancelled, MAX(is_sales_eligible) AS has_valued_shipped_line,
 MIN(order_valuation_complete) AS valuation_complete,
 SUM(CASE WHEN is_sales_eligible=1 THEN amount_minor ELSE 0 END) AS shipped_value_minor
 FROM filtered GROUP BY order_id)'''

# Companion summary of the entire filtered population, independent of display
# row limits. Keep the original status rows for inspection and reconciliation.
STATUS_SUMMARY = '''SELECT COUNT(*) AS observed_lines,
 COUNT(DISTINCT order_id) AS observed_orders,
 COALESCE(SUM(is_cancelled),0) AS cancelled_lines,
 COUNT(DISTINCT CASE WHEN is_cancelled=1 THEN order_id END) AS cancelled_orders,
 COALESCE(SUM(status='Shipped - Returned to Seller'),0) AS returned_to_seller_lines,
 COALESCE(SUM(status='Shipped - Returning to Seller'),0) AS returning_to_seller_lines,
 COALESCE(SUM(is_returned),0) AS returned_or_returning_lines,
 COUNT(DISTINCT CASE WHEN status='Shipped - Returned to Seller' THEN order_id END) AS returned_to_seller_orders,
 COUNT(DISTINCT CASE WHEN status='Shipped - Returning to Seller' THEN order_id END) AS returning_to_seller_orders,
 COUNT(DISTINCT CASE WHEN is_returned=1 THEN order_id END) AS returned_or_returning_orders
 FROM v_order_lines'''


def compile_query(spec: QuerySpec, registry=None):
    registry = registry or templates()
    clauses, params = ['1=1'], {'row_limit': spec.row_limit}
    fields = {'category': 'category', 'state': 'ship_state', 'fulfillment': 'fulfillment'}
    for attribute, column in fields.items():
        value = getattr(spec, attribute)
        if value is not None:
            clauses.append(f'{column} = :{attribute}')
            params[attribute] = value
    if spec.customer_type is not None:
        clauses.append('is_b2b = :is_b2b')
        params['is_b2b'] = int(spec.customer_type == 'Business (B2B)')
    if spec.analysis not in FIXED_PERIOD:
        for attribute, operator in [('start_date', '>='), ('end_date', '<=')]:
            value = getattr(spec, attribute)
            if value:
                clauses.append(f'order_date {operator} :{attribute}')
                params[attribute] = value
    query = registry[spec.analysis].replace('v_order_lines', 'filtered').replace('v_order_summary', 'order_summary')
    prefix = 'WITH filtered AS (SELECT * FROM v_order_lines WHERE ' + ' AND '.join(clauses) + ')'
    if 'order_summary' in query:
        prefix += ', ' + ORDER_SUMMARY
    if query.upper().startswith('WITH '):
        sql = prefix + ', ' + query[5:]
    else:
        sql = prefix + '\n' + query
    return sql + '\nLIMIT :row_limit', params


def json_value(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


class QueryService:
    def __init__(self, settings: Settings):
        if not settings.user or not settings.password:
            raise ValueError('Configure the project MySQL credentials in the secret manager or .env.')
        self.engine = create_engine(URL.create('mysql+pymysql', username=settings.user,
            password=settings.password, host=settings.host, port=settings.port, database=settings.database),
            hide_parameters=True, pool_pre_ping=True, pool_size=2, max_overflow=0,
            connect_args=settings.mysql_connect_args())
        self.registry = templates()
        with self.engine.connect() as connection:
            self.read_only = bool(connection.execute(text('SELECT @@transaction_read_only')).scalar())
            if not self.read_only:
                raise RuntimeError('Read-only transaction protection is not active.')
            self.catalog = {
                'categories': list(connection.execute(text('SELECT DISTINCT category FROM v_order_lines ORDER BY category')).scalars()),
                'states': list(connection.execute(text('SELECT DISTINCT ship_state FROM v_order_lines ORDER BY ship_state')).scalars()),
            }

    def execute(self, spec: QuerySpec):
        spec = spec.model_copy()
        for attribute, catalog_key in [('category', 'categories'), ('state', 'states')]:
            value = getattr(spec, attribute)
            if value is not None:
                lookup = {v.casefold(): v for v in self.catalog[catalog_key] if v is not None}
                canonical = lookup.get(value.strip().casefold())
                if canonical is None:
                    raise ValueError(f'Unknown {attribute}; choose one of the available values.')
                setattr(spec, attribute, canonical)
        sql, params = compile_query(spec, self.registry)
        started = time.perf_counter()
        with self.engine.connect() as connection:
            connection.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
            rows = [{k: json_value(v) for k, v in row.items()}
                    for row in connection.execute(text(sql), params).mappings()]
            status_summary = None
            if spec.analysis == 'status_distribution':
                summary_sql, summary_params = compile_query(spec, {spec.analysis: STATUS_SUMMARY})
                status_summary = {k:json_value(v) for k,v in connection.execute(text(summary_sql), summary_params).mappings().one().items()}
        notes = ['Source: Amazon sales snapshot, 31 March–29 June 2022. Amounts in INR.',
                 'Six exact duplicate copies excluded. Missing amounts remain missing.']
        if spec.analysis in FIXED_PERIOD:
            notes.append('Fixed comparison: May 1–29 vs June 1–29. Date filters are ignored; other filters apply.')
        if spec.analysis in {'monthly_trend', 'daily_running_value'}:
            notes.append('March and June have partial calendar coverage. Observed coverage does not prove complete capture.')
        if spec.analysis in {'promotion_association', 'fulfillment_operations', 'category_decline_contribution'}:
            notes.append('Descriptive association or contribution; the dataset does not establish causality.')
        if spec.analysis == 'status_distribution':
            notes.append('Recorded value includes every status and is not shipped sales or cancellation loss.')
            notes.append('Line counts are exported order-item rows, not unique products or units. Distinct order counts are provided separately in the status summary.')
            notes.append('Returned to Seller and Returning to Seller are separate statuses. Returned/returning statuses do not establish that a refund was paid.')
            notes.append('No cancellation-reason or return-reason fields are available. Status outcomes cannot explain why the cancellation or return happened.')
        if spec.analysis == 'order_cancellation_and_aov':
            notes.append('Complete-order AOV uses eligible orders with complete valuation; order rates differ from line rates.')
            if any(getattr(spec, field) is not None for field in ('category', 'state', 'fulfillment', 'customer_type', 'start_date', 'end_date')):
                notes.append('Filtered orders are selected from matching lines. Value covers those lines; full-order valuation completeness is retained.')
        count_key = {'overview':'analytical_lines', 'data_quality':'line_count', 'order_cancellation_and_aov':'orders'}.get(spec.analysis)
        if count_key and rows and rows[0][count_key] == 0:
            notes.append('No source lines/orders match these filters. Empty aggregate sums and rates are NULL, not measured zero values.')
        if len(rows) == spec.row_limit:
            notes.append(f'At most {spec.row_limit} rows displayed; raise the row limit to inspect more groups.')
        result = {'analysis': spec.analysis, 'title': TITLES[spec.analysis],
                'filters': spec.model_dump(mode='json'), 'rows': rows, 'notes': notes,
                'sql': sql, 'parameters': {k: json_value(v) for k, v in params.items()},
                'query_ms': round((time.perf_counter() - started) * 1000, 1)}
        if status_summary is not None:
            result.update(summary=status_summary, summary_sql=summary_sql,
                summary_parameters={k:json_value(v) for k,v in summary_params.items()})
        return result

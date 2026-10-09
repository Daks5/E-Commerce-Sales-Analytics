import copy
from datetime import date
import json
from types import SimpleNamespace
import pandas as pd
import pytest
from pydantic import ValidationError
from sqlalchemy import text
from assistant.config import ROOT, Settings
from assistant.queries import QueryService, QuerySpec, TITLES, compile_query
from assistant.gemini import AssistantError, GeminiAssistant, numeric_claims_supported, fallback_summary


@pytest.fixture(scope='module')
def service():
    return QueryService(Settings.load())


@pytest.fixture(scope='module')
def source():
    return pd.read_csv(ROOT / 'data/processed/analytical_order_lines.csv')


@pytest.mark.parametrize('analysis', list(TITLES))
def test_all_reviewed_queries_match_version_one(service, analysis):
    gold = json.loads((ROOT / 'reports/business_results.json').read_text(encoding='utf-8'))[analysis]
    actual = service.execute(QuerySpec(analysis=analysis, row_limit=200))['rows']
    # Some GROUP BY templates intentionally have no explicit display ordering.
    sort = lambda rows: sorted(rows, key=lambda row: str(list(row.values())[0]))
    assert len(actual) == len(gold)
    for observed, expected in zip(sort(actual), sort(gold)):
        assert set(observed) == set(expected)
        for key, value in expected.items():
            if isinstance(value, (int, float)):
                assert observed[key] == pytest.approx(value, abs=1e-5)
            else:
                assert observed[key] == (value[:10] if key == 'order_date' else value)


FILTERS = [
    {}, {'category': 'Set'}, {'category': 'Kurta'}, {'category': 'kurta'},
    {'state': 'MAHARASHTRA'}, {'state': 'KARNATAKA'}, {'state': 'DELHI'},
    {'fulfillment': 'Merchant'}, {'fulfillment': 'Amazon'},
    {'customer_type': 'Business (B2B)'}, {'customer_type': 'Retail'},
    {'start_date': '2022-05-01', 'end_date': '2022-05-29'},
    {'start_date': '2022-06-01', 'end_date': '2022-06-29'},
    {'start_date': '2022-03-31', 'end_date': '2022-03-31'},
    {'category': 'Set', 'fulfillment': 'Merchant'},
    {'category': 'Kurta', 'state': 'MAHARASHTRA'},
    {'category': 'Set', 'state': 'KARNATAKA', 'customer_type': 'Retail'},
    {'category': 'Set', 'customer_type': 'Business (B2B)', 'start_date': '2022-06-01'},
    {'state': 'DELHI', 'fulfillment': 'Amazon', 'end_date': '2022-04-30'},
    {'category': 'Set', 'state': 'MAHARASHTRA', 'fulfillment': 'Merchant', 'customer_type': 'Retail', 'start_date': '2022-05-01', 'end_date': '2022-05-29'},
]


def filtered(source, selections):
    frame = source
    for key, column in [('category', 'category'), ('state', 'ship_state'), ('fulfillment', 'fulfillment')]:
        if key in selections:
            frame = frame[frame[column].str.casefold() == selections[key].casefold()]
    if 'customer_type' in selections:
        frame = frame[frame.is_b2b == int(selections['customer_type'] == 'Business (B2B)')]
    if 'start_date' in selections:
        frame = frame[frame.order_date >= selections['start_date']]
    if 'end_date' in selections:
        frame = frame[frame.order_date <= selections['end_date']]
    return frame


@pytest.mark.parametrize('selection', FILTERS)
def test_filtered_totals_against_python_source(service, source, selection):
    frame = filtered(source, selection)
    sales = frame[frame.is_sales_eligible == 1]
    row = service.execute(QuerySpec(analysis='overview', **selection))['rows'][0]
    assert row['analytical_lines'] == len(frame)
    assert row['observed_orders'] == frame.order_id.nunique()
    assert row['shipped_sales_value'] == pytest.approx(sales.amount_minor.sum() / 100, abs=0.001)
    assert row['valued_shipped_units'] == sales.quantity.sum()
    assert row['valued_shipped_orders'] == sales.order_id.nunique()
    assert row['cancelled_lines'] == frame.is_cancelled.sum()
    assert row['missing_amount_lines'] == frame.amount_missing.sum()


@pytest.mark.parametrize('selection', FILTERS[:12])
def test_filtered_order_grain_and_aov(service, source, selection):
    frame = filtered(source, selection).copy()
    grouped = frame.groupby('order_id').agg(cancelled=('is_cancelled', 'max'), full=('is_cancelled', 'min'), complete=('order_valuation_complete', 'min'), eligible=('is_sales_eligible', 'max'))
    complete_ids = grouped[(grouped.complete == 1) & (grouped.eligible == 1)].index
    amount = frame[(frame.order_id.isin(complete_ids)) & (frame.is_sales_eligible == 1)].amount_minor.sum()/100
    row = service.execute(QuerySpec(analysis='order_cancellation_and_aov', **selection))['rows'][0]
    assert row['orders'] == len(grouped)
    assert row['any_cancelled_orders'] == grouped.cancelled.sum()
    assert row['fully_cancelled_orders'] == grouped.full.sum()
    assert row['complete_valued_orders'] == len(complete_ids)
    assert row['complete_order_aov'] == pytest.approx(amount/len(complete_ids), abs=1e-5)


@pytest.mark.parametrize('args', [
    {'analysis':'DROP TABLE fact_order_lines'}, {'analysis':'overview','sql':'DELETE FROM x'},
    {'analysis':'overview','row_limit':201}, {'analysis':'overview','row_limit':'10'},
    {'analysis':'overview','fulfillment':"Amazon'; DROP TABLE x;--"},
    {'analysis':'overview','start_date':'2023-01-01'},
    {'analysis':'overview','start_date':'2022-06-01','end_date':'2022-05-01'},
])
def test_invalid_requests_rejected(args):
    with pytest.raises(ValidationError):
        QuerySpec(**args)


def test_filters_bound_not_interpolated():
    value = "Set'; DELETE FROM fact_order_lines;--"
    sql, params = compile_query(QuerySpec(analysis='overview', category=value))
    assert value not in sql and params['category'] == value


def test_unknown_category_never_executes(service):
    with pytest.raises(ValueError):
        service.execute(QuerySpec(analysis='overview', category="Set'; DELETE FROM x;--"))


def test_fixed_comparison_ignores_date_filters(service):
    whole = service.execute(QuerySpec(analysis='comparable_may_june'))
    narrow = service.execute(QuerySpec(analysis='comparable_may_june', start_date='2022-04-01', end_date='2022-04-02'))
    assert whole['rows'] == narrow['rows']
    assert any('ignored' in note for note in narrow['notes'])


def test_connection_transaction_is_readonly(service):
    with service.engine.connect() as connection:
        assert connection.execute(text('SELECT @@transaction_read_only')).scalar() == 1


class Step:
    def __init__(self, kind='function_call', name='query_analysis', arguments=None, ident='call-1'):
        self.type, self.name, self.arguments, self.id = kind, name, arguments or {}, ident
    def model_dump(self, **kwargs):
        return {'type':self.type, 'name':self.name, 'arguments':self.arguments, 'id':self.id, 'signature':'preserve-exact-signature'}


class FakeClient:
    def __init__(self, responses):
        self.responses, self.requests = iter(responses), []
        self.interactions = self
    def create(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        value = next(self.responses)
        if isinstance(value, Exception):raise value
        return value


def response(steps=None, message=''):
    return SimpleNamespace(steps=steps or [], output_text=message, usage=SimpleNamespace(total_input_tokens=100, total_output_tokens=20))


def test_function_flow_retains_signature_and_evidence(service):
    client = FakeClient([response([Step(arguments={'analysis':'overview'})]), response(message='Valued shipped sales are ₹69,660,658.')])
    answer = GeminiAssistant(Settings.load(), service, client).ask('Sales overview')
    assert answer.kind == 'analysis' and answer.api_calls == 2
    history = client.requests[1]['input']
    assert history[1]['signature'] == 'preserve-exact-signature'
    payload = json.loads(history[2]['result'][0]['text'])
    assert 'sql' not in payload and 'parameters' not in payload
    assert answer.evidence[0]['rows'][0]['shipped_sales_value'] == 69660658
    assert client.requests[0]['store'] is False


def test_unverified_numbers_fall_back(service):
    client = FakeClient([response([Step(arguments={'analysis':'overview'})]), response(message='Sales are ₹999999999.')])
    answer = GeminiAssistant(Settings.load(), service, client).ask('Sales')
    assert '999999999' not in answer.text and '69,660,658' in answer.text


def test_no_query_no_numeric_answer(service):
    client = FakeClient([response(message='Sales are ₹123.')])
    answer = GeminiAssistant(Settings.load(), service, client).ask('Sales')
    assert answer.kind == 'clarification' and '123' not in answer.text


def test_profit_limitation_is_deterministic(service):
    client = FakeClient([response([Step(name='explain_limitation', arguments={'topic':'profit'})])])
    answer = GeminiAssistant(Settings.load(), service, client).ask('Profit?')
    assert answer.kind == 'limitation' and 'cost' in answer.text and not answer.evidence


def test_followup_context_is_transmitted(service):
    client = FakeClient([response([Step(name='request_clarification', arguments={'question':'Which cancellation rate would you like?'})])])
    GeminiAssistant(Settings.load(), service, client).ask('Only Merchant', [{'queries':[{'category':'Set'}]}])
    assert 'Set' in client.requests[0]['input'][0]['content'][0]['text']


def test_budget_limits_rounds(service):
    client = FakeClient([response([Step(arguments={'analysis':'overview'})])])
    answer = GeminiAssistant(Settings.load(), service, client).ask('Sales', request_budget=1)
    assert answer.api_calls == 1 and answer.evidence


def test_provider_error_does_not_expose_details(service):
    client = FakeClient([RuntimeError('secret-key-placeholder')])
    with pytest.raises(AssistantError) as caught:
        GeminiAssistant(Settings.load(), service, client).ask('Sales')
    assert 'secret' not in str(caught.value) and caught.value.api_calls == 1


def test_numeric_check():
    evidence = [{'rows':[{'value':69660658}], 'filters':{'row_limit':10}}]
    assert numeric_claims_supported('₹6.97 crore', evidence)
    assert not numeric_claims_supported('₹99889988', evidence)


def test_empty_aggregate_summary():
    result = {'analysis':'overview', 'rows':[{'analytical_lines':0, 'shipped_sales_value':None}]}
    assert 'No records' in fallback_summary([result])


def test_comparison_fallback_uses_verified_values():
    rows = json.loads((ROOT/'reports/business_results.json').read_text(encoding='utf-8'))['comparable_may_june']
    answer = fallback_summary([{'analysis':'comparable_may_june','rows':rows}])
    assert '21,906,300' in answer and '20,433,336' in answer
    assert '6.72% decrease' in answer

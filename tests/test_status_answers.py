"""Count answers must be explicit, use the right grain and admit missing reasons."""
import base64
import copy
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from assistant.config import ROOT, Settings
from assistant.gemini import GeminiAssistant, fallback_summary, numeric_claims_supported
from assistant.queries import QueryService, QuerySpec


SUMMARY = dict(observed_lines=100, observed_orders=80, cancelled_lines=20,
    cancelled_orders=15, returned_to_seller_lines=10, returning_to_seller_lines=5,
    returned_or_returning_lines=15, returned_to_seller_orders=8,
    returning_to_seller_orders=4, returned_or_returning_orders=11)


def result():
    return dict(analysis='status_distribution', title='Order status exposure',
        rows=[dict(status='Cancelled', line_count=20)], summary=SUMMARY,
        filters=dict(analysis='status_distribution', row_limit=1), notes=[],
        sql='SELECT reviewed status counts', summary_sql='SELECT reviewed complete counts',
        summary_parameters={}, parameters={}, query_ms=1)


def test_direct_line_counts_and_missing_reasons():
    text = fallback_summary([result()], 'How many products were cancelled or returned and why?')
    assert '20 order lines were cancelled' in text
    assert '10 order lines were marked Returned to Seller' in text
    assert '5 were marked Returning to Seller' in text
    assert '15 order lines marked returned or returning' in text
    assert 'no cancellation-reason or return-reason fields' in text
    assert 'not counts of unique products' in text
    assert 'see the notes' not in text


def test_order_counts_are_distinct_and_return_subgroups_can_overlap():
    text = fallback_summary([result()], 'How many orders were cancelled or returned?')
    assert '15 distinct orders were cancelled' in text
    assert '11 distinct orders marked returned or returning' in text
    assert 'may overlap' in text


def test_summary_counts_pass_numeric_check_even_with_truncated_rows():
    assert numeric_claims_supported('15 returned or returning lines.', [result()])
    assert not numeric_claims_supported('999 returned lines.', [result()])


class Call:
    type = 'function_call'
    def __init__(self, name, arguments):
        self.name, self.arguments, self.id = name, arguments, name + '-id'
    def model_dump(self, **kwargs):
        return dict(type=self.type, name=self.name, arguments=self.arguments, id=self.id)


def reply(text='', calls=None):
    return SimpleNamespace(output_text=text, steps=calls or [], usage=None)


class Client:
    def __init__(self, replies):
        self.interactions, self.replies, self.requests = self, iter(replies), []
    def create(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        return next(self.replies)


class Service:
    catalog = dict(categories=[], states=[])
    def execute(self, spec):
        assert spec.analysis == 'status_distribution'
        return result()


def settings():
    return Settings('localhost', 3306, 'test', 'test', '', api_key='test-only-key')


def test_count_and_why_preserves_answerable_part_and_blocks_invented_reasons():
    client = Client([reply(calls=[Call('query_analysis', {'analysis':'status_distribution'})]),
        reply('20 cancelled lines and 15 returns because of poor quality.')])
    answer = GeminiAssistant(settings(), Service(), client).ask('How many products were cancelled or returned and why?')
    assert '20 order lines' in answer.text and '15 order lines marked returned or returning' in answer.text
    assert 'poor quality' not in answer.text and 'cannot determine why' in answer.text
    assert answer.evidence and answer.kind == 'analysis'
    payload = json.loads(client.requests[-1]['input'][-1]['result'][0]['text'])
    assert payload['summary'] == SUMMARY
    assert 'summary_sql' not in payload and 'summary_parameters' not in payload


def test_limitation_tool_does_not_discard_count_question():
    client = Client([reply(calls=[Call('explain_limitation', {'topic':'causality'})]),
        reply(calls=[Call('query_analysis', {'analysis':'status_distribution'})]), reply('See notes.')])
    answer = GeminiAssistant(settings(), Service(), client).ask('How many items were cancelled or returned and why?')
    assert answer.api_calls == 3 and '20 order lines' in answer.text
    assert 'no cancellation-reason' in answer.text


def test_reason_only_is_a_clear_limitation():
    client = Client([reply(calls=[Call('explain_limitation', {'topic':'outcome_reasons'})])])
    answer = GeminiAssistant(settings(), Service(), client).ask('Why were items returned?')
    assert not answer.evidence and 'cannot determine why' in answer.text


def test_reason_only_does_not_show_an_unrequested_status_chart():
    client = Client([reply(calls=[Call('query_analysis', {'analysis':'status_distribution'})]), reply('See status notes.')])
    answer = GeminiAssistant(settings(), Service(), client).ask('Why were the products cancelled or returned?')
    assert answer.kind == 'limitation' and not answer.evidence
    assert 'no cancellation-reason or return-reason fields' in answer.text
    assert 'See status notes' not in answer.text


def test_count_without_sql_does_not_present_unverified_answer():
    client = Client([reply('20 products were returned.')])
    answer = GeminiAssistant(settings(), Service(), client).ask('How many products were returned?', request_budget=1)
    assert '20' not in answer.text and 'could not retrieve complete' in answer.text


@pytest.mark.parametrize('filters', [{}, {'category':'Kurta', 'state':'MAHARASHTRA'}, {'fulfillment':'Merchant'}])
def test_complete_status_summary_reconciles_with_independent_source(filters):
    source = pd.read_csv(ROOT / 'data/processed/analytical_order_lines.csv')
    for key, column in [('category','category'), ('state','ship_state'), ('fulfillment','fulfillment')]:
        if key in filters:
            source = source[source[column] == filters[key]]
    service = QueryService(Settings.load())
    actual = service.execute(QuerySpec(analysis='status_distribution', row_limit=1, **filters))
    summary = actual['summary']
    cancelled = source[source.is_cancelled == 1]
    returned = source[source.status == 'Shipped - Returned to Seller']
    returning = source[source.status == 'Shipped - Returning to Seller']
    combined = source[source.is_returned == 1]
    assert len(actual['rows']) == 1
    assert summary == dict(observed_lines=len(source), observed_orders=source.order_id.nunique(),
        cancelled_lines=len(cancelled), cancelled_orders=cancelled.order_id.nunique(),
        returned_to_seller_lines=len(returned), returning_to_seller_lines=len(returning),
        returned_or_returning_lines=len(combined), returned_to_seller_orders=returned.order_id.nunique(),
        returning_to_seller_orders=returning.order_id.nunique(), returned_or_returning_orders=combined.order_id.nunique())
    assert any('No cancellation-reason' in note for note in actual['notes'])


def test_status_chart_uses_order_line_counts_instead_of_recorded_money():
    ui = AppTest.from_file(str(ROOT / 'assistant/app.py'), default_timeout=45).run()
    ui.selectbox[0].set_value('status_distribution')
    ui.number_input[0].set_value(200)
    ui.button(key='FormSubmitter:explorer-Run analysis').click().run()
    assert not ui.exception
    frame = ui.dataframe[0].value
    chart = json.loads(ui.get('plotly_chart')[0].proto.spec)
    values = chart['data'][0]['x']
    if isinstance(values, dict):
        values = np.frombuffer(base64.b64decode(values['bdata']), dtype=values['dtype'])
    assert list(values) == list(frame.line_count)
    assert chart['layout']['xaxis']['title']['text'] == 'Order lines'

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import ssl
from unittest.mock import patch
import pytest
from assistant.config import Settings
from assistant.usage import BudgetExhausted, ProcessBudget


def test_cloud_tls_fails_closed_and_verifies_hostname():
    settings = Settings('cloud.example', 3306, 'db', 'reader', 'secret', cloud_mode=True)
    with pytest.raises(ValueError, match='requires MYSQL_SSL_CA'):
        settings.mysql_connect_args()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with patch('assistant.config.ssl.create_default_context', return_value=context) as make:
        args = replace(settings, ssl_ca='provider PEM').mysql_connect_args()
    make.assert_called_once_with(cadata='provider PEM')
    assert args['ssl'].check_hostname
    assert args['ssl'].verify_mode == ssl.CERT_REQUIRED
    assert 'READ ONLY' in args['init_command']
    assert 'ssl' not in replace(settings, cloud_mode=False).mysql_connect_args()


def test_budget_is_atomic_across_viewers():
    budget = ProcessBudget(30, clock=lambda: 3600)
    def reserve(_):
        try:
            return budget.reserve(4).slots
        except BudgetExhausted:
            return 0
    with ThreadPoolExecutor(10) as executor:
        assert sum(executor.map(reserve, range(20))) == 30


def test_budget_refunds_known_requests_once_and_handles_hour_rollover():
    clock = [3600]
    budget = ProcessBudget(4, clock=lambda: clock[0])
    lease = budget.reserve(4)
    budget.settle(lease, 2)
    budget.settle(lease, 0)  # Duplicate settlement cannot refund twice.
    assert budget.reserve(4).slots == 2
    with pytest.raises(BudgetExhausted):
        budget.reserve()
    clock[0] = 7200
    newer = budget.reserve(4)
    budget.settle(lease, 0)  # Old hour cannot change the new hour.
    with pytest.raises(BudgetExhausted):
        budget.reserve()
    budget.settle(newer, None)  # Unknown failure consumes reserved allowance.
    with pytest.raises(BudgetExhausted):
        budget.reserve()


def test_cloud_app_chat_is_public_and_keeps_usage_limits(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from assistant.config import ROOT
    from assistant.queries import QueryService
    from assistant.gemini import Answer, GeminiAssistant
    cloud = Settings('cloud.example', 3306, 'db', 'reader', 'secret',
                     cloud_mode=True, api_key='test-only-key',
                     shared_hourly_requests=97, max_requests=2)
    monkeypatch.setattr(Settings, 'load', classmethod(lambda cls: cloud))
    # Test the UI without a database connection or Gemini request.
    monkeypatch.setattr(QueryService, '__init__', lambda self, settings:
        setattr(self, 'catalog', {'categories': ['Kurta'], 'states': ['MAHARASHTRA']}))
    monkeypatch.setattr(QueryService, 'execute', lambda self, spec:
        {'rows': [{'shipped_sales_value': 69660658,
                   'valued_shipped_orders': 100227, 'cancelled_line_pct': 14.21}]})
    calls = []
    def fake_ask(self, question, context=None, request_budget=4):
        calls.append(request_budget)
        return Answer(question, 'Test answer.', [], 'limitation', api_calls=2)
    monkeypatch.setattr(GeminiAssistant, 'ask', fake_ask)
    ui = AppTest.from_file(str(ROOT / 'assistant/app.py'), default_timeout=45).run()
    assert not ui.exception
    assert not ui.chat_input[0].disabled
    assert len(ui.selectbox) == 5  # Public explorer controls remain present.
    assert len(ui.text_input) == 0
    assert len(ui.button) == 1  # Only the Query Explorer submit button.
    assert calls == []
    ui.chat_input[0].set_value('Explain missing amounts').run()
    assert not ui.exception
    assert calls == [2]
    assert ui.session_state['api_calls'] == 2
    assert ui.chat_input[0].disabled  # Existing session allowance still applies.
    monkeypatch.setattr(Settings, 'load', classmethod(lambda cls: replace(cloud, api_key='')))
    ui.run()
    assert not ui.exception
    assert any('Gemini is not configured' in info.value for info in ui.info)
    assert ui.chat_input[0].disabled

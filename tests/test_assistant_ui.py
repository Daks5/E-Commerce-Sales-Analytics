"""Exercise the rendered app without making external Gemini requests."""
from streamlit.testing.v1 import AppTest
from assistant.config import ROOT
from assistant.gemini import Answer, AssistantError, GeminiAssistant
from assistant.queries import QuerySpec


def app():
    result = AppTest.from_file(str(ROOT/'assistant/app.py'), default_timeout=45).run()
    assert not result.exception
    return result


def test_explorer_category_and_daily_series():
    ui = app()
    ui.selectbox[0].set_value('category_performance')
    ui.selectbox[3].set_value('Merchant')
    ui.button(key='FormSubmitter:explorer-Run analysis').click().run()
    assert not ui.exception
    frame = ui.dataframe[0].value
    assert frame.loc[frame.category == 'Set', 'shipped_value'].iloc[0] == 9161423
    ui.selectbox[0].set_value('daily_running_value')
    ui.number_input[0].set_value(200)
    ui.button(key='FormSubmitter:explorer-Run analysis').click().run()
    assert not ui.exception
    assert len(ui.dataframe[0].value) == 91


def test_chat_persists_evidence_and_usage(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-only-key')
    def fake_ask(self, question, context=None, request_budget=3):
        evidence = self.service.execute(QuerySpec(analysis='overview'))
        return Answer(question, 'Verified sales overview.', [evidence], 'analysis', api_calls=2)
    monkeypatch.setattr(GeminiAssistant, 'ask', fake_ask)
    ui = app()
    ui.chat_input[0].set_value('Give me a sales overview').run()
    assert not ui.exception
    assert ui.session_state['api_calls'] == 2
    assert ui.session_state['messages'][0].evidence[0]['rows'][0]['shipped_sales_value'] == 69660658
    assert any('Session API calls: 2/30' in entry.value for entry in ui.markdown)
    assert len(ui.sidebar) == 0
    assert not any(button.label == 'Clear conversation' for button in ui.button)
    ui.button(key='FormSubmitter:explorer-Run analysis').click().run()
    assert len(ui.session_state['messages']) == 1
    assert ui.session_state['api_calls'] == 2


def test_chat_provider_error_counts_attempt_without_crashing(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-only-key')
    def fail(self, *args, **kwargs):
        raise AssistantError('Gemini is temporarily unavailable.', api_calls=1)
    monkeypatch.setattr(GeminiAssistant, 'ask', fail)
    ui = app()
    ui.chat_input[0].set_value('Sales overview').run()
    assert not ui.exception
    assert ui.session_state['api_calls'] == 1
    assert any('Session API calls: 1/30' in entry.value for entry in ui.markdown)
    assert any('temporarily unavailable' in entry.value for entry in ui.error)


def test_document_answer_displays_citation_and_source_passage(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-only-key')
    source = dict(citation='D1', source='docs/cleaning_decisions.md', title='Cleaning decisions',
        section='Missing values', start_line=1, end_line=2,
        text='Missing amounts remain null; they are not imputed as zero.')
    def fake_ask(self, question, context=None, request_budget=4):
        return Answer(question, 'Missing amounts remain null. [D1]', [], 'documentation',
            api_calls=3, sources=[source], retrieval_calls=1)
    monkeypatch.setattr(GeminiAssistant, 'ask', fake_ask)
    ui = app()
    ui.chat_input[0].set_value('How are missing amounts treated?').run()
    assert not ui.exception
    assert any('Missing amounts remain null. [D1]' in item.value for item in ui.markdown)
    assert any('[D1] Cleaning decisions' in item.label for item in ui.expander)
    assert any('docs/cleaning_decisions.md' in item.value for item in ui.caption)
    assert ui.session_state['api_calls'] == 3

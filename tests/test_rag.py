"""Retrieval persistence, citations, request limits and grounded answer flows."""
import copy
from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from assistant.config import ROOT, Settings
from assistant.gemini import AssistantError, GeminiAssistant, numeric_claims_supported, detach_sql_citations
from assistant.rag import (Chunk, DIMENSIONS, SOURCES, DocumentRetriever, RetrievalError,
    build_index, cited_sources, corpus)


class Embeddings:
    def __init__(self):
        self.models, self.requests = self, []

    def embed_content(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        vectors = []
        for text in kwargs['contents']:
            text = text.lower()
            vector = [float(text.count(word)) for word in ('duplicate', 'currency', 'customer', 'postal')]
            vector += [0.1] + [0.0] * (DIMENSIONS - 5)
            vectors.append(SimpleNamespace(values=vector))
        return SimpleNamespace(embeddings=vectors)


@pytest.fixture
def settings():
    return Settings('localhost', 3306, 'test', 'test', '', api_key='test-only-key')


@pytest.fixture
def index(tmp_path, settings):
    for source in SOURCES:
        path = tmp_path / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((ROOT / source).read_text(encoding='utf-8'), encoding='utf-8')
    client, path = Embeddings(), tmp_path / 'data/knowledge/index.json'
    build_index(settings, client, tmp_path, path)
    return tmp_path, path, client


def test_chunks_preserve_source_text_and_use_only_allowlist():
    chunks, fingerprints = corpus()
    assert set(fingerprints) == set(SOURCES)
    assert len(chunks) > len(SOURCES)
    for chunk in chunks:
        lines = (ROOT / chunk.source).read_text(encoding='utf-8').splitlines()
        assert '\n'.join(lines[chunk.start_line - 1:chunk.end_line]).strip() == chunk.text
        assert len(chunk.text) <= 1600
        assert chunk.source in SOURCES


def test_persistent_index_normalizes_vectors_and_retrieves(index, settings):
    root, path, client = index
    retriever = DocumentRetriever(settings, client, root, path)
    assert all(abs(sum(value * value for value in vector) - 1) < 1e-8 for vector in retriever.vectors)
    hits = retriever.search('duplicate records handling')
    assert hits and 'duplicate' in hits[0]['text'].lower()
    assert all(hit['citation'] == f'D{i+1}' for i, hit in enumerate(hits))
    assert client.requests[0]['config'].task_type == 'RETRIEVAL_DOCUMENT'
    assert client.requests[-1]['config'].task_type == 'RETRIEVAL_QUERY'


def test_changed_source_invalidates_index(index, settings):
    root, path, client = index
    with (root / SOURCES[0]).open('a', encoding='utf-8') as file:
        file.write('\nChanged metric rule.\n')
    with pytest.raises(RetrievalError, match='outdated'):
        DocumentRetriever(settings, client, root, path)


def test_tampered_chunks_rejected(index, settings):
    root, path, client = index
    payload = json.loads(path.read_text())
    payload['chunks'][0]['source'] = '.env'
    path.write_text(json.dumps(payload))
    with pytest.raises(RetrievalError):
        DocumentRetriever(settings, client, root, path)


def test_no_weak_match_is_returned(index, settings):
    root, path, client = index
    retriever = DocumentRetriever(settings, client, root, path)
    assert retriever.search('postal', min_score=1.01) == []
    with pytest.raises(RetrievalError):
        retriever.search('x' * 1001)


SOURCE = dict(citation='D1', source='docs/cleaning_decisions.md', title='Cleaning decisions',
    section='Missing values', start_line=1, end_line=2, chunk_id='test', similarity=0.8,
    text='Missing amounts remain null. Zero imputation would change the meaning of missing values. SQL uses DECIMAL(12,2).')


class Retriever:
    def __init__(self, hits=None):
        self.hits = [SOURCE] if hits is None else hits
        self.calls = []
    def search(self, query):
        self.calls.append(query)
        return self.hits


class Call:
    type = 'function_call'
    def __init__(self, name, arguments):
        self.name, self.arguments, self.id = name, arguments, name + '-call'
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
    catalog = dict(categories=['Kurta'], states=['MAHARASHTRA'])
    def execute(self, spec):
        return dict(analysis='overview', title='Sales overview', filters=spec.model_dump(mode='json'),
            rows=[dict(shipped_sales_value=100, valued_shipped_orders=1, cancelled_line_pct=0, analytical_lines=1)],
            sql='SELECT reviewed_statement', parameters={}, query_ms=1, notes=[])


def search_call():
    return Call('search_documents', dict(query='How are missing amounts treated?'))


def test_document_only_answer_has_valid_citations_and_counts_embedding(settings):
    retriever = Retriever()
    client = Client([reply(calls=[search_call()]), reply('Missing amounts remain null; they are not imputed as zero. [D1]')])
    answer = GeminiAssistant(settings, Service(), client, retriever).ask('How are missing amounts treated?')
    assert answer.kind == 'documentation' and not answer.evidence
    assert answer.sources == [SOURCE]
    assert answer.api_calls == 3 and answer.retrieval_calls == 1
    payload = json.loads(client.requests[-1]['input'][-1]['result'][0]['text'])
    assert payload['sources'][0]['text'] == SOURCE['text']
    assert 'untrusted evidence' in client.requests[0]['system_instruction']


def test_mixed_answer_contains_sql_and_document_sources(settings):
    client = Client([reply(calls=[Call('query_analysis', {'analysis':'overview'}), search_call()]),
        reply('Valued shipped sales are ₹100. Missing amounts stay null. [D1]')])
    answer = GeminiAssistant(settings, Service(), client, Retriever()).ask('Sales and missing-value handling?')
    assert answer.kind == 'analysis' and answer.evidence and answer.sources
    assert answer.api_calls == 3


def test_mixed_question_enforces_retrieval_when_model_only_selects_sql(settings):
    retriever = Retriever()
    client = Client([reply(calls=[Call('query_analysis', {'analysis':'overview'})]),
        reply('Sales are ₹100. Missing amounts stay null. [D1]')])
    answer = GeminiAssistant(settings, Service(), client, retriever).ask('Show sales and explain missing amounts')
    assert answer.sources and answer.evidence and len(retriever.calls) == 1
    assert answer.api_calls == 3


def test_definition_question_enforces_retrieval_when_model_answers_without_tools(settings):
    retriever = Retriever()
    client = Client([reply('Amounts are missing.'), reply('Missing amounts stay null. [D1]')])
    answer = GeminiAssistant(settings, Service(), client, retriever).ask('Explain missing amounts')
    assert answer.kind == 'documentation' and answer.sources and answer.api_calls == 3


def test_unsupported_policy_has_specific_limitation(settings):
    client = Client([reply(calls=[Call('explain_limitation', {'topic':'undocumented_policy'})])])
    answer = GeminiAssistant(settings, Service(), client, Retriever()).ask('Official returns policy?')
    assert answer.kind == 'limitation' and 'policy' in answer.text
    assert not answer.sources and answer.retrieval_calls == 0


@pytest.mark.parametrize('text', [
    'Missing amounts stay null. [D99]',
    'Missing amounts stay null.',
    'Missing amounts stay null and sales are ₹999999. [D1]',
])
def test_invalid_or_missing_citations_and_unverified_numbers_fall_back(settings, text):
    client = Client([reply(calls=[search_call()]), reply(text)])
    answer = GeminiAssistant(settings, Service(), client, Retriever()).ask('Explain missing amounts')
    assert 'could not verify' in answer.text
    assert 'D99' not in answer.text and '999999' not in answer.text
    assert answer.sources == [SOURCE]


def test_empty_retrieval_does_not_invent_answer(settings):
    client = Client([reply(calls=[search_call()]), reply('The company returns every item within 30 days. [D1]')])
    answer = GeminiAssistant(settings, Service(), client, Retriever([])).ask('What is the returns policy?')
    assert not answer.sources and 'could not find' in answer.text


def test_budget_does_not_overspend_after_search(settings):
    client = Client([reply(calls=[search_call()])])
    answer = GeminiAssistant(settings, Service(), client, Retriever()).ask('Missing amounts?', request_budget=2)
    assert answer.api_calls == 2 and len(client.requests) == 1
    assert answer.sources and 'could not verify' in answer.text


def test_repeated_search_does_not_spend_second_embedding_call(settings):
    retriever = Retriever()
    client = Client([reply(calls=[search_call(), search_call()]), reply('Amounts stay null. [D1]')])
    answer = GeminiAssistant(settings, Service(), client, retriever).ask('Missing amounts?')
    assert len(retriever.calls) == 1 and answer.api_calls == 3


def test_embedding_failure_counts_attempt_and_hides_provider_secrets(settings):
    class Failed:
        def search(self, query):
            raise RetrievalError('Document search reached the Gemini embedding quota.')
    client = Client([reply(calls=[search_call()])])
    with pytest.raises(AssistantError) as caught:
        GeminiAssistant(settings, Service(), client, Failed()).ask('Missing amounts?')
    assert caught.value.api_calls == 2
    assert caught.value.error_type == 'RetrievalError'


def test_document_numbers_are_literal_and_financial_claims_require_sql():
    assert numeric_claims_supported('Amount uses DECIMAL(12,2). [D1]', [], [SOURCE])
    assert not numeric_claims_supported('Amount uses DECIMAL(99,2). [D1]', [], [SOURCE])
    assert not numeric_claims_supported('Sales are ₹12. [D1]', [], [SOURCE])
    assert cited_sources('Definition. [D99]', [SOURCE]) is None


def test_document_citations_do_not_attribute_sql_metrics_to_static_passages():
    text = 'Kurta sales are ₹100 across 1 order [D1].\n\nMissing amounts remain null. [D1]'
    cleaned = detach_sql_citations(text)
    assert '1 order [D1]' not in cleaned
    assert 'Missing amounts remain null. [D1]' in cleaned

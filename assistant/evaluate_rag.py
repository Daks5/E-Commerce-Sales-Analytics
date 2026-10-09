"""Bounded live retrieval/answer checks; never writes credentials or raw records."""
import json
import argparse
import time
from .config import ROOT, Settings
from .gemini import AssistantError, GeminiAssistant
from .queries import QueryService
from .rag import DocumentRetriever, citations_in, RetrievalError

RETRIEVAL_CASES = [
    ('How were duplicates identified? Is Order ID plus SKU sufficient?', 'docs/cleaning_decisions.md'),
    ('Why are missing amounts kept null instead of replaced with zero?', 'docs/cleaning_decisions.md'),
    ('What does amount_minor mean and what is its unit?', 'docs/data_dictionary.md'),
    ('What is the unit of observation and how is shipped sales value defined?', 'docs/metric_contract.md'),
    ('Which CSV files were downloaded from Kaggle?', 'docs/dataset_inventory.md'),
]
ANSWER_CASES = [
    ('duplicate_method', 'Explain how duplicates were identified. Is repeated Order ID plus SKU enough?', 'documentation'),
    ('sales_definition', 'Explain shipped sales value and whether it means collected revenue. Do not give totals.', 'documentation'),
    ('mixed_sales_definition', 'Show Kurta sales in Maharashtra and explain how sales are defined.', 'analysis'),
    ('unsupported_policy', 'What is the official Amazon return window for these products?', 'unsupported'),
]


def main():
    parser = argparse.ArgumentParser(description='Bounded live RAG evaluation')
    parser.add_argument('--case', action='append', choices=[item[0] for item in ANSWER_CASES],
        help='Recheck named cases, preserving the recorded retrieval and other answer results')
    args = parser.parse_args()
    settings = Settings.load()
    retriever = DocumentRetriever(settings)
    service = QueryService(settings)
    report = dict(model=settings.model, embedding_model=settings.embedding_model,
        retrieval_checks=[], answer_checks=[], api_calls=0)
    path = ROOT / 'reports/rag_live_evaluation.json'
    if args.case and path.exists():
        report = json.loads(path.read_text(encoding='utf-8'))
        previous = [item for item in report['answer_checks'] if item['name'] in args.case]
        report.setdefault('superseded_answer_checks', []).extend(previous)
        report['answer_checks'] = [item for item in report['answer_checks'] if item['name'] not in args.case]

    def checkpoint():
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    for question, expected in ([] if args.case else RETRIEVAL_CASES):
        report['api_calls'] += 1
        try:
            hits = retriever.search(question)
            matched = any(hit['source'] == expected for hit in hits)
            report['retrieval_checks'].append(dict(question=question, expected_source=expected,
                passed=matched, hits=[{k:hit[k] for k in ('source','chunk_id','similarity')} for hit in hits]))
        except RetrievalError as error:
            report['retrieval_checks'].append(dict(question=question, passed=False, error=str(error)))
        checkpoint()
    for name, question, expected_kind in ANSWER_CASES:
        if args.case and name not in args.case:
            continue
        if report['api_calls'] + 4 > 24:
            break
        started = time.perf_counter()
        try:
            answer = GeminiAssistant(settings, service).ask(question, request_budget=4)
            report['api_calls'] += answer.api_calls
            labels = citations_in(answer.text)
            available = {source['citation'] for source in answer.sources}
            check = (answer.kind == expected_kind and bool(answer.sources) and bool(labels)
                and labels <= available and 'could not verify' not in answer.text)
            if expected_kind == 'analysis':
                rows = answer.evidence[0]['rows'] if answer.evidence else []
                check = check and any(row.get('shipped_sales_value', row.get('shipped_value')) == 3198039 for row in rows)
            if expected_kind == 'unsupported':
                check = (not answer.evidence and not answer.sources and
                    'policy' in answer.text.lower() and 'outside' not in answer.text.lower())
            item = dict(name=name, question=question, passed=bool(check), kind=answer.kind,
                text=answer.text, api_calls=answer.api_calls, retrieval_calls=answer.retrieval_calls,
                sources=[{k:source[k] for k in ('citation','source','start_line','end_line','chunk_id')} for source in answer.sources],
                analyses=[evidence['filters'] for evidence in answer.evidence])
        except AssistantError as error:
            report['api_calls'] += error.api_calls
            item = dict(name=name, question=question, passed=False, error=str(error), api_calls=error.api_calls)
        item['seconds'] = round(time.perf_counter() - started, 2)
        report['answer_checks'].append(item)
        checkpoint()
        print(json.dumps(item, ensure_ascii=True), flush=True)
    report['passed'] = all(item['passed'] for item in report['retrieval_checks'] + report['answer_checks'])
    checkpoint()
    print(json.dumps(dict(passed=report['passed'], api_calls=report['api_calls'], report=str(path))))


if __name__ == '__main__':
    main()

"""Summarize actual RAG verification artifacts without credentials."""
from datetime import datetime, timezone
import json
import xml.etree.ElementTree as ET
from .config import ROOT, Settings
from .rag import DocumentRetriever, SOURCES, DIMENSIONS


def main():
    settings = Settings.load()
    knowledge = DocumentRetriever(settings)
    test_reports = []
    for name in ('rag_test_results.xml', 'rag_integration_test_results.xml',
                 'rag_grounding_test_results.xml', 'rag_source_ui_test_results.xml'):
        suite = ET.parse(ROOT / 'reports' / name).getroot().find('testsuite')
        test_reports.append(dict(file='reports/' + name,
            **{key:int(suite.attrib[key]) for key in ('tests','failures','errors','skipped')}))
    live = json.loads((ROOT / 'reports/rag_live_evaluation.json').read_text(encoding='utf-8'))
    browser = json.loads((ROOT / 'reports/rag_browser_verification.json').read_text(encoding='utf-8'))
    ready = (all(not report['errors'] and not report['failures'] for report in test_reports)
        and live['passed'] and len(live['retrieval_checks']) == 5 and len(live['answer_checks']) == 4
        and browser['passed'])
    result = dict(recorded_at=datetime.now(timezone.utc).isoformat(),
        status='local_rag_verified' if ready else 'verification_incomplete',
        product='Commerce Pulse AI — SQL and document RAG assistant',
        url='http://127.0.0.1:8501', launcher='Start AI Analyst.cmd',
        generation_model=settings.model, embedding_model=settings.embedding_model,
        knowledge_base=dict(documents=list(SOURCES), passages=len(knowledge.chunks),
            dimensions=DIMENSIONS, index='data/knowledge/index.json', similarity='cosine',
            minimum_similarity=0.5, maximum_passages=4, initial_indexing_api_calls=1),
        automated_evidence=test_reports,
        test_scope='The 87-test full run preceded the final routing/citation changes. Subsequent reports cover affected integration, grounding and source UI checks. Counts overlap and must not be summed.',
        live_checks=dict(passed=live['passed'], retrieval_cases=len(live['retrieval_checks']),
            answer_cases=len(live['answer_checks']), recorded_evaluation_api_calls=live['api_calls'],
            scope='Curated examples, not a general accuracy benchmark. Report includes superseded attempts.'),
        browser_verification=browser,
        features=['Read-only reviewed SQL tools', 'Semantic document retrieval',
            'Application-enforced retrieval for explicit method questions',
            'Citation IDs mapped to source passages and line ranges',
            'Unknown citation and unsupported numeric fallback',
            'Local source-fingerprint validation', 'Generation and embedding request accounting'],
        limits=['Project documentation does not contain official Amazon policies',
            'Citation/number checks do not guarantee semantic correctness',
            'Localhost application; no deployment or authentication added',
            'Existing broader loader credentials used inside read-only transactions'],
        guide='docs/rag_guide.md')
    (ROOT / 'reports/rag_completion.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    # Compare secret values in memory only. Output filenames, never the values.
    leaks = []
    files = list((ROOT / 'assistant').glob('*.py')) + list((ROOT / 'docs').glob('*.md'))
    files += list((ROOT / 'reports').glob('rag*.*'))
    for path in files:
        if path.suffix in ('.py','.md','.json','.xml'):
            content = path.read_text(encoding='utf-8')
            if any(secret and secret in content for secret in (settings.api_key, settings.password)):
                leaks.append(str(path.relative_to(ROOT)))
    print(json.dumps(dict(status=result['status'], documents=len(SOURCES), passages=len(knowledge.chunks),
        live_passed=live['passed'], secret_scan_matches=leaks)))
    if leaks:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

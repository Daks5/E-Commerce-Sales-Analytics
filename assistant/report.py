"""Write a credential-free delivery summary from real test evidence."""
from datetime import datetime, timezone
import json
from statistics import median
import xml.etree.ElementTree as ET
from .config import ROOT, Settings


def main():
    suite = ET.parse(ROOT/'reports/assistant_test_results.xml').getroot().find('testsuite')
    tests = {key:int(suite.attrib[key]) for key in ('tests','failures','errors','skipped')}
    live = json.loads((ROOT/'reports/assistant_live_evaluation.local.json').read_text(encoding='utf-8'))
    cases = live['cases']
    browser = json.loads((ROOT/'reports/assistant_browser_verification.json').read_text(encoding='utf-8'))
    ready = not (tests['errors'] or tests['failures']) and len(cases) == 9 and all(case['passed'] for case in cases)
    result = {
        'recorded_at':datetime.now(timezone.utc).isoformat(),
        'status':'local_mvp_verified' if ready else 'verification_incomplete',
        'product':'Commerce Pulse AI — separate Version 2 assistant',
        'url':'http://127.0.0.1:8501', 'launcher':'Start AI Analyst.cmd',
        'configured_model':Settings.load().model,
        'automated_tests':tests,
        'live_gemini':{'model':live['model'], 'passed':live['passed'], 'cases':len(cases),
            'api_calls':live['api_calls'], 'deterministic_fallbacks':sum(case.get('deterministic_fallback',False) for case in cases),
            'median_case_seconds':median(case['elapsed_seconds'] for case in cases),
            'scope':'Nine curated routing/filter/limitation cases, not a general accuracy benchmark'},
        'interface_verification':{'browser_observations':browser,
            'chat_evidence_usage_and_provider_errors':'Passing Streamlit AppTest with mocked provider'},
        'query_controls':{'reviewed_analyses':14,'parameter_validation':True,'bound_sql_parameters':True,
            'read_only_transactions_verified':True, 'maximum_rows':200, 'mysql_select_timeout_ms':15000,
            'maximum_api_calls_per_question':3, 'maximum_queries_per_question':4},
        'database_account':'Existing project loader used under read-only transactions; dedicated SELECT-only account optional, not provisioned',
        'power_bi':'Existing separate presentation dashboard; not embedded in Streamlit',
        'provider_availability':'3.8 and 3.7 Flash had temporary service/high-demand errors; tested 3.5 Flash Lite configured',
        'limitations':['Localhost only; no network authentication/deployment',
            'Gemini can make semantic errors; SQL evidence is authoritative',
            'Digit checks are a conservative fallback, not a factual-accuracy guarantee',
            'No profit/cost, customer-retention, causal-uplift or validated-forecast claims',
            'Provider quota, service availability and charges apply independently of the session allowance'],
        'evidence':['reports/assistant_test_results.xml','reports/assistant_live_evaluation.local.json',
            'reports/assistant_browser_verification.json','reports/screenshots_assistant/','docs/ai_assistant.md'],
    }
    chart_fix = ROOT/'reports/assistant_chart_fix.json'
    if chart_fix.exists():
        result['sku_chart_fix'] = json.loads(chart_fix.read_text(encoding='utf-8'))
    (ROOT/'reports/assistant_completion.json').write_text(json.dumps(result, indent=2, ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':result['status'],'tests':tests,'live_passed':live['passed'],'live_cases':len(cases)}))


if __name__ == '__main__':
    main()

"""Reconcile the hosted read-only database against the finished local results."""
import json
import math
import os
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    values = tomllib.loads((ROOT / '.private/streamlit_secrets.toml').read_text())
    os.environ.update({key:str(value) for key,value in values.items()})
    from assistant.config import Settings
    from assistant.queries import QueryService, QuerySpec, TITLES
    from assistant.rag import DocumentRetriever
    settings = Settings.load()
    service = QueryService(settings)
    gold = json.loads((ROOT / 'reports/business_results.json').read_text())
    checks = {}
    order = lambda rows: sorted(rows, key=lambda row:str(list(row.values())[0]))
    try:
        for name in TITLES:
            actual = service.execute(QuerySpec(analysis=name))['rows']
            expected = gold[name]
            passed = len(actual) == len(expected)
            for observed, target in zip(order(actual), order(expected)):
                passed &= set(observed) == set(target)
                for key, value in target.items():
                    passed &= (isinstance(observed.get(key), (float,int)) and math.isclose(observed[key], value, abs_tol=1e-5, rel_tol=1e-10)) if isinstance(value,(int,float)) else observed.get(key) == (value[:10] if key == 'order_date' and value else value)
            checks[name] = bool(passed)
        knowledge = DocumentRetriever(settings)
        result = dict(read_only=service.read_only, analyses=checks,
                      knowledge_passages=len(knowledge.chunks),
                      passed=service.read_only and all(checks.values()) and len(knowledge.chunks)==17)
        (ROOT / 'reports/cloud_database_verification.json').write_text(json.dumps(result,indent=2), encoding='utf-8')
        print(json.dumps(result))
        raise SystemExit(0 if result['passed'] else 1)
    finally:
        service.engine.dispose()


if __name__ == '__main__':
    main()

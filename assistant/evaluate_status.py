"""Bounded live checks for direct count answers and explicit missing evidence."""
import json
from .config import ROOT, Settings
from .gemini import AssistantError, GeminiAssistant
from .queries import QueryService, QuerySpec


def main():
    settings, report = Settings.load(), {'cases':[], 'api_calls':0}
    service = QueryService(settings)
    cases = [
        ('count_and_why', 'how much products were cancelled or return and why were they cancelled or returned', {}),
        ('filtered_orders', 'How many orders were cancelled or returned for Kurta in Maharashtra, and why?', {'category':'Kurta','state':'MAHARASHTRA'}),
        ('reasons_only', 'Why were the products cancelled or returned?', None),
        ('policy', 'What is the official Amazon return window for these products?', None),
    ]
    path = ROOT / 'reports/status_answer_live_evaluation.json'
    for name, question, filters in cases:
        if report['api_calls'] + 4 > 16:
            break
        try:
            answer = GeminiAssistant(settings, service).ask(question, request_budget=4)
            report['api_calls'] += answer.api_calls
            if filters is not None:
                expected = service.execute(QuerySpec(analysis='status_distribution', **filters))['summary']
                grain = 'orders' if name == 'filtered_orders' else 'lines'
                passed = all(f"{expected[field + '_' + grain]:,}" in answer.text for field in
                    ('cancelled','returned_to_seller','returning_to_seller','returned_or_returning'))
                matching = [item for item in answer.evidence if item['analysis']=='status_distribution']
                passed = passed and bool(matching) and all(matching[0]['filters'].get(key)==value for key,value in filters.items())
                passed = passed and 'no cancellation-reason or return-reason fields' in answer.text
            elif name == 'policy':
                passed = 'no supporting policy document' in answer.text.lower()
            else:
                passed = 'no cancellation-reason or return-reason fields' in answer.text and 'cannot determine why' in answer.text
            item = dict(name=name,question=question,text=answer.text,passed=bool(passed),api_calls=answer.api_calls,
                analyses=[result['filters'] for result in answer.evidence])
        except AssistantError as error:
            report['api_calls'] += error.api_calls
            item = dict(name=name,question=question,passed=False,error=str(error),api_calls=error.api_calls)
        report['cases'].append(item)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(item), flush=True)
    report['passed'] = len(report['cases']) == len(cases) and all(item['passed'] for item in report['cases'])
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(dict(passed=report['passed'],api_calls=report['api_calls'])))


if __name__ == '__main__':
    main()

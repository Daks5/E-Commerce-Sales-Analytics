"""Local setup diagnostics. Never prints credential values."""
import argparse
import json
from .config import Settings
from .queries import QueryService, QuerySpec


def main():
    parser = argparse.ArgumentParser(description='Commerce Pulse AI diagnostics')
    parser.add_argument('--gemini', action='store_true', help='Also send one short live Gemini test request')
    parser.add_argument('--tool', action='store_true', help='Test one minimal live Gemini function declaration')
    args = parser.parse_args()
    settings = Settings.load()
    service = QueryService(settings)
    print(json.dumps({'database_connected': True, 'read_only_transactions': service.read_only,
        'gemini_key_configured': settings.gemini_ready, 'model': settings.model,
        'overview': service.execute(QuerySpec(analysis='overview'))['rows']}, indent=2))
    if (args.gemini or args.tool) and settings.gemini_ready:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings.api_key, http_options=types.HttpOptions(timeout=20000, retry_options=types.HttpRetryOptions(attempts=1)))
        try:
            options = {'input':'Reply with just: ready'}
            if args.tool:
                options = {'input':'Use query_analysis to look up my sales.', 'tools':[{'type':'function', 'name':'query_analysis', 'description':'Look up verified sales.', 'parameters':{'type':'object', 'properties':{'analysis':{'type':'string', 'enum':['overview']}}, 'required':['analysis']}}]}
            result = client.interactions.create(model=settings.model, store=False, **options, generation_config={'thinking_level':'low', 'max_output_tokens':1000}, timeout=45)
            print('Gemini reply:', result.output_text)
            print('Step types:', [step.type for step in result.steps or []])
        except Exception as error:
            # Provider messages can include request details; remove local secrets.
            safe = str(error)
            for secret in (settings.api_key, settings.password):
                if secret:safe = safe.replace(secret, '[REDACTED]')
            print('Gemini diagnostic:', type(error).__name__, getattr(error, 'status_code', None), safe[:1000])


if __name__ == '__main__':
    main()

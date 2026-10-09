"""Small, persistent semantic index of explicitly approved project documents.

Only allowlisted Markdown is embedded. No credentials, raw records or arbitrary
uploads are read. Document changes invalidate the index instead of silently
serving stale passages. Gemini embedding calls are explicit, never automatic
when opening the app.
"""
from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from .config import ROOT, Settings

SOURCES = (
    'docs/metric_contract.md', 'docs/cleaning_decisions.md',
    'docs/data_dictionary.md', 'docs/dataset_inventory.md',
)
INDEX_PATH = ROOT / 'data/knowledge/index.json'
FORMAT_VERSION = 1
DIMENSIONS = 768


class RetrievalError(Exception):
    """Safe, actionable retrieval errors without provider request details."""


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source: str
    title: str
    section: str
    start_line: int
    end_line: int
    text: str


def corpus(root=ROOT):
    chunks, fingerprints = [], {}
    for source in SOURCES:
        content = (root / source).read_text(encoding='utf-8')
        fingerprints[source] = hashlib.sha256(content.encode()).hexdigest()
        lines = content.splitlines()
        title = lines[0].lstrip('# ').strip()
        section, pending, start = title, [], 1

        def flush(end):
            nonlocal pending
            text = '\n'.join(pending).strip()
            if text:
                digest = hashlib.sha256((source + '\n' + text).encode()).hexdigest()[:12]
                chunks.append(Chunk(digest, source, title, section, start, end, text))
            pending = []

        for number, line in enumerate(lines, 1):
            if line.startswith('#'):
                flush(number - 1)
                section = line.lstrip('# ').strip()
                start = number
            # Keep source lines (including table rows) intact and retain location.
            if pending and sum(len(item) + 1 for item in pending) + len(line) > 1600:
                flush(number - 1)
                start = number
            if not pending:
                start = number
            pending.append(line)
        flush(len(lines))
    return chunks, fingerprints


def normalized(vector):
    values = [float(value) for value in vector]
    if len(values) != DIMENSIONS or not all(math.isfinite(value) for value in values):
        raise RetrievalError('The knowledge index has invalid embedding dimensions. Rebuild it.')
    length = math.sqrt(sum(value * value for value in values))
    if not length:
        raise RetrievalError('An empty embedding was returned. Retry the knowledge index build.')
    return [value / length for value in values]


def make_client(settings):
    from google import genai
    from google.genai import types
    return genai.Client(api_key=settings.api_key,
        http_options=types.HttpOptions(timeout=45000, retry_options=types.HttpRetryOptions(attempts=1)))


def embed(client, model, texts, task):
    from google.genai import types
    try:
        result = client.models.embed_content(model=model, contents=texts,
            config=types.EmbedContentConfig(task_type=task, output_dimensionality=DIMENSIONS))
        embeddings = result.embeddings or []
        if len(embeddings) != len(texts):
            raise RetrievalError('The embedding response did not match the document count. Rebuild the index.')
        return [normalized(item.values) for item in embeddings]
    except RetrievalError:
        raise
    except Exception as error:
        code = getattr(error, 'status_code', None) or getattr(error, 'code', None)
        if code == 429:
            message = 'Document search reached the Gemini embedding quota. Wait and retry; Query Explorer remains available.'
        elif code in (401, 403):
            message = 'Document search could not access the embedding model. Check the Gemini key and project access.'
        else:
            message = 'The Gemini embedding request could not complete. Retry later; Query Explorer remains available.'
        raise RetrievalError(message) from None


def build_index(settings, client=None, root=ROOT, path=INDEX_PATH):
    if not settings.gemini_ready:
        raise RetrievalError('Configure GEMINI_API_KEY in .env before building the knowledge index.')
    chunks, fingerprints = corpus(root)
    client = client or make_client(settings)
    vectors, calls = [], 0
    for offset in range(0, len(chunks), 100):
        batch = chunks[offset:offset + 100]
        texts = [f'{item.title} — {item.section}\n{item.text}' for item in batch]
        vectors.extend(embed(client, settings.embedding_model, texts, 'RETRIEVAL_DOCUMENT'))
        calls += 1
    payload = dict(version=FORMAT_VERSION, model=settings.embedding_model,
        dimensions=DIMENSIONS, fingerprints=fingerprints,
        chunks=[asdict(item) for item in chunks], vectors=vectors)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)
    return dict(documents=len(fingerprints), passages=len(chunks), embedding_model=settings.embedding_model,
        dimensions=DIMENSIONS, indexing_api_calls=calls, index=str(path.relative_to(root)))


class DocumentRetriever:
    def __init__(self, settings, client=None, root=ROOT, path=INDEX_PATH):
        self.settings, self.client, self.root = settings, client, root
        try:
            payload = json.loads(Path(path).read_text(encoding='utf-8'))
            chunks, fingerprints = corpus(root)
            if (payload['version'] != FORMAT_VERSION or payload['model'] != settings.embedding_model
                    or payload['fingerprints'] != fingerprints or payload['dimensions'] != DIMENSIONS
                    or payload['chunks'] != [asdict(item) for item in chunks]
                    or len(payload['vectors']) != len(chunks)):
                raise ValueError('Stale index')
            self.chunks = chunks
            self.vectors = [normalized(vector) for vector in payload['vectors']]
        except (OSError, ValueError, KeyError, TypeError):
            raise RetrievalError('The knowledge index is missing or outdated. Run: python -m assistant.rag build') from None

    def search(self, query, top_k=4, min_score=0.5):
        if not query.strip() or len(query) > 1000 or not 1 <= top_k <= 4:
            raise RetrievalError('Enter a document search question of at most 1,000 characters.')
        if self.client is None:
            self.client = make_client(self.settings)
        vector = embed(self.client, self.settings.embedding_model, [query], 'RETRIEVAL_QUERY')[0]
        scores = [sum(a * b for a, b in zip(vector, stored)) for stored in self.vectors]
        indices = sorted(range(len(scores)), key=lambda i: (-scores[i], self.chunks[i].chunk_id))
        hits = []
        for index in indices:
            if len(hits) >= top_k or scores[index] < min_score:
                break
            hits.append(dict(asdict(self.chunks[index]), citation=f'D{len(hits) + 1}',
                similarity=round(scores[index], 5)))
        return hits


def citations_in(text):
    return set(re.findall(r'\[(D\d+)\]', text))


def cited_sources(text, sources):
    labels = citations_in(text)
    available = {source['citation'] for source in sources}
    if labels - available:
        return None
    return [source for source in sources if source['citation'] in labels]


def document_fallback(sources):
    if not sources:
        return 'I could not find supporting project documentation. Try a more specific question about the dataset, cleaning or metric definitions.'
    # Extractive fallback does not invent a paraphrase or attach fabricated citations.
    return 'I do not have a supported answer to this question from the available project documents. I could not verify an explanation from the retrieved passages; they are shown below only for reference.'


def main():
    parser = argparse.ArgumentParser(description='Build/search the approved project knowledge base')
    parser.add_argument('action', choices=['build', 'search', 'status'])
    parser.add_argument('query', nargs='?')
    args = parser.parse_args()
    settings = Settings.load()
    try:
        if args.action == 'build':
            result = build_index(settings)
        else:
            retriever = DocumentRetriever(settings)
            result = (retriever.search(args.query or '') if args.action == 'search'
                else dict(ready=True, documents=len(SOURCES), passages=len(retriever.chunks), model=settings.embedding_model))
        print(json.dumps(result, indent=2, ensure_ascii=True))
    except RetrievalError as error:
        print(str(error))
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()

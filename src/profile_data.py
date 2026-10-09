"""Inventory the downloaded archive without modifying source files."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data' / 'raw' / 'source'

def read_csv(path: Path, **kwargs):
    for encoding in ('utf-8-sig', 'cp1252'):
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False, **kwargs), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError(f'Unable to decode {path.name}')

def main():
    inventory = []
    for path in sorted(SOURCE.glob('*.csv')):
        df, encoding = read_csv(path, dtype='string')
        inferred, _ = read_csv(path)
        columns = []
        for col in df.columns:
            s = df[col]
            cleaned = s.str.strip().replace('', pd.NA)
            item = dict(name=col, inferred_dtype=str(inferred[col].dtype), missing=int(cleaned.isna().sum()), unique=int(cleaned.nunique()), examples=cleaned.dropna().drop_duplicates().head(3).tolist())
            if cleaned.nunique() <= 40:
                item['value_counts'] = {str(k): int(v) for k,v in cleaned.value_counts(dropna=False).items()}
            if col.strip().lower() in ('amount','qty','quantity','gross amt','rate'):
                numbers = pd.to_numeric(cleaned, errors='coerce')
                item['numeric'] = dict(min=None if numbers.dropna().empty else float(numbers.min()), max=None if numbers.dropna().empty else float(numbers.max()), missing=int(numbers.isna().sum()), zero=int(numbers.eq(0).sum()), negative=int(numbers.lt(0).sum()), sum=float(numbers.sum()))
            columns.append(item)
        record = dict(file=path.name, bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), encoding=encoding, rows=len(df), column_count=len(df.columns), exact_duplicate_rows=int(df.duplicated().sum()), columns=columns)
        inventory.append(record)
        print(json.dumps({k:v for k,v in record.items() if k != 'columns'}))
        print('Columns:', list(df.columns))
    (ROOT/'reports'/'dataset_inventory.json').write_text(json.dumps(inventory, indent=2, ensure_ascii=False),encoding='utf-8')
    lines = ['# Downloaded dataset inventory', '', 'Source: https://www.kaggle.com/datasets/thedevastator/unlock-profits-with-e-commerce-sales-data', '', '| File | Rows | Columns | Exact duplicate rows |', '|---|---:|---:|---:|']
    for r in inventory:
        lines.append(f"| {r['file']} | {r['rows']:,} | {r['column_count']} | {r['exact_duplicate_rows']:,} |")
    for r in inventory:
        lines += ['', '## '+r['file'], '', f"SHA-256: `{r['sha256']}`", '', '| Column | Inferred type | Missing | Unique |', '|---|---|---:|---:|']
        for c in r['columns']:
            lines.append(f"| {c['name']} | {c['inferred_dtype']} | {c['missing']:,} | {c['unique']:,} |")
    (ROOT/'docs'/'dataset_inventory.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__ == '__main__':
    main()

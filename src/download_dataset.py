"""Download only the selected Kaggle archive; never overwrite existing raw data."""
from pathlib import Path
import hashlib
import json
import urllib.request
import zipfile
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
URL='https://www.kaggle.com/api/v1/datasets/download/thedevastator/unlock-profits-with-e-commerce-sales-data'
PAGE='https://www.kaggle.com/datasets/thedevastator/unlock-profits-with-e-commerce-sales-data'

def main():
    raw=ROOT/'data/raw'
    raw.mkdir(parents=True,exist_ok=True)
    archive=raw/'kaggle_ecommerce.zip'
    if not archive.exists():
        urllib.request.urlretrieve(URL,archive)
    source=raw/'source'
    source.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for entry in z.infolist():
            target=(source/entry.filename).resolve()
            if not target.is_relative_to(source.resolve()):
                raise ValueError('Archive entry escapes the raw source folder.')
            if entry.is_dir():
                target.mkdir(parents=True,exist_ok=True)
            elif not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(z.read(entry))
    manifest={'source_page':PAGE,'download_url':URL,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'archive_bytes':archive.stat().st_size,'inventory_time_utc':datetime.now(timezone.utc).isoformat(),'files':[]}
    for path in sorted(source.glob('*.csv')):
        manifest['files'].append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size})
    (ROOT/'reports/source_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Archive verified; raw files preserved.')

if __name__=='__main__':
    main()

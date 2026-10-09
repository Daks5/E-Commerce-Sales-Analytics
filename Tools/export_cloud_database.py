"""Export the app's star schema and views without changing the source database.

Run from this deployment folder. Supply the original .env path explicitly.
Private artifacts are stored under .private/, excluded from version control.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('dim_date', 'dim_product', 'dim_geography', 'dim_status',
          'fact_order_lines', 'v_order_lines', 'v_order_summary')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-env', required=True, type=Path)
    parser.add_argument('--mysqldump', required=True, type=Path)
    args = parser.parse_args()
    values = dotenv_values(args.source_env)
    if values.get('MYSQL_DATABASE') != 'ecommerce_db':
        raise SystemExit('This export is restricted to the ecommerce_db project.')
    folder = ROOT / '.private'
    folder.mkdir(exist_ok=True)
    config = folder / 'export-client.cnf'
    output = folder / 'ecommerce_cloud.sql'
    def option(value):
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r') + '"'
    try:
        config.write_text('[client]\n' + '\n'.join(
            f'{name}={option(values[key])}' for name, key in
            [('host','MYSQL_HOST'), ('port','MYSQL_PORT'), ('user','MYSQL_USER'), ('password','MYSQL_PASSWORD')]), encoding='utf-8')
        command = [str(args.mysqldump), f'--defaults-extra-file={config}',
                   '--single-transaction', '--skip-add-drop-table', '--skip-add-locks',
                   '--skip-lock-tables', '--no-tablespaces', '--set-gtid-purged=OFF',
                   '--column-statistics=0', '--skip-triggers', '--skip-comments',
                   '--hex-blob', f'--result-file={output}', 'ecommerce_db', *TABLES]
        result = subprocess.run(command, capture_output=True)
        if result.returncode:
            raise SystemExit('Export failed. Check the source connection and mysqldump version; provider details are hidden.')
        sql = output.read_text(encoding='utf-8')
        sql, changed = re.subn(r'DEFINER=`[^`]+`@`[^`]+` SQL SECURITY DEFINER',
                               'DEFINER=CURRENT_USER SQL SECURITY INVOKER', sql)
        if changed != 2 or re.search(r'DEFINER=`', sql):
            raise SystemExit('Expected exactly two portable view definers; review the export before importing.')
        output.write_text(sql, encoding='utf-8', newline='\n')
        manifest = {'objects': list(TABLES), 'bytes': output.stat().st_size,
                    'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                    'view_security': 'INVOKER', 'source_modified': False}
        (folder / 'cloud_export_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        print(json.dumps(manifest))
    finally:
        config.unlink(missing_ok=True)


if __name__ == '__main__':
    main()

"""Restore the app database into an empty Aiven schema and create its reader.

Connection and generated secrets stay in ignored .private/. Existing target
objects or reader accounts cause a stop; the script never resets a password.
"""
import argparse
import json
from pathlib import Path
import secrets
import ssl
import subprocess
import sys
from dotenv import dotenv_values
import pymysql
import toml

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.private'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mysql', required=True, type=Path)
    parser.add_argument('--gemini-env', required=True, type=Path)
    args = parser.parse_args()
    connection = json.loads((PRIVATE / 'aiven_admin.json').read_text())
    if not connection['host'].endswith('.aivencloud.com') or connection['database'] != 'ecommerce_db':
        raise SystemExit('Target must be the named Aiven project database.')
    tls = ssl.create_default_context(cadata=connection['ca'])
    with pymysql.connect(host=connection['host'], port=connection['port'],
                         user=connection['user'], password=connection['password'],
                         ssl=tls, connect_timeout=15, read_timeout=30, autocommit=True) as admin:
        with admin.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s', ('ecommerce_db',))
            if cursor.fetchone()[0]:
                raise SystemExit('Target schema contains objects. Refusing to replace existing data.')
            cursor.execute("SELECT COUNT(*) FROM mysql.user WHERE user='ecommerce_reader'")
            if cursor.fetchone()[0]:
                raise SystemExit('Reader already exists. Refusing to reset an existing credential.')
            cursor.execute('CREATE DATABASE IF NOT EXISTS ecommerce_db CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs')
        ca_path = PRIVATE / 'aiven-ca.pem'
        ca_path.write_text(connection['ca'], encoding='utf-8')
        config = PRIVATE / 'import-client.cnf'
        def option(value):
            return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r') + '"'
        try:
            config.write_text('[client]\n' + '\n'.join(f'{key}={option(connection[key])}'
                              for key in ('host','port','user','password')), encoding='utf-8')
            with (PRIVATE / 'ecommerce_cloud.sql').open('rb') as source:
                result = subprocess.run([str(args.mysql), f'--defaults-extra-file={config}',
                    '--ssl-mode=VERIFY_IDENTITY', f'--ssl-ca={ca_path}', 'ecommerce_db'],
                    stdin=source, capture_output=True, timeout=600)
            if result.returncode:
                (PRIVATE / 'import_error.log').write_bytes(result.stderr)
                raise SystemExit('Import failed. Private diagnostics were saved locally; inspect the target before retrying.')
        finally:
            config.unlink(missing_ok=True)
        reader_password = secrets.token_urlsafe(32)
        reader = dict(DEPLOYMENT_MODE='cloud', MYSQL_HOST=connection['host'], MYSQL_PORT=str(connection['port']),
                      MYSQL_DATABASE='ecommerce_db', MYSQL_ASSISTANT_USER='ecommerce_reader',
                      MYSQL_ASSISTANT_PASSWORD=reader_password, MYSQL_SSL_CA=connection['ca'],
                      GEMINI_API_KEY=dotenv_values(args.gemini_env)['GEMINI_API_KEY'],
                      GEMINI_MODEL='gemini-3.5-flash-lite', GEMINI_EMBEDDING_MODEL='gemini-embedding-001',
                      ASSISTANT_MAX_REQUESTS='30', SHARED_HOURLY_REQUESTS='30')
        # Save the generated credential before CREATE USER so a partial run does
        # not strand it. This file is never committed or printed.
        (PRIVATE / 'streamlit_secrets.toml').write_text(toml.dumps(reader), encoding='utf-8')
        with admin.cursor() as cursor:
            cursor.execute("CREATE USER 'ecommerce_reader'@'%%' IDENTIFIED BY %s REQUIRE SSL WITH MAX_USER_CONNECTIONS 4", (reader_password,))
            cursor.execute("GRANT SELECT ON ecommerce_db.* TO 'ecommerce_reader'@'%'")
        with pymysql.connect(host=connection['host'], port=connection['port'], user='ecommerce_reader',
                             password=reader_password, database='ecommerce_db', ssl=tls,
                             connect_timeout=15, autocommit=True) as limited:
            with limited.cursor() as cursor:
                cursor.execute('SHOW GRANTS')
                grants = [row[0] for row in cursor.fetchall()]
                if any('ALL PRIVILEGES' in grant or 'GRANT OPTION' in grant for grant in grants):
                    raise SystemExit('Reader privileges are broader than intended.')
                cursor.execute('SELECT COUNT(*) FROM v_order_lines')
                assert cursor.fetchone()[0] == 128969
                cursor.execute('SELECT SUM(amount_minor)/100 FROM v_order_lines WHERE is_sales_eligible=1')
                assert float(cursor.fetchone()[0]) == 69660658
                cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
                cipher = cursor.fetchone()[1]
                assert cipher
        status = dict(imported=True, reader_select_only=True, analytical_lines=128969,
                      shipped_value=69660658, tls_cipher=cipher, imported_objects=7)
        (PRIVATE / 'cloud_import_check.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
        print(json.dumps(status))


if __name__ == '__main__':
    try:
        main()
    except (pymysql.MySQLError, ssl.SSLError, OSError, subprocess.TimeoutExpired) as error:
        PRIVATE.mkdir(exist_ok=True)
        (PRIVATE / 'connection_error.local.txt').write_text(repr(error), encoding='utf-8')
        code = error.args[0] if error.args and isinstance(error.args[0], int) else None
        print(json.dumps({'error_class':type(error).__name__, 'error_code':code}), file=sys.stderr)
        print('Cloud connection or import could not finish. Check service readiness and private connection settings; credentials are hidden.', file=sys.stderr)
        raise SystemExit(1)

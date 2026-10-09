from dataclasses import dataclass, field
import os
import ssl
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)
    api_key: str = field(repr=False, default='')
    model: str = 'gemini-3.5-flash-lite'
    max_requests: int = 30
    embedding_model: str = 'gemini-embedding-001'
    cloud_mode: bool = False
    ssl_ca: str = field(repr=False, default='')
    demo_access_code: str = field(repr=False, default='')
    shared_hourly_requests: int = 30

    @classmethod
    def load(cls):
        values = dotenv_values(ROOT / '.env')
        # Streamlit initializes its root-level secrets when accessed. Explicitly
        # read them too so CLI environment variables and cloud secrets both work.
        secrets = {}
        try:
            import streamlit as st
            secrets = dict(st.secrets)
        except FileNotFoundError:
            pass
        def get(name, default=''):
            return os.getenv(name, str(secrets.get(name, values.get(name) or default)))
        return cls(
            host=get('MYSQL_HOST', '127.0.0.1'), port=int(get('MYSQL_PORT', '3306')),
            database=get('MYSQL_DATABASE', 'ecommerce_db'),
            user=get('MYSQL_ASSISTANT_USER') or get('MYSQL_USER'),
            password=get('MYSQL_ASSISTANT_PASSWORD') if get('MYSQL_ASSISTANT_USER') else get('MYSQL_PASSWORD'),
            api_key=get('GEMINI_API_KEY'), model=get('GEMINI_MODEL', 'gemini-3.5-flash-lite'),
            max_requests=max(1, min(int(get('ASSISTANT_MAX_REQUESTS', '30')), 100)),
            embedding_model=get('GEMINI_EMBEDDING_MODEL', 'gemini-embedding-001'),
            cloud_mode=get('DEPLOYMENT_MODE', 'cloud').lower() == 'cloud',
            ssl_ca=get('MYSQL_SSL_CA'), demo_access_code=get('DEMO_ACCESS_CODE'),
            shared_hourly_requests=max(1, min(int(get('SHARED_HOURLY_REQUESTS', '30')), 100)),
        )

    def mysql_connect_args(self):
        args = {'connect_timeout': 8, 'read_timeout': 20, 'write_timeout': 8,
                'init_command': 'SET SESSION TRANSACTION READ ONLY'}
        if self.cloud_mode and not self.ssl_ca.strip():
            raise ValueError('Cloud MySQL requires MYSQL_SSL_CA; TLS cannot be disabled.')
        if self.ssl_ca.strip():
            # The secret contains the provider's PEM CA certificate, not a
            # laptop-specific filename. Verify both issuer and server hostname.
            context = ssl.create_default_context(cadata=self.ssl_ca)
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            args['ssl'] = context
        return args

    @property
    def gemini_ready(self):
        return bool(self.api_key.strip()) and not self.api_key.startswith(('your_', 'replace_'))

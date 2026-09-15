import os

# Settings are validated at import time; give tests a throwaway database and a key that
# passes the 32-character SECRET_KEY check, unless the environment already provides them.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "local-test-secret-key-0123456789abcdef")

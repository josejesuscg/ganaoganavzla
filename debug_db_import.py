# debug_db_import.py
import db, os
import inspect
from urllib.parse import urlparse
print("db module file:", inspect.getsourcefile(db))
# mostrar host del DATABASE_URL (sin credenciales)
print("DATABASE_URL presente?:", bool(os.getenv("DATABASE_URL")))
try:
    from dotenv import load_dotenv
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if url:
        parsed = urlparse(url)
        print("DB host:", parsed.hostname, "port:", parsed.port, "db:", parsed.path)
    else:
        print("DATABASE_URL is empty")
except Exception as e:
    print("Error leyendo env:", e)

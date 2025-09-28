# db.py (REEMPLAZAR COMPLETO)
import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("SUPABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Falta DATABASE_URL en variables de entorno (.env o Replit Secrets)")

def _dsn_with_ssl(dsn: str) -> str:
    if "sslmode=" in dsn:
        return dsn
    return dsn + ("&sslmode=require" if "?" in dsn else "?sslmode=require")

@contextmanager
def get_conn():
    conn = psycopg2.connect(_dsn_with_ssl(DATABASE_URL))
    try:
        conn.set_client_encoding('UTF8')
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    user_id BIGINT,
                    username TEXT,
                    nombre TEXT,
                    telefono TEXT,
                    cedula TEXT,
                    numeros TEXT,
                    precio NUMERIC,
                    estado TEXT,
                    imagen_url TEXT,
                    hash_pago TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

def crear_ticket_db(*, ticket_id:str, user_id:int, username:str, nombre:str,
                    telefono:str, cedula:str, numeros:list, precio:float,
                    imagen_url:str="", hash_pago:str="", estado:str="Pendiente"):
    """
    Inserta y retorna True si realmente insertó. Si ya existía ticket_id, retorna False.
    """
    numeros_csv = ", ".join(numeros) if isinstance(numeros, (list, tuple)) else str(numeros)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tickets (ticket_id, user_id, username, nombre, telefono, cedula,
                                         numeros, precio, estado, imagen_url, hash_pago)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (ticket_id) DO NOTHING
                    RETURNING ticket_id;
                """, (ticket_id, user_id, username, nombre, telefono, cedula,
                      numeros_csv, precio, estado, imagen_url, hash_pago))
                row = cur.fetchone()
                if row:
                    return True
                else:
                    return False
    except Exception as e:
        # para debugging, lanzamos excepción con información
        raise RuntimeError(f"Error en crear_ticket_db: {e}")

def actualizar_estado_db(ticket_id:str, estado:str):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE tickets SET estado=%s WHERE ticket_id=%s RETURNING ticket_id;", (estado, ticket_id))
                row = cur.fetchone()
                return bool(row)
    except Exception as e:
        raise RuntimeError(f"Error en actualizar_estado_db: {e}")

def fetch_all_tickets():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""SELECT ticket_id, username, user_id, telefono, cedula, numeros,
                                  COALESCE(precio,0) AS precio, COALESCE(estado,'') AS estado,
                                  COALESCE(imagen_url,'') AS imagen_url,
                                  COALESCE(hash_pago,'') AS hash_pago,
                                  created_at
                           FROM tickets
                           ORDER BY created_at ASC;""")
            rows = cur.fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["numeros"] = [n.strip() for n in (d.get("numeros") or "").split(",") if n.strip()]
                out.append(d)
            return out

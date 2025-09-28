# test_insert_and_list.py
import uuid, traceback
import db, json, inspect

print("db module file:", inspect.getsourcefile(db))

ticket_id = "TST-" + uuid.uuid4().hex[:12].upper()
try:
    ok = db.crear_ticket_db(
        ticket_id=ticket_id,
        user_id=999999999,
        username="prueba_user",
        nombre="Prueba BD",
        telefono="+000000000",
        cedula="V-0000000",
        numeros=["01","02"],
        precio=1.0,
        imagen_url="",
        hash_pago="",
        estado="Pendiente"
    )
    print("crear_ticket_db returned:", ok, "ticket_id:", ticket_id)
except Exception as e:
    print("ERROR al llamar crear_ticket_db:")
    traceback.print_exc()

print("\nListado (últimos 10):")
try:
    t = db.fetch_all_tickets()
    print(json.dumps(t[-10:], indent=2, ensure_ascii=False))
    print("Total tickets:", len(t))
except Exception as e:
    print("ERROR listando tickets:")
    traceback.print_exc()

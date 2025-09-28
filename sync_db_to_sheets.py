# sync_db_to_sheets.py
import db
import respaldo

def sync_db_to_sheets():
    tickets = db.fetch_all_tickets()
    if not tickets:
        print("⚠️ No hay tickets en la BD para sincronizar.")
        return

    ws = respaldo.get_worksheet("Tickets")

    # Limpiar hoja antes de volcar datos
    ws.clear()

    # Encabezados — deben coincidir con tu hoja
    headers = [
        "TICKET ID",
        "USERNAME O NOMBRE",
        "USER ID TLG",
        "TELEFONO",
        "CEDULA",
        "NUMEROS",
        "MONTO",
        "FECHA",
        "ESTADO",
        "IMAGEN URL",
    ]
    ws.append_row(headers, value_input_option="USER_ENTERED")

    # Volcar todos los tickets de la BD
    for t in tickets:
        fila = [
            t.get("ticket_id", ""),
            t.get("username", ""),
            t.get("user_id", ""),
            t.get("telefono", ""),
            t.get("cedula", ""),
            ",".join(t.get("numeros", [])),
            str(t.get("precio", "")),
            str(t.get("fecha", "")),
            t.get("estado", ""),
            t.get("imagen_url", ""),
        ]
        ws.append_row(fila, value_input_option="USER_ENTERED")

    print(f"✅ Sync completo. Tickets volcados: {len(tickets)}")

if __name__ == "__main__":
    sync_db_to_sheets()

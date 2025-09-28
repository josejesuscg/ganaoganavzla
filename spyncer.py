# syncer.py
import os
import db
import respaldo

def row_from_ticket(ticket: dict) -> dict:
    return {
        "ticket_id": ticket["id"],
        "username_or_nombre": ticket.get("username") or ticket.get("nombre") or "",
        "user_id": ticket["user_id"],
        "telefono": ticket.get("telefono",""),
        "cedula": ticket.get("cedula",""),
        "numeros": ticket.get("numeros", []),
        "estado": ticket.get("estado","Pendiente ⏳"),
        "imagen_url": ticket.get("imagen_url",""),
        "precio": float(ticket.get("precio", 1.0)),
        "hash_pago": ticket.get("hash_pago","") or ticket.get("hash","") or ""
    }

def sync_ticket_to_sheet(ticket_id: str) -> bool:
    ticket = db.obtener_ticket(ticket_id)
    if not ticket:
        return False
    info = row_from_ticket(ticket)
    try:
        ok = respaldo.respaldar_ticket(
            ticket_id=info["ticket_id"],
            username_or_nombre=info["username_or_nombre"],
            user_id=info["user_id"],
            telefono=info["telefono"],
            cedula=info["cedula"],
            numeros=info["numeros"],
            estado=info["estado"],
            imagen_url=info["imagen_url"],
            precio=info["precio"],
            hash_pago=info["hash_pago"]
        )
        if not ok:
            try:
                respaldo.actualizar_estado_ticket(ticket_id, info["estado"])
            except Exception:
                pass
        return True
    except Exception:
        return False

def sync_db_to_sheet():
    tickets = db.obtener_todos()
    try:
        respaldo.borrar_registros_sheets()
    except Exception:
        pass
    for t in tickets:
        row = row_from_ticket(t)
        respaldo.respaldar_ticket(
            ticket_id=row["ticket_id"],
            username_or_nombre=row["username_or_nombre"],
            user_id=row["user_id"],
            telefono=row["telefono"],
            cedula=row["cedula"],
            numeros=row["numeros"],
            estado=row["estado"],
            imagen_url=row["imagen_url"],
            precio=row["precio"],
            hash_pago=row["hash_pago"]
        )
    return True

# syncer.py
import logging
import respaldo

log = logging.getLogger(__name__)

def sync_ticket_insert(*, ticket_id, username_or_nombre, user_id, telefono, cedula,
                       numeros, precio, estado="Pendiente ⏳", imagen_url="", hash_pago=""):
    ok = respaldo.respaldar_ticket(
        ticket_id=ticket_id,
        username_or_nombre=username_or_nombre,
        user_id=user_id,
        telefono=telefono,
        cedula=cedula,
        numeros=numeros,
        estado=estado,
        imagen_url=imagen_url,
        precio=precio,
        hash_pago=hash_pago
    )
    if not ok:
        log.warning("No se pudo insertar en Sheets el ticket %s", ticket_id)
    return ok

def sync_ticket_estado(ticket_id, nuevo_estado):
    ok = respaldo.actualizar_estado_ticket(ticket_id, nuevo_estado)
    if not ok:
        log.warning("No se pudo actualizar estado en Sheets para %s", ticket_id)
    return ok

def sync_ticket_imagen(ticket_id, imagen_url):
    ok = respaldo.actualizar_imagen_ticket(ticket_id, imagen_url)
    if not ok:
        log.warning("No se pudo actualizar imagen_url en Sheets para %s", ticket_id)
    return ok

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import logging
from gspread.exceptions import GSpreadException
import os
import json


try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
    

CREDENCIALES_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credenciales.json")
SHEET_ID = os.getenv("SHEET_ID", "")
SHEET_TAB_TICKETS = os.getenv("SHEET_TAB_TICKETS", "Tickets")


logger = logging.getLogger(__name__)

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

#TELEGRAM_BOT_TOKEN = "8119337796:AAHGQ8Qa2mdlhokn01FHyL0p3wqOj_rmoiU"
#TELEGRAM_CHANNEL_ID = "TU_CANAL_AQUÍ"

_gc = None
_sheet = None

def _get_client():
    global _gc
    if _gc is None:
        with open(CREDENCIALES_JSON) as f:
            creds = json.load(f)
        _gc = gspread.service_account_from_dict(creds)
    return _gc

def get_sheet():
    global _sheet
    if _sheet is None:
        client = _get_client()
        _sheet = client.open_by_key(SHEET_ID)
    return _sheet

def get_worksheet(tab_name: str):
    sheet = get_sheet()
    return sheet.worksheet(tab_name)



# Obtenemos la instancia del sistema para acceder al formato de números


def _obtener_hoja():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENCIALES_JSON, SCOPE)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1
    except FileNotFoundError:
        logger.critical(f"Archivo de credenciales no encontrado: {CREDENCIALES_JSON}")
        raise
    except GSpreadException as e:
        logger.error(f"Error de API Google Sheets: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error inesperado al conectar con Sheets: {str(e)}")
        raise

# Variable global para el formato
# Al inicio del archivo, después de los imports
formato_numero = "{:02d}"  # Valor por defecto

def set_formato_numero(digitos: int):
    """Sincroniza el formato con main.py"""
    global formato_numero
    formato_numero = f"{{:0{digitos}d}}"
    logger.info(f"Formato de números actualizado a {digitos} dígitos")
    
# Inicializa con el valor por defecto (2 dígitos)


def respaldar_ticket(ticket_id, username_or_nombre, user_id, telefono, cedula, numeros, estado="Pendiente ⏳", imagen_url="", precio=1.0, hash_pago=""):
    try:
        sheet = _obtener_hoja()
        fecha_venezuela = datetime.now() - timedelta(hours=4)
        fecha_actual = fecha_venezuela.strftime("%d/%m/%Y %H:%M:%S")
        monto_total = len(numeros) * precio

        # Mantener los números exactamente como fueron recibidos
        nueva_fila = [
            ticket_id,
            username_or_nombre,
            str(user_id),
            telefono,
            cedula,
            ", ".join(numeros),  # Sin modificación
            f"{monto_total:.2f}",
            fecha_actual,
            estado,
            imagen_url,
            hash_pago
        ]

        sheet.insert_row(nueva_fila, index=2)
        return True
    except Exception as e:
        logger.error(f"Error al respaldar ticket {ticket_id}: {str(e)}")
        return False

def actualizar_estado_ticket(ticket_id, nuevo_estado):
    try:
        sheet = _obtener_hoja()
        # Buscar en TODA la columna A (sin asumir posición)
        cell_list = sheet.findall(str(ticket_id).strip(), in_column=1)

        if not cell_list:
            logger.warning(f"No se encontró el ticket: {ticket_id}")
            return False

        # Actualizar PRIMERA coincidencia (columna I = ESTADO)
        sheet.update_cell(cell_list[0].row, 9, nuevo_estado)
        return True

    except Exception as e:
        logger.error(f"Error crítico al actualizar {ticket_id}: {str(e)}")
        return False



def borrar_registros_sheets():
    try:
        sheet = _obtener_hoja()
        registros = sheet.get_all_values()
        if len(registros) <= 1:
            return True
        sheet.batch_clear(["A2:K{}".format(len(registros))])
        return True
    except Exception as e:
        logger.error(f"Error al borrar registros: {str(e)}")
        return False

def cargar_tickets_desde_sheets():
    try:
        sheet = _obtener_hoja()
        todos_los_valores = sheet.get_all_values()

        restaurados = {
            "verificados": {},
            "pendientes": [],
            "digitos_detectados": None,
            "existen_datos": False
        }

        if not todos_los_valores or len(todos_los_valores) <= 1:
            return restaurados

        encabezados = todos_los_valores[0]
        registros = []
        for fila_valores in todos_los_valores[1:]:
            if not any(fila_valores):
                continue

            while len(fila_valores) < len(encabezados):
                fila_valores.append("")

            fila_dict = dict(zip(encabezados, fila_valores))
            registros.append(fila_dict)

        if not registros:
            return restaurados

        max_digitos = 2
        numeros_encontrados = False

        for fila in registros:
            numeros_str = str(fila.get("NUMEROS", "")).strip()
            if not numeros_str:
                continue

            numeros_procesados = []
            for n in numeros_str.split(","):
                n = n.strip()
                if n and n.isdigit():
                    if len(n) > max_digitos:
                        max_digitos = len(n)
                    numeros_procesados.append(n)
                    numeros_encontrados = True

            ticket_id_str = str(fila.get("TICKET ID", "")).strip()
            # Asegurar que siempre haya un ticket_id único para cada fila con datos
            if not ticket_id_str:
                # Genera un ID temporal si la celda está vacía
                fila_con_datos = [str(v) for v in fila.values() if str(v).strip()]
                fila_hash = str(hash("".join(fila_con_datos)))[-8:]
                ticket_id_str = f"TMP_ID_{fila_hash}"

            ticket_id = ticket_id_str

            if not numeros_procesados:
                continue

            datos_ticket = {
                "ticket_id": ticket_id,
                "user_id": int(fila.get("USER ID TLG", 0)) if str(fila.get("USER ID TLG", "0")).isdigit() else 0,
                "numeros": numeros_procesados,
                "hash": str(fila.get("HASH", "")).strip(),
                "estado": str(fila.get("ESTADO", "")).strip(),
                "nombre": str(fila.get("USERNAME O NOMBRE", "")).strip(),
                "telefono": str(fila.get("TELEFONO", "")).strip(),
                "cedula": str(fila.get("CEDULA", "")).strip(),
                "fecha": str(fila.get("FECHA", "")).strip(),
                "imagen_url": str(fila.get("IMAGEN URL", "")).strip()
            }

            estado_lower = datos_ticket["estado"].lower()
            if "verificado" in estado_lower and "no" not in estado_lower and "rechazado" not in estado_lower:
                restaurados["verificados"][ticket_id] = datos_ticket
            elif "rechazado" not in estado_lower and "verificado" not in estado_lower:
                restaurados["pendientes"].append(datos_ticket)

        if numeros_encontrados:
            restaurados["digitos_detectados"] = max_digitos
            restaurados["existen_datos"] = True

            for ticket in restaurados["verificados"].values():
                ticket["numeros"] = [n.zfill(max_digitos) for n in ticket["numeros"]]
            for ticket in restaurados["pendientes"]:
                ticket["numeros"] = [n.zfill(max_digitos) for n in ticket["numeros"]]

        return restaurados

    except Exception as e:
        logger.critical(f"Error al cargar tickets: {str(e)}")
        return {
            "verificados": {},
            "pendientes": [],
            "digitos_detectados": None,
            "existen_datos": False
        }

#--------------------------------------------------------------



def eliminar_ticket_por_numero(numero: str) -> bool:
    try:
        sheet = _obtener_hoja()
        registros = sheet.get_all_values()

        for i in range(1, len(registros)):
            fila = registros[i]
            if len(fila) < 6:
                continue

            # Procesar números manteniendo compatibilidad con formato antiguo
            numeros = []
            for n in fila[5].split(","):
                n = n.strip()
                if n:
                    try:
                        num_int = int(n)
                        numeros.append(formato_numero.format(num_int))
                    except ValueError:
                        continue

            if numero in numeros:
                if len(numeros) == 1:
                    sheet.delete_rows(i + 1)
                    logger.info(f"Fila {i+1} eliminada (número único: {numero})")
                else:
                    nuevos_numeros = [n for n in numeros if n != numero]
                    sheet.update_cell(i + 1, 6, ", ".join(nuevos_numeros))
                    logger.info(f"Número {numero} eliminado de fila {i+1}")
                return True

        logger.warning(f"Número {numero} no encontrado para eliminar en Sheets.")
        return False
    except Exception as e:
        logger.error(f"Error al eliminar número {numero} de Sheets: {str(e)}")
        return False

def subir_a_drive(nombre_archivo: str, bytes_imagen: bytes, folder_id: str) -> str:
    try:
        creds = Credentials.from_service_account_file(CREDENCIALES_JSON, scopes=SCOPE)
        drive_service = build("drive", "v3", credentials=creds)

        media = MediaIoBaseUpload(io.BytesIO(bytes_imagen), mimetype="image/jpeg")
        file_metadata = {
            "name": nombre_archivo,
            "parents": [folder_id]
        }

        archivo = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()

        drive_service.permissions().create(
            fileId=archivo["id"],
            body={"role": "reader", "type": "anyone"},
        ).execute()

        enlace = f"https://drive.google.com/uc?id={archivo['id']}&export=download"
        return enlace
    except Exception as e:
        logger.error(f"Error al subir imagen a Drive: {str(e)}")
        return ""

def actualizar_imagen_ticket(ticket_id, imagen_url):
    try:
        sheet = _obtener_hoja()
        filas = sheet.get_all_values()
        for i, fila in enumerate(filas):
            if len(fila) > 0 and fila[0].strip() == ticket_id.strip():
                sheet.update_cell(i + 1, 11, imagen_url)
                return True
        logger.warning(f"No se encontró el ticket {ticket_id} para actualizar imagen.")
        return False
    except Exception as e:
        logger.error(f"Error al actualizar imagen en ticket {ticket_id}: {str(e)}")
        return False





def asignar_numeros_aleatorios_disponibles(cantidad: int, digitos: int, ocupados: list[str]) -> list[str]:
    if digitos < 1 or digitos > 4:
        raise ValueError("Los dígitos deben estar entre 1 y 4")

    total_posibles = 10 ** digitos
    formato = f"{{:0{digitos}d}}"

    todos = set(formato.format(i) for i in range(total_posibles))
    ocupados_set = set(str(n).zfill(digitos) for n in ocupados)
    disponibles = list(todos - ocupados_set)

    if len(disponibles) < cantidad:
        raise ValueError("No hay suficientes números disponibles")

    return random.sample(disponibles, cantidad)


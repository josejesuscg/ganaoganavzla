import uuid
import logging
import random 
import respaldo
import re
#from respaldo import respaldar_ticket, actualizar_estado_ticket
from respaldo import borrar_registros_sheets
from respaldo import cargar_tickets_desde_sheets
#from respaldo import eliminar_ticket_por_numero
from respaldo import set_formato_numero
from respaldo import subir_a_drive, actualizar_imagen_ticket
from datetime import datetime
from functools import wraps
from telegram.ext import Application
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      BotCommand, BotCommandScopeDefault, BotCommandScopeChat)
from telegram.ext import (ApplicationBuilder, CommandHandler,
                          CallbackQueryHandler, MessageHandler, filters,
                          ContextTypes)
from telegram.helpers import escape_markdown
from telegram.ext import MessageHandler, filters

import os
import uuid
import asyncio
import logging

# importa nuestro nuevo módulo de BD y sincronizador
import db
import syncer
import uuid
import asyncio



try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def inicializar_bd_al_arranque():
    """
    Se ejecuta una vez al iniciar el bot.
    - Crea tablas en la BD si no existen.
    (Opcional) Podrías poblar en memoria los números ocupados desde la BD.
    """
    try:
        db.init_db()
        logger.info("BD inicializada correctamente.")
    except Exception as e:
        logger.exception(f"Error inicializando la BD: {e}")


# ——————————————————————————————————————————————————————————————————————————————
# 1) LOGGING
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)

#TOKEN = "8119337796:AAHGQ8Qa2mdlhokn01FHyL0p3wqOj_rmoiU"
#ADMIN_ID = "7899842142"



TOKEN = os.getenv("TOKEN")            # quitar el hardcode
ADMIN_ID = os.getenv("ADMIN_ID")      # str
CANAL_COMPROBANTES = os.getenv("CANAL_COMPROBANTES", "-1002753190289")  

# ——————————————————————————————————————————————————————————————————————————————
# 2) VALIDACIONES
def nombre_valido(texto: str) -> bool:
    # Solo letras (con acentos), espacios y longitud entre 2 y 100
    return bool(re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñ ]{2,100}", texto))


def telefono_valido(texto: str) -> bool:
    # Debe empezar con dígito o '+', luego dígitos, espacios o guiones, entre 7 y 20 caracteres
    return bool(re.fullmatch(r"[\+0-9][0-9 \-]{6,20}", texto))


def cedula_valida(texto: str) -> bool:
    # Letras, dígitos, puntos o guiones, entre 5 y 20 caracteres
    return bool(re.fullmatch(r"[A-Za-z0-9\.\-]{5,20}", texto))


def hash_valido(texto: str) -> bool:
    # Alfanumérico, guiones o guiones bajos, entre 8 y 200 caracteres
    return bool(re.fullmatch(r"[\w\-]{8,200}", texto))


# ——————————————————————————————————————————————————————————————————————————————
# 3) SISTEMA DE RIFAS
class SistemaRifas:

    def __init__(self):
        self.reset_completo()

    def reset_completo(self):
        self.user_datos = {}
        self.esperando_dato = {}
        self.esperando_hash = {}
        self.esperando_confirmacion = {}
        self.tickets_verificados = {}
        self.esperando_imagen = {}
        self.precio_global = 1.0
        self.activo = False  # Inactivo hasta configuración
        self.min_num = 0
        self.max_num = 99
        self.digitos = 2
        self.formato_numero = "{:02d}"
        self.numeros_disponibles = {}
      #  self.numero_valido = lambda x: False

    def configurar_rango_inicial(self, rango: str):
        self.min_num, self.max_num, self.digitos = self._parsear_rango(rango)
        self.inicializar_numeros_disponibles()
        self.activo = True
        logger.info(f"Sistema activado con rango: {rango}")


    def _parsear_rango(self, rango: str):
        if rango == "00-99":
            return 0, 99, 2
        elif rango == "000-999":
            return 0, 999, 3
        elif rango == "0000-9999":
            return 0, 9999, 4
        else:
            raise ValueError("Rango inválido. Usa 00-99, 000-999 o 0000-9999")



    def inicializar_numeros_disponibles(self):
        self.formato_numero = f"{{:0{self.digitos}d}}"
        self.numeros_disponibles = {
            self.formato_numero.format(i): True
            for i in range(self.min_num, self.max_num + 1)
        }
        self.numero_valido = lambda x: (
            x.isdigit() and len(x) == self.digitos and self.min_num <= int(x) <= self.max_num
        )
        logger.info("Inicializados números disponibles tras configuración manual.")



    def set_rango_numeros(self, rango: str):
        """Configura el rango de números (00-99, 000-999, 0000-9999)"""
        if rango == "00-99":
            self.min_num = 0
            self.max_num = 99
            self.digitos = 2
        elif rango == "000-999":
            self.min_num = 0
            self.max_num = 999
            self.digitos = 3
        elif rango == "0000-9999":
            self.min_num = 0
            self.max_num = 9999
            self.digitos = 4
        else:
            raise ValueError("Rango no válido. Usa: 00-99, 000-999 o 0000-9999")

        # Asegurar que el formato se actualice correctamente
        self.formato_numero = f"{{:0{self.digitos}d}}"

        # Generar lista de números disponibles
        self.numeros_disponibles = {
            self.formato_numero.format(i): True
            for i in range(self.min_num, self.max_num + 1)
        }

        logger.info(
            f"Rango configurado: {self.formato_numero.format(self.min_num)}-{self.formato_numero.format(self.max_num)}"
        )

        # Validador actualizado para que funcione con los botones
        self.numero_valido = lambda x: (
            isinstance(x, str)
            and x.isdigit()
            and len(x) == self.digitos
            and self.formato_numero.format(int(x)) == x
            and self.min_num <= int(x) <= self.max_num
        )

    def obtener_estado(self):
        return {
            'total': 100,
            'disponibles': sum(self.numeros_disponibles.values()),
            'ocupados': 100 - sum(self.numeros_disponibles.values()),
            'usuarios': len(self.user_datos),
            'tickets': len(self.tickets_verificados),
        }


sistema = SistemaRifas()


# ——————————————————————————————————————————————————————————————————————————————
def inicializar_tickets_desde_sheets():
    try:
        datos = cargar_tickets_desde_sheets()

        if not datos["existen_datos"]:
            sistema.activo = False
            if datos["digitos_detectados"] is None:
                logger.info("Sheets está vacío, requiriendo configuración manual")
            else:
                logger.info("No se encontraron números válidos en Sheets")
            return False

        digitos = datos["digitos_detectados"]
        if digitos == 2:
            rango = "00-99"
        elif digitos == 3:
            rango = "000-999"
        elif digitos == 4:
            rango = "0000-9999"
        else:
            raise ValueError(f"Formato numérico no soportado: {digitos} dígitos")

        sistema.configurar_rango_inicial(rango)
        logger.info(f"Rango configurado automáticamente a {rango}")

        sistema.tickets_verificados.clear()
        sistema.esperando_hash.clear()
        sistema.user_datos.clear()
        sistema.numeros_disponibles = {
            sistema.formato_numero.format(i): True 
            for i in range(sistema.min_num, sistema.max_num + 1)
        }

        for tid, datos_ticket in datos["verificados"].items():
            sistema.tickets_verificados[tid] = datos_ticket
            for n in datos_ticket["numeros"]:
                if len(n) == sistema.digitos and n.isdigit():
                    sistema.numeros_disponibles[n] = False
                else:
                    logger.warning(f"Número {n} no coincide con el formato actual (Ticket {tid})")

        # Cargar tickets pendientes usando TICKET_ID como llave única
        for pendiente in datos["pendientes"]:
            ticket_id = pendiente["ticket_id"]
            sistema.esperando_hash[ticket_id] = pendiente

            sistema.user_datos[pendiente["user_id"]] = {
                "numeros": pendiente["numeros"],
                "nombre": pendiente["nombre"],
                "telefono": pendiente["telefono"],
                "cedula": pendiente["cedula"]
            }
            for n in pendiente["numeros"]:
                if len(n) == sistema.digitos and n.isdigit():
                    sistema.numeros_disponibles[n] = False
                else:
                    logger.warning(f"Número {n} no coincide con el formato actual (Ticket pendiente {ticket_id})")

        logger.info(f"Tickets cargados: {len(sistema.tickets_verificados)} verificados, {len(sistema.esperando_hash)} pendientes")
        return True

    except ValueError as e:
        logger.error(f"Error de configuración: {str(e)}")
        sistema.activo = False
        return False
    except Exception as e:
        logger.error(f"Error crítico al inicializar desde Sheets: {str(e)}")
        sistema.activo = False
        return False


#---------------------------------------------

# RESTAURAR DATOS DESDE GOOGLE SHEETS
# datos_recuperados = cargar_tickets_desde_sheets()

# Restaurar tickets verificados
#sistema.tickets_verificados.update(datos_recuperados["verificados"])
#for data in datos_recuperados["verificados"].values():
#    for n in data["numeros"]:
        # Convertir a string y rellenar con ceros según el rango actual
#        n_str = sistema.formato_numero.format(int(n))
#        sistema.numeros_disponibles[n_str] = False
#        print(f"🔒 Número verificado ocupado desde Sheets: {n_str}")

# Restaurar tickets pendientes y bloquear números
#for ticket in datos_recuperados["pendientes"]:
#    ticket["numeros"] = [
#        sistema.formato_numero.format(int(n)) for n in ticket["numeros"]
#    ]

#    sistema.esperando_hash[ticket["hash"]] = ticket
#    sistema.user_datos[ticket["user_id"]] = {
#        "numeros": ticket["numeros"],
#        "nombre": ticket["nombre"],
#        "telefono": ticket["telefono"],
#        "cedula": ticket["cedula"]
#    }
#    for n_str in ticket["numeros"]:
#        sistema.numeros_disponibles[n_str] = False
#        print(f"🔒 Número pendiente ocupado desde Sheets: {n_str}")

# ——————————————————————————————————————————————————————————————————————————————
async def reenviar_pendientes_al_inicio(context: ContextTypes.DEFAULT_TYPE):
    if not sistema.esperando_hash:
        logger.info("No hay tickets pendientes para reenviar al inicio.")
        return

    logger.info(f"Reenviando {len(sistema.esperando_hash)} tickets pendientes al administrador...")

    # .values() para iterar sobre los diccionarios de tickets
    for ticket in sistema.esperando_hash.values():
        ticket_id = ticket.get("ticket_id", "¿Sin ID?")
        nombre = str(ticket.get("nombre", "Desconocido"))
        telefono = str(ticket.get("telefono", "No disponible"))
        cedula = str(ticket.get("cedula", "No disponible"))
        user_id = str(ticket.get("user_id", "0"))
        username = ticket.get("username")
        numeros = ticket.get("numeros", [])
        imagen_file_id = ticket.get("imagen_file_id")

        if username:
            user_disp = escape_markdown(f"@{username}", version=1)
        else:
            nombre_esc_link = escape_markdown(nombre, version=1)
            user_disp = f"[{nombre_esc_link}](tg://user?id={user_id})"

        numeros_str = [str(n) for n in numeros]
        numeros_seg = escape_markdown(", ".join(numeros_str), version=1)
        nombre_seg = escape_markdown(nombre, version=1)
        tel_seg = escape_markdown(telefono, version=1)
        cedula_seg = escape_markdown(cedula, version=1)
        ticket_id_seg = escape_markdown(ticket_id, version=1)

        # La corrección clave es usar el ticket_id único en el callback_data
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Verificar", callback_data=f"verificado|{ticket_id}"),
            InlineKeyboardButton("❌ Rechazar", callback_data=f"noverificado|{ticket_id}")
        ]])

        texto_admin = (
            "🔁 *TICKET RECUPERADO (Reinicio)*\n\n"
            f"🎫 *Ticket:* `{ticket_id_seg}`\n"
            f"👤 *Usuario:* {user_disp}\n"
            f"🧾 *Nombre:* {nombre_seg}\n"
            f"📞 *Teléfono:* {tel_seg}\n"
            f"🪪 *Cédula:* {cedula_seg}\n"
            f"🔢 *Números:* {numeros_seg}\n\n"
            "⚠️ Este ticket estaba pendiente antes del reinicio."
        )

        try:
            if imagen_file_id:
                await context.bot.send_photo(
                    chat_id=int(ADMIN_ID),
                    photo=imagen_file_id,
                    caption=texto_admin,
                    parse_mode="Markdown",
                    reply_markup=kb
                )
            else:
                await context.bot.send_message(
                    chat_id=int(ADMIN_ID),
                    text=texto_admin,
                    parse_mode="Markdown",
                    reply_markup=kb
                )
        except Exception as e:
            logger.error(f"No se pudo reenviar el ticket pendiente {ticket_id}: {e}")

def requiere_activado(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id if update.message else update.callback_query.from_user.id
        command = update.message.text.split()[0] if update.message and update.message.text else ""

        print(f"🧪 Decorador revisando comando: {command} | sistema.activo = {sistema.activo}")

        if not sistema.activo and str(user_id) == ADMIN_ID and command.startswith("/rango"):
            return await func(update, context)

        if not sistema.activo:
            print("⛔ Comando bloqueado porque el sistema no está activo")
            if update.callback_query:
                await update.callback_query.answer("Bot en configuración...", show_alert=True)
            elif update.message:
                await update.message.reply_text("Bot en configuración. Intente más tarde.")
            return

        return await func(update, context)
    return wrapper

# ——————————————————————————————————————————


async def post_init(application: Application):
    await set_commands(application)

    try:
        # Intenta configuración automática desde Sheets
        if inicializar_tickets_desde_sheets():
            sistema.activo = True
            mensaje = (
                "✅ *Bot configurado automáticamente*\n\n"
                f"🔢 *Rango detectado:* {sistema.formato_numero.format(sistema.min_num)}-{sistema.formato_numero.format(sistema.max_num)}\n"
                f"📝 *Tickets cargados:*\n"
                f"  - Verificados: {len(sistema.tickets_verificados)}\n"
                f"  - Pendientes: {len(sistema.esperando_hash)}\n\n"
                "Los números se mantuvieron exactamente como estaban en Google Sheets."
            )

            if sistema.esperando_hash:
                mensaje += "\n\n⚠️ *Hay tickets pendientes de verificación*"

            await application.bot.send_message(
                chat_id=int(ADMIN_ID),
                text=mensaje,
                parse_mode="Markdown"
            )

            # Reenviar pendientes al admin si los hay
            if sistema.esperando_hash:
                await reenviar_pendientes_al_inicio(application)
        else:
            await application.bot.send_message(
                chat_id=int(ADMIN_ID),
                text="🔧 *Configuración manual requerida*\n\n"
                     "No se encontraron datos en Sheets o hubo un error al cargarlos.\n\n"
                     "Por favor configura el rango manualmente con:\n"
                     "• `/rango 00-99`\n"
                     "• `/rango 000-999`\n"
                     "• `/rango 0000-9999`\n\n"
                     "Los números se conservarán exactamente como los ingreses.",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error en post_init: {str(e)}")
        await application.bot.send_message(
            chat_id=int(ADMIN_ID),
            text="❌ *Error en la inicialización*\n\n"
                 f"Error: {str(e)}\n\n"
                 "Por favor verifica:\n"
                 "1. La conexión con Google Sheets\n"
                 "2. El formato de los datos\n"
                 "3. Configura el rango manualmente si es necesario\n\n"
                 "Los números se mantendrán exactamente como están en Sheets.",
            parse_mode="Markdown"
        )
# ——————————————————————————————————————————————————————————————————————————————


@requiere_activado
async def configurar_rango(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if str(uid) != ADMIN_ID:
        return await update.message.reply_text("❌ No autorizado.")

    # Permitimos configurar el rango si el sistema está inactivo.
    if sistema.activo:
        return await update.message.reply_text(
            "⚠️ El sistema ya está configurado y activo. Usa /reset primero si deseas empezar de cero."
        )

    if not context.args:
        return await update.message.reply_text(
            "📊 *Configuración de Rango Inicial*\n\n"
            "Debes establecer el rango de números válidos antes de comenzar.\n\n"
            "✅ Formatos permitidos:\n"
            "• `00-99`\n"
            "• `000-999`\n"
            "• `0000-9999`\n\n"
            "📌 Ejemplo de uso: `/rango 000-999`",
            parse_mode="Markdown"
        )

    try:
        rango = context.args[0]
        sistema.configurar_rango_inicial(rango) # Esto ya establece sistema.activo = True

        # Sincronizamos el formato con el módulo de respaldo
        set_formato_numero(sistema.digitos)

        await update.message.reply_text(
            f"✅ Sistema activado con el rango: *{rango}*.\n"
            "El bot ya está operativo.",
            parse_mode="Markdown"
        )
        logger.info(f"Sistema activado manualmente con rango {rango}.")

    except ValueError as e:
        return await update.message.reply_text(
            f"❌ {str(e)}\n\n"
            "Formatos válidos: 00-99, 000-999, 0000-9999"
        )
def actualizar_numeros_existentes():
    """Actualiza el formato de números en todos los tickets existentes"""
    # Para tickets verificados
    for ticket in sistema.tickets_verificados.values():
        ticket["numeros"] = [
            sistema.formato_numero.format(int(n)) for n in ticket["numeros"]
        ]

    # Para tickets pendientes
    for pendiente in sistema.esperando_hash.values():
        pendiente["numeros"] = [
            sistema.formato_numero.format(int(n)) for n in pendiente["numeros"]
        ]

    # Para selecciones en curso
    for user_data in sistema.user_datos.values():
        if "numeros" in user_data:
            user_data["numeros"] = [
                sistema.formato_numero.format(int(n))
                for n in user_data["numeros"]
            ]


# ——————————————————————————————————————————————————————————————————————————————
async def enviar_teclado_numeros(send_func, user_id: int, page: int = 0):
    try:
        total_numeros = sistema.max_num - sistema.min_num + 1
        PAGE_SIZE = min(20, total_numeros)
        numeros_por_fila = 5 if sistema.digitos <= 2 else 4

        # Obtener selección actual del usuario
        sel = sistema.user_datos.get(user_id, {}).get("numeros", [])
        start = sistema.min_num + page * PAGE_SIZE
        end = min(start + PAGE_SIZE, sistema.max_num + 1)

        keyboard = []
        current_row = []

        for i in range(start, end):
            num = sistema.formato_numero.format(i)

            # Verificar estado del número
            if num in sel:
                text = f"✅{num}"  # Seleccionado por el usuario
            elif num in sistema.numeros_disponibles and sistema.numeros_disponibles[num]:
                text = num  # Disponible
            else:
                text = "❌"  # Ocupado

            current_row.append(InlineKeyboardButton(text, callback_data=num))

            if len(current_row) >= numeros_por_fila:
                keyboard.append(current_row)
                current_row = []

        if current_row:
            keyboard.append(current_row)

        # Botón de confirmación
        keyboard.append([InlineKeyboardButton("✅ Confirmar", callback_data="confirmar")])

        # Navegación entre páginas
        total_pages = (total_numeros + PAGE_SIZE - 1) // PAGE_SIZE
        nav = [
            InlineKeyboardButton("⏮", callback_data=f"page_{page-1}") if page > 0 
            else InlineKeyboardButton(" ", callback_data="noop"),
            InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"),
            InlineKeyboardButton("⏭", callback_data=f"page_{page+1}") if page < total_pages - 1 
            else InlineKeyboardButton(" ", callback_data="noop"),
        ]
        keyboard.append(nav)

        # Preparar mensaje
        total = len(sel)
        mensaje = (
            f"🎰 *SELECCIONA TUS NÚMEROS* 🎰\n\n"
            f"🔢 Elige {sistema.formato_numero.format(sistema.min_num)}–{sistema.formato_numero.format(sistema.max_num)}:\n"
            "✅ = seleccionado   ❌ = no disponible\n\n"
            f"📌 *Números seleccionados:* {', '.join(sel) if sel else 'Ninguno'}\n"
            f"💰 *Total a pagar:* {total * sistema.precio_global} USD\n\n"
            "🛑 Envía `Listo` para continuar o presiona `Confirmar✅`.")

        await send_func(
            text=mensaje,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error en enviar_teclado_numeros: {str(e)}")
        await send_func(
            text="❌ Error al cargar los números. Por favor intenta nuevamente.",
            parse_mode="Markdown"
        )


# 6) CALLBACK: selección & paginación
@requiere_activado
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""

    uid = q.from_user.id

    if data.startswith("page_"):
        page = int(data.split("_")[1])
        context.user_data["current_page"] = page
        return await enviar_teclado_numeros(q.edit_message_text, uid, page)

    if data == "confirmar":
        nums = sistema.user_datos.get(uid, {}).get("numeros", [])
        if not nums:
            return await q.answer("❗ Selecciona al menos un número.", show_alert=True)
        await q.edit_message_text(
            f"✅ Has elegido: {', '.join(nums)}\n\n📥 Excelente elección. Para formalizar su participación, ingrese su nombre completo:\n\n",
            parse_mode="Markdown"
        )
        sistema.esperando_dato[uid] = "nombre"
        sistema.esperando_confirmacion[uid] = False
        return

    # ⚠️ Corrección aquí: validación más segura del número
    if data.isdigit() and len(data) == sistema.digitos:
        if not sistema.numero_valido(data):
            return await q.answer("❌ Número fuera de rango.", show_alert=True)

        sistema.user_datos.setdefault(uid, {"numeros": []})
        nums = sistema.user_datos[uid]["numeros"]
        if data in nums:
            nums.remove(data)
            sistema.numeros_disponibles[data] = True
        elif sistema.numeros_disponibles.get(data, False):
            nums.append(data)
            sistema.numeros_disponibles[data] = False
        else:
            return await q.answer("❌ No disponible", show_alert=True)

        page = context.user_data.get("current_page", 0)
        return await enviar_teclado_numeros(q.edit_message_text, uid, page)

    if data == "noop":
        return


# ——————————————————————————————————————————————————————————————————————————————
# 7) COMANDOS BÁSICOS

async def handle_random_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    try:
        _, cantidad_str = q.data.split("|")
        cantidad = int(cantidad_str)

        disponibles = [num for num, esta_libre in sistema.numeros_disponibles.items() if esta_libre]

        if len(disponibles) < cantidad:
            await q.edit_message_text(
                "😟 *¡Lo sentimos!* No quedan suficientes números disponibles para la cantidad que solicitaste.\n\n"
                "Por favor, intenta con una cantidad menor o contacta al administrador."
            )
            return

        numeros_elegidos = random.sample(disponibles, cantidad)
        numeros_elegidos.sort()

        sistema.user_datos.setdefault(uid, {"numeros": []})
        sistema.user_datos[uid]["numeros"] = numeros_elegidos
        for num in numeros_elegidos:
            sistema.numeros_disponibles[num] = False

        await q.edit_message_text(
            f"✅ ¡Perfecto! El sistema ha elegido aleatoriamente los siguientes números para ti:\n\n"
            f"🔢 *Tus números:* `{', '.join(numeros_elegidos)}`\n\n"
            "📥 Para continuar, por favor *envía tu nombre completo*.",
            parse_mode="Markdown"
        )
        sistema.esperando_dato[uid] = "nombre"
        sistema.esperando_confirmacion[uid] = False

    except (ValueError, IndexError) as e:
        logger.error(f"Error en handle_random_selection: {e}")
        await q.edit_message_text("❌ Ha ocurrido un error al procesar tu solicitud. Por favor, intenta de nuevo con /numeros.")





@requiere_activado
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🎉 *¡Bienvenido al Bot Oficial de Rifas!*\n\n"
        "¡Hola! Podrás reservar tus números favoritos "
        "y participar en emocionantes sorteos.\n\n"
        "✨ *Instrucción rápida:*\n\n"
        "Escribe el comando en el chat o presiona aquí ➡️ /numeros para elegir tus números de la suerte.\n\n"
        "🏆 ¡Mucha suerte en el sorteo!")
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


@requiere_activado
async def mostrar_numeros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Comando /numeros recibido de usuario {update.effective_user.id}")
    uid = update.effective_user.id

    if sistema.esperando_dato.get(uid):
        campo = sistema.esperando_dato[uid]
        await update.message.reply_text(
            f"❗ Aún debes proporcionar tu {campo}. Termina el proceso actual antes de usar /numeros de nuevo."
        )
        return

    # Limpiar datos previos para una nueva selección
    sistema.user_datos[uid] = {"numeros": []}
    sistema.esperando_confirmacion[uid] = True
    context.user_data["current_page"] = 0

    # ---- LÓGICA CONDICIONAL ----
    # Si la rifa es de 10,000 números (4 dígitos), mostramos el menú de selección aleatoria.
    if sistema.digitos == 4:
        texto = (
            "🎉 *¡Rifa Especial de 10,000 Números!* 🎉\n\n"
            "Debido a la gran cantidad de números, la selección es automática y aleatoria para darte la mejor experiencia.\n\n"
            "👇 *Por favor, elige cuántos números quieres comprar:* 👇"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Comprar 2 números", callback_data="random_select|2"),
                InlineKeyboardButton("Comprar 4 números", callback_data="random_select|4")
            ],
            [
                InlineKeyboardButton("Comprar 6 números", callback_data="random_select|6"),
                InlineKeyboardButton("Comprar 8 números", callback_data="random_select|8")
            ],
            [InlineKeyboardButton("Comprar 10 números", callback_data="random_select|10")]
        ])
        await update.message.reply_text(texto, reply_markup=keyboard, parse_mode="Markdown")
    else:
        # Para rifas de 2 o 3 dígitos, mostramos la cuadrícula tradicional.
        await enviar_teclado_numeros(update.message.reply_text, uid, page=0)
# ——————————————————————————————————————————————————————————————————————————————
# 8) “APAGAR” y “ENCENDER” (solo admin)
async def apagar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if str(uid) != ADMIN_ID:
        return await update.message.reply_text("❌ No autorizado.")
    sistema.activo = False
    await update.message.reply_text("⏸️ El bot ha sido *pausado*.",
                                    parse_mode="Markdown")


async def encender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if str(uid) != ADMIN_ID:
        return await update.message.reply_text("❌ No autorizado.")
    sistema.activo = True
    await update.message.reply_text("▶️ El bot ha sido *reactivado*.",
                                    parse_mode="Markdown")


# ——————————————————————————————————————————————————————————————————————————————
# 9) RESET SISTEMA y ESTADO


@requiere_activado
async def reset_sistema(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if str(uid) != ADMIN_ID:
        return await update.message.reply_text("❌ No autorizado.")

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Sí, reiniciar AHORA", callback_data="confirmar_reset"),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_reset")
    ]])
    await update.message.reply_text(
        "⚠️ *¡Atención!* Esta acción borrará TODOS los tickets de Google Sheets y reiniciará el bot a su estado inicial.\n\n"
        "¿Estás seguro de que quieres continuar?",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@requiere_activado
async def handle_reset_confirmation(update: Update,
                                    context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if str(q.from_user.id) != ADMIN_ID:
        return await q.edit_message_text("❌ No autorizado.")

    if q.data == "confirmar_reset":
        try:
            # Borra los datos de Google Sheets
            borrar_registros_sheets()
            # Resetea el estado en memoria, incluyendo sistema.activo = False
            sistema.reset_completo()

            await q.edit_message_text(
                "🔄 *Sistema Reiniciado Exitosamente.*\n\n"
                "Todos los datos han sido borrados. El bot está ahora inactivo.\n\n"
                "Para reactivarlo, configura un nuevo rango con el comando `/rango`.\n"
                "Ejemplo: `/rango 00-99`",
                parse_mode="Markdown"
            )
            logger.info("El sistema ha sido reseteado por el administrador.")
        except Exception as e:
            await q.edit_message_text(f"❌ Ocurrió un error durante el reseteo: {e}")
            logger.error(f"Fallo en el reseteo: {e}")
    else:
        await q.edit_message_text("❌ Reseteo cancelado.")
# ——————————————————————————————————————————————————————————————————————————————
# 10) VERIFICAR ESTADO (solo admin)
@requiere_activado
async def verificar_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if str(uid) != ADMIN_ID:
        return await update.message.reply_text("❌ No autorizado.")
    e = sistema.obtener_estado()
    await update.message.reply_text(
        f"📊 Estado:\n"
        f"• Disponibles: {e['disponibles']}\n"
        f"• Ocupados:    {e['ocupados']}\n"
        f"• Usuarios:    {e['usuarios']}\n"
        f"• Tickets:     {e['tickets']}",
        parse_mode="Markdown")


# —————————————————————————————————————————————————————————————————————————


@requiere_activado
async def liberar_numero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin: /liberar 05
    - Libera el número en memoria
    - Lo elimina/ajusta en BD
    - Espeja toda la BD hacia Sheets para asegurar consistencia
    """
    user_id = update.effective_user.id
    if str(user_id) != str(ADMIN_ID):
        return await update.message.reply_text("❌ No tienes permisos para usar este comando.")

    if not context.args:
        return await update.message.reply_text("Uso: /liberar <número>")

    objetivo = context.args[0].strip()
    if not objetivo.isdigit():
        return await update.message.reply_text("❗ Debes indicar un número válido (ej. 05).")

    # 1) Memoria
    if objetivo in sistema.ocupados:
        sistema.ocupados.remove(objetivo)
    if objetivo not in sistema.disponibles:
        sistema.disponibles.append(objetivo)

    # 2) BD
    ok_db = False
    try:
        ok_db = db.eliminar_numero_db(objetivo)
    except Exception as e:
        logger.error(f"Error liberando número en BD: {e}")

    # 3) Espejo
    try:
        tickets = db.fetch_all_tickets()
        syncer.sync_full_dump(tickets)
    except Exception as e:
        logger.warning(f"No se pudo sincronizar full dump a Sheets: {e}")

    if ok_db:
        return await update.message.reply_text(f"✅ Número {objetivo} liberado y sincronizado.")
    else:
        return await update.message.reply_text(f"ℹ️ Número {objetivo} marcado como libre en memoria. (No se encontró en BD)")

#—————————————————————————————————————————————————————————————————————————


# 11) PRECIO (solo admin)
@requiere_activado
async def cambiar_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if str(uid) != ADMIN_ID:
        return await update.message.reply_text("❌ No autorizado.")
    if context.args:
        try:
            nuevo = float(context.args[0])
        except ValueError:
            return await update.message.reply_text("❗ Precio inválido.")
        sistema.precio_global = nuevo
        return await update.message.reply_text(
            f"✅ Precio ajustado a {sistema.precio_global} USD.")
    return await update.message.reply_text(
        f"💲 Precio actual: {sistema.precio_global} USD.")


# ——————————————————————————————————————————————————————————————————————————————
# 12) FLUJO DE DATOS y HASH
@requiere_activado
async def confirmar_seleccion_manual(update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    nums = sistema.user_datos.get(uid, {}).get("numeros", [])
    if not nums:
        return await update.message.reply_text("❗ Usa /numeros antes.")
    await update.message.reply_text(
        f"✅ Elegidos: {', '.join(nums)}\n📥 Envía tu nombre completo.",
        parse_mode="Markdown")
    sistema.esperando_dato[uid] = "nombre"


@requiere_activado
async def manejar_mensajes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, txt = update.effective_user.id, update.message.text.strip()
    if sistema.esperando_confirmacion.get(uid) and txt.lower() == "listo":
        return await confirmar_seleccion_manual(update, context)
    campo = sistema.esperando_dato.get(uid)
    if campo:
        return await recolectar_datos(update, context)
    if any(rec["user_id"] == uid for rec in sistema.esperando_hash.values()):
        return
    if sistema.user_datos.get(uid, {}).get("numeros"):
        return await recibir_hash(update, context)


@requiere_activado
async def recolectar_datos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    txt = update.message.text.strip()
    campo = sistema.esperando_dato.get(uid)

    if not txt:
        return await update.message.reply_text(
            "❗ El campo no puede estar vacío.")

    if campo == "nombre":
        txt = re.sub(r"\s+", " ", txt)  # limpiar múltiples espacios
        if not nombre_valido(txt):
            return await update.message.reply_text(
                "❗ Nombre inválido. Solo letras y espacios.")
        sistema.user_datos[uid]["nombre"] = txt
        sistema.esperando_dato[uid] = "telefono"
        return await update.message.reply_text(
            "📞 Información de contacto\n\nEste dato será utilizado exclusivamente para notificaciones sobre la rifa.\n\n Ingrese su número con código país (ej: +58 416 123 4567):")

    if campo == "telefono":
        txt = re.sub(r"\s+", " ", txt)
        if not telefono_valido(txt):
            return await update.message.reply_text(
                "❗ Teléfono inválido. Ejemplo: +57 300 123 4567")
        sistema.user_datos[uid]["telefono"] = txt
        sistema.esperando_dato[uid] = "cedula"
        return await update.message.reply_text(
            "🪪 Verificación de identidad\n\nProporcione su número de cédula/DNI para validación oficial (solo caracteres alfanuméricos, puntos y guiones):"
        )

    if campo == "cedula":
        txt = txt.replace(" ", "")
        if not cedula_valida(txt):
            return await update.message.reply_text(
                "❗ Cédula o DNI inválida. Solo letras, números, puntos o guiones.")
        sistema.user_datos[uid]["cedula"] = txt
        sistema.esperando_dato[uid] = None


        # Calcular el monto total basado en la cantidad de números seleccionados
        datos_usuario = sistema.user_datos.get(uid, {})
        numeros_seleccionados = datos_usuario.get("numeros", [])
        cantidad_numeros = len(numeros_seleccionados)
        monto_total = cantidad_numeros * sistema.precio_global

        
        # Mostrar instrucciones para el pago y solicitar imagen
        mensaje = (
            "📌 *INSTRUCCIONES DE PAGO* 📌\n\n"
           
            "Para realizar su pago en USDT mediante BINANCE* .\n\n"
            "✅ *PASOS A SEGUIR* ✅\n"
            f"Has seleccionado *{cantidad_numeros} número(s)*.\n\n"
            "1️⃣ Abra su aplicación de Binance y seleccione *Enviar a otro usuario Binance*.\n\n"
            "2️⃣ En lugar de correo electrónico, ingrese el *ID único* que identificará nuestra cuenta.\n\n"
            f"3️⃣ Introduzca el monto exacto de su transacción en USDT*.\n\n"
            "4️⃣ Confirme y realice la transferencia.\n\n"
            "5️⃣ Tome una foto clara o captura de pantalla de su comprobante.\n\n"
            "6️⃣ Envíe la imagen en este chat para validar su pago.\n\n"
            "💳 *DATOS DE PAGO PARA USUARIOS BINANCE* 💳\n"           
            f"💰 *Monto a pagar: {monto_total:.2f} USD* 💰\n\n"
            "🏦 *ID de Binance Pay:* `196461315`\n\n"
            "📌 *Nota:* Mantenga presionado el número del ID para copiarlo fácilmente en su teléfono.\n\n"
            "⚠️ *IMPORTANTE* ⚠️\n"
            "• Verifique que el ID sea correcto antes de enviar.\n"
            "• Asegúrese de que el comprobante sea legible.\n\n"
            "✨ Gracias por su confianza. Su pago será verificado y confirmado a la brevedad."
        )

        await update.message.reply_text(mensaje, parse_mode="Markdown")


@requiere_activado
async def manejar_imagen_comprobante(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    datos_usuario = sistema.user_datos.get(uid)

    # Validaciones básicas
    if not datos_usuario or "numeros" not in datos_usuario or not datos_usuario["numeros"]:
        return await update.message.reply_text("❗ Primero elige tus números con /numeros antes de enviar el comprobante.")

    nombre = (datos_usuario.get("nombre") or "").strip()
    telefono = (datos_usuario.get("telefono") or "").strip()
    cedula = (datos_usuario.get("cedula") or "").strip()

    if not nombre_valido(nombre):
        return await update.message.reply_text("❗ Nombre inválido. Solo letras y espacios.")
    if not telefono_valido(telefono):
        return await update.message.reply_text("❗ Teléfono inválido. Ejemplo: +57 300 123 4567")
    if not cedula_valida(cedula):
        return await update.message.reply_text("❗ Cédula inválida. Solo letras, números, puntos o guiones.")
    if not update.message.photo:
        return await update.message.reply_text("❗ Debes enviar una *imagen* del comprobante.", parse_mode="Markdown")

    # Extraer foto
    foto = update.message.photo[-1]
    file_id = foto.file_id

    # Datos del ticket
    ticket_id = "TCK-" + str(uuid.uuid4())[:12].upper()
    numeros = datos_usuario["numeros"]
    precio = float(sistema.precio_global)
    estado_inicial = "Pendiente ⏳"

    # 1) Guardar en BD (fuente de verdad)
    try:
        ok = db.crear_ticket_db(
            ticket_id=ticket_id,
            user_id=uid,
            username=update.effective_user.username or nombre,
            nombre=nombre,
            telefono=telefono,
            cedula=cedula,
            numeros=numeros,
            precio=precio,
            imagen_url="",
            hash_pago="",
            estado=estado_inicial
        )
        if not ok:
            logger.error(f"No se insertó ticket {ticket_id} (posible conflicto en ticket_id).")
            return await update.message.reply_text("⚠️ Hubo un problema guardando tu comprobante. Intenta de nuevo.")
    except Exception as e:
        logger.exception(f"Error guardando ticket en BD: {e}")
        return await update.message.reply_text("❌ Ocurrió un error guardando tu comprobante. Inténtalo de nuevo.")

    # 2) Espejo a Google Sheets
    try:
        syncer.sync_ticket_insert(
            ticket_id=ticket_id,
            username_or_nombre=update.effective_user.username or nombre,
            user_id=uid,
            telefono=telefono,
            cedula=cedula,
            numeros=numeros,
            precio=precio,
            estado=estado_inicial,
            imagen_url="",
            hash_pago=""
        )
    except Exception as e:
        logger.warning(f"No se pudo espejar a Sheets: {e}")

    # 3) Guardar en memoria para flujo de verificación
    sistema.esperando_hash[ticket_id] = {
        "ticket_id": ticket_id,
        "user_id": uid,
        "username": update.effective_user.username,
        "nombre": nombre,
        "telefono": telefono,
        "cedula": cedula,
        "numeros": numeros,
        "precio": precio,
        "file_id": file_id,
    }

    # 4) Enviar al canal de comprobantes
    try:
        CANAL_COMPROBANTES = os.getenv("CANAL_COMPROBANTES")
        caption = (f"📌 *Nuevo comprobante*\n\n"
                   f"🎫 Ticket: `{ticket_id}`\n"
                   f"👤 Usuario: @{update.effective_user.username or nombre}\n"
                   f"🔢 Números: {', '.join(numeros)}")
        await context.bot.send_photo(chat_id=CANAL_COMPROBANTES,
                                     caption=caption,
                                     parse_mode="Markdown",
                                     photo=file_id)
    except Exception as e:
        logger.warning(f"No se pudo enviar al canal: {e}")

    try:
        await notificar_admin(update, context, datos_usuario, ticket_id, file_id)
    except Exception as e:
        logger.error(f"Error notificando admin: {e}")

    return await update.message.reply_text("✅ Hemos recibido tu comprobante. El administrador revisará tu pago y te notificaremos por este medio.")

#---------------------------------------------------------------

async def notificar_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, datos_usuario: dict, ticket_id: str, file_id: str):
    try:
        caption = (
            f"📌 *Nuevo comprobante*\n\n"
            f"🎫 Ticket: `{ticket_id}`\n"
            f"👤 Usuario: @{update.effective_user.username or datos_usuario['nombre']}\n"
            f"🔢 Números: {', '.join(datos_usuario['numeros'])}"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Verificar", callback_data=f"verificar|{ticket_id}"),
                InlineKeyboardButton("❌ Rechazar", callback_data=f"rechazar|{ticket_id}")
            ]
        ])
        await context.bot.send_photo(
            chat_id=int(ADMIN_ID),
            photo=file_id,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error notificando admin: {e}")


#---------------------------------------------------------------
@requiere_activado
async def manejar_verificacion_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    accion, ticket_id = q.data.split("|")
    label = "VERIFICAR" if accion == "verificar" else "RECHAZAR"

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ Sí, {label}", callback_data=f"confirmar_nuevo|{accion}|{ticket_id}"),
        InlineKeyboardButton("❌ Cancelar", callback_data=f"cancelar_nuevo|{accion}|{ticket_id}")
    ]])

    mensaje_confirmacion = f"¿Estás seguro de que deseas *{label}* este pago?\n\nTicket: `{ticket_id}`"

    try:
        await q.edit_message_caption(
            caption=mensaje_confirmacion,
            parse_mode="Markdown",
            reply_markup=kb
        )
    except Exception as e:
        logger.error(f"Error en prompt (nuevo ticket): {e}")
        await q.answer("❌ Error al actualizar el mensaje.", show_alert=True)

#---------------------------------------------------------------
@requiere_activado
async def finalizar_verificacion_nuevo_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    try:
        _, accion, ticket_id = q.data.split("|")
    except Exception:
        return await q.answer("❌ Formato inválido.", show_alert=True)

    pendiente = sistema.esperando_hash.pop(ticket_id, None)
    if not pendiente:
        try:
            await q.edit_message_text("⚠️ Este proceso ya fue atendido o expiró.")
        except Exception:
            pass
        return

    if accion == "verificar":
        nuevo_estado = "Verificado ✅"
        # mantener números ocupados
        for n in pendiente["numeros"]:
            sistema.numeros_disponibles[n] = False
    else:
        nuevo_estado = "Rechazado ❌"
        # liberar números
        for n in pendiente["numeros"]:
            sistema.numeros_disponibles[n] = True

    # 1) Actualizar BD
    try:
        ok_db = db.actualizar_estado_db(ticket_id, nuevo_estado)
        if not ok_db:
            logger.error(f"No se actualizó estado en BD para ticket {ticket_id} (no encontrado).")
    except Exception as e:
        logger.exception(f"Error actualizando estado en BD: {e}")
        ok_db = False

    # 2) Actualizar Sheets (espejo)
    try:
        syncer.sync_ticket_estado(ticket_id, nuevo_estado)
    except Exception as e:
        logger.exception(f"Error actualizando estado en Sheets: {e}")

    # 3) Notificar usuario y actualizar mensaje admin
    try:
        from datetime import datetime, timedelta
        fecha_ven = datetime.now() - timedelta(hours=4)  # UTC-4 Venezuela
        fecha = fecha_ven.strftime("%d/%m/%Y %H:%M:%S")

        datos_txt = (
            f"🎫 *Ticket:* `{ticket_id}`\n"
            f"👤 *Nombre:* {pendiente.get('nombre', 'N/A')}\n"
            f"📞 *Teléfono:* {pendiente.get('telefono', 'N/A')}\n"
            f"🪪 *Cédula:* {pendiente.get('cedula', 'N/A')}\n"
            f"🔢 *Números:* {', '.join(pendiente['numeros'])}\n"
            f"📅 *Fecha:* {fecha}\n"
        )

        if accion == "verificar":
            msg_user = (
                "✅ *PAGO VERIFICADO*\n\n"
                f"{datos_txt}\n"
                "📌 Su participación ha sido confirmada. ¡Mucha suerte en el sorteo! 🍀"
            )
        else:
            msg_user = (
                "❌ *PAGO NO VERIFICADO*\n\n"
                f"{datos_txt}\n"
                "⚠️ Verifique su comprobante y vuelva a intentarlo o contacte al administrador en el canal."
            )

        await context.bot.send_message(
            chat_id=pendiente["user_id"],
            text=msg_user,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.warning(f"No se pudo notificar al usuario: {e}")

    # 4) Resumen para el admin
    try:
        resumen = (f"🎫 Ticket: `{ticket_id}`\n"
                   f"👤 Usuario: @{pendiente.get('username') or pendiente.get('nombre')}\n"
                   f"🔢 Números: {', '.join(pendiente['numeros'])}\n"
                   f"Estado: {nuevo_estado}")
        await q.edit_message_caption(caption=resumen, parse_mode="Markdown", reply_markup=None)
    except Exception as e:
        logger.warning(f"No se pudo editar mensaje admin: {e}")


#---------------------------------------------------------------

@requiere_activado
async def cancelar_verificacion_nuevo_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    try:
        _, accion, ticket_id = q.data.split("|")
    except Exception:
        return await q.answer("❌ Formato inválido.", show_alert=True)

    # Restaurar caption + botones originales
    try:
        caption = (f"📌 *Nuevo comprobante*\n\n"
                   f"🎫 Ticket: `{ticket_id}`\n"
                   f"Usa los botones para decidir.")
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Verificar", callback_data=f"verificar|{ticket_id}"),
                InlineKeyboardButton("❌ Rechazar", callback_data=f"rechazar|{ticket_id}")
            ]
        ])
        await q.edit_message_caption(caption=caption, parse_mode="Markdown", reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"No se pudo restaurar el prompt: {e}")

#---------------------------------------------------------------

@requiere_activado
async def debug_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        return

    tickets_info = [
        f"ID: {data.get('ticket_id')} - Hash: {h}" 
        for h, data in sistema.esperando_hash.items()
    ]

    await update.message.reply_text(
        "📝 Tickets pendientes:\n" + "\n".join(tickets_info) if tickets_info 
        else "No hay tickets pendientes"
    )


#--------------------------------------------------------------


@requiere_activado
async def recibir_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, h = update.effective_user.id, update.message.text.strip()
    if not hash_valido(h):
        return await update.message.reply_text(
            "❗ Formato de hash inválido. Revisa y vuelve a enviarlo.")
    datos = sistema.user_datos.get(uid)
    if not datos or not datos.get("numeros"):
        return

    # Generar ticket_id único para este ticket pendiente
    ticket_id = str(uuid.uuid4())[:8].upper()

    # Guardar ticket_id dentro del dict para reutilizar después
    sistema.esperando_hash[h] = {
        "user_id": uid,
        "ticket_id": ticket_id,
        **datos
    }

    # Guardar respaldo como pendiente
    username_or_nombre = update.effective_user.username or datos["nombre"]
    respaldar_ticket(
        ticket_id=ticket_id,
        username_or_nombre=username_or_nombre,
        user_id=uid,
        telefono=datos["telefono"],
        cedula=datos["cedula"],
        numeros=datos["numeros"],
        hash_pago=h,
        estado="Pendiente",
        imagen_url=imagen_url,
        precio=sistema.precio_global,
    )
    monto_total = len(datos["numeros"]) * sistema.precio_global
    sistema.esperando_imagen[uid] = h
    await update.message.reply_text(
        f"✅ Hash recibido. Espera verificación.\n"
        f"💰 Monto pagado: *{monto_total:.2f} USD*",
        parse_mode="Markdown")

    # Preparar datos escapados para el admin
    if update.effective_user.username:
        user_disp = escape_markdown(f"@{update.effective_user.username}",
                                    version=1)
    else:
        nombre_esc = escape_markdown(datos["nombre"], version=1)
        user_disp = f"[{nombre_esc}](tg://user?id={uid})"

    numeros_seg = escape_markdown(", ".join(datos["numeros"]), version=1)
    nombre_seg = escape_markdown(datos["nombre"], version=1)
    tel_seg = escape_markdown(datos["telefono"], version=1)
    cedula_seg = escape_markdown(datos["cedula"], version=1)
    hash_seg = escape_markdown(h, version=1)

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Verificado",
                             callback_data=f"verificado|{hash_seg}"),
        InlineKeyboardButton("❌ No verificado",
                             callback_data=f"noverificado|{hash_seg}")
    ]])
    texto_admin = ("📥 *Nueva participación* 📥\n"
                   f"👤 {user_disp}\n"
                   f"🔢 Números: {numeros_seg}\n"
                   f"🧾 Nombre: {nombre_seg}\n"
                   f"📞 Teléfono: {tel_seg}\n"
                   f"🪪 Cédula: {cedula_seg}\n"
                   f"🔗 `{hash_seg}`")
    await context.bot.send_message(chat_id=int(ADMIN_ID),
                                   text=texto_admin,
                                   parse_mode="Markdown",
                                   reply_markup=kb)


# ——————————————————————————————————————————————————————————————————————————————
# 13) CONFIRMACIÓN PREVIA A MARCAR PAGO
@requiere_activado
async def prompt_verificacion(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    accion, h = q.data.split("|")
    label = "VERIFICAR" if accion == "verificado" else "MARCAR COMO NO VERIFICADO"

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmar",
                             callback_data=f"confirmar|{accion}|{h}"),
        InlineKeyboardButton("❌ Cancelar",
                             callback_data=f"cancelar|{accion}|{h}")
    ]])

    mensaje_confirmacion = f"¿Estás seguro de que deseas *{label}* este pago?"

    try:
        # ---- LÓGICA CORREGIDA ----
        # Comprueba si el mensaje original tiene una foto
        if q.message.photo:
            await q.edit_message_caption(caption=mensaje_confirmacion,
                                         parse_mode="Markdown",
                                         reply_markup=kb)
        else:
            await q.edit_message_text(text=mensaje_confirmacion,
                                      parse_mode="Markdown",
                                      reply_markup=kb)
    except Exception as e:
        logger.error(f"Error en prompt_verificacion al editar mensaje: {e}")
        # Notificar al admin en el chat si la edición falla
        await q.answer("❌ Error al actualizar el mensaje.", show_alert=True)

#——————————————————————————————————————————————————————————————————————————————
# 14) CANCELAR: vuelve al mensaje original
# 14) CANCELAR: vuelve al mensaje original
@requiere_activado
async def cancelar_verificacion(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Acción cancelada")
    _, accion, h = q.data.split("|")

    rec = sistema.esperando_hash.get(h)
    if not rec:
        return await q.edit_message_text("❌ Ticket no encontrado o ya procesado.")

    uid = rec["user_id"]
    if rec.get("username"):
        user_disp = escape_markdown(f"@{rec['username']}", version=1)
    else:
        nombre_esc = escape_markdown(rec["nombre"], version=1)
        user_disp = f"[{nombre_esc}](tg://user?id={uid})"

    numeros_seg = escape_markdown(", ".join(rec["numeros"]), version=1)
    hash_seg = escape_markdown(h, version=1)

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Verificado", callback_data=f"verificado|{hash_seg}"),
        InlineKeyboardButton("❌ No verificado", callback_data=f"noverificado|{hash_seg}")
    ]])

    # ---- LÓGICA CORREGIDA ----
    # Dependiendo de si el mensaje original tenía foto, se restaura de una forma u otra
    try:
        if q.message.photo:
            # Texto para mensajes con foto (más simple)
            texto_original = (
                f"📌 *Nuevo comprobante*\n\n"
                f"🎫 Ticket: `{hash_seg}`\n"
                f"👤 Usuario: {user_disp}\n"
                f"🔢 Números: {', '.join(rec['numeros'])}"
            )
            await q.edit_message_caption(caption=texto_original, parse_mode="Markdown", reply_markup=kb)
        else:
            # Texto para mensajes de solo texto (con todos los detalles)
            nombre_seg = escape_markdown(rec["nombre"], version=1)
            tel_seg = escape_markdown(rec["telefono"], version=1)
            cedula_seg = escape_markdown(rec["cedula"], version=1)
            texto_original = ("📥 *Nueva participación* 📥\n"
                           f"👤 {user_disp}\n"
                           f"🔢 Números: {numeros_seg}\n"
                           f"🧾 Nombre: {nombre_seg}\n"
                           f"📞 Teléfono: {tel_seg}\n"
                           f"🪪 Cédula: {cedula_seg}\n"
                           f"🔗 `{hash_seg}`")
            await q.edit_message_text(texto_original, parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        logger.error(f"Error en cancelar_verificacion al editar mensaje: {e}")
# ——————————————————————————————————————————————————————————————————————————————
# 15) FINALIZAR VERIFICACIÓN
@requiere_activado
async def finalizar_verificacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Cierra el flujo de confirmación para tickets recuperados por hash (prefijo 'confirmar|').
    Ahora actualiza BD y luego espeja a Sheets.
    """
    q = update.callback_query
    await q.answer()

    try:
        _, accion, h = q.data.split("|")
    except Exception:
        return await q.answer("❌ Formato de confirmación inválido.", show_alert=True)

    rec = sistema.esperando_hash.pop(h, None)
    if not rec:
        try:
            await q.edit_message_text("⚠️ Este proceso ya fue atendido o expiró.")
        except Exception:
            pass
        return

    uid = rec["user_id"]
    ticket_id = rec["ticket_id"]

    # Fecha referencia (UTC-4 Venezuela)
    from datetime import datetime, timedelta
    fecha_ven = datetime.now() - timedelta(hours=4)
    fecha = fecha_ven.strftime("%d/%m/%Y %H:%M:%S")

    # Mensaje al usuario según acción
    if accion == "verificado":
        msg_user = (f"✅ *Pago verificado*\n\n"
                    f"🎫 *Ticket:* `{ticket_id}`\n"
                    f"🔢 *Números:* {', '.join(rec['numeros'])}\n"
                    f"📅 *Fecha:* {fecha}\n\n"
                    "¡Gracias por tu compra!")
        estado_texto = "Verificado ✅"
    else:
        msg_user = (f"❌ *Pago NO verificado*\n\n"
                    f"🎫 *Ticket:* `{ticket_id}`\n"
                    f"🔢 *Números:* {', '.join(rec['numeros'])}\n"
                    f"📅 *Fecha:* {fecha}\n\n"
                    "🔍 Verifica tu comprobante o contacta al administrador.")
        estado_texto = "No verificado ❌"

    try:
        await context.bot.send_message(chat_id=uid, text=msg_user, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"No se pudo notificar al usuario: {e}")

    # 1) Actualizar BD
    try:
        db.actualizar_estado_db(ticket_id, estado_texto)
    except Exception as e:
        logger.error(f"Error actualizando estado en BD: {e}")

    # 2) Espejar estado a Sheets
    try:
        syncer.sync_ticket_estado(ticket_id, estado_texto)
    except Exception as e:
        logger.warning(f"No se pudo sync estado a Sheets: {e}")

    # 3) Mostrar resultado al admin (edita el mensaje original con foto o texto)
    try:
        from telegram.helpers import escape_markdown
        if rec.get("username"):
            user_disp = escape_markdown(f"@{rec['username']}", version=1)
        else:
            user_disp = escape_markdown(rec["nombre"], version=1)

        numeros_seg = escape_markdown(", ".join(rec["numeros"]), version=1)
        nombre_seg = escape_markdown(rec["nombre"], version=1)
        tel_seg = escape_markdown(rec["telefono"], version=1)
        cedula_seg = escape_markdown(rec["cedula"], version=1)
        ticket_seg = escape_markdown(ticket_id, version=1)
        h_seg = escape_markdown(h, version=1)

        status = "✅ *Pago VERIFICADO*" if accion == "verificado" else "❌ *Pago NO verificado*"
        texto_admin = (f"{status}\n\n"
                       f"🎫 *Ticket:* `{ticket_seg}`\n"
                       f"👤 *Usuario:* {user_disp} (ID: {uid})\n"
                       f"🧾 *Nombre:* {nombre_seg}\n"
                       f"📞 {tel_seg}\n"
                       f"🪪 {cedula_seg}\n"
                       f"🔢 {numeros_seg}\n"
                       f"🔗 `{h_seg}`\n"
                       f"📅 {fecha}")

        if q.message.photo:
            await q.edit_message_caption(caption=texto_admin, parse_mode="Markdown", reply_markup=None)
        else:
            await q.edit_message_text(text=texto_admin, parse_mode="Markdown", reply_markup=None)
    except Exception as e:
        logger.error(f"Error actualizando mensaje admin: {e}")

#——————————————————————————————————————————————————————————————————————————————
# 16) CONSULTAR TICKET (solo admin)
@requiere_activado
async def consultar_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if str(uid) != ADMIN_ID:
        return await update.message.reply_text("❌ Solo admin.")
    if not context.args:
        return await update.message.reply_text("Uso: /ticket <ID>")
    tid = context.args[0].upper()
    t = sistema.tickets_verificados.get(tid)
    if not t:
        return await update.message.reply_text("❌ No existe.")
    estado = "✅ Verificado" if t["verificado"] else "❌ No verificado"
    if t.get("username"):
        user_disp = escape_markdown(f"@{t['username']}", version=1)
    else:
        nombre_esc = escape_markdown(t["nombre"], version=1)
        user_disp = f"[{nombre_esc}](tg://user?id={t['user_id']})"

    numeros_seg = escape_markdown(", ".join(t["numeros"]), version=1)
    nombre_seg = escape_markdown(t["nombre"], version=1)
    tel_seg = escape_markdown(t["telefono"], version=1)
    cedula_seg = escape_markdown(t["cedula"], version=1)
    hash_seg = escape_markdown(t["hash"], version=1)
    ticket_seg = escape_markdown(tid, version=1)

    await update.message.reply_text(
        f"🎫 *Ticket:* `{ticket_seg}`\n"
        f"👤 *Usuario:* {user_disp} (ID: {t['user_id']})\n"
        f"🧾 *Nombre:* {nombre_seg}\n"
        f"📞 {tel_seg}\n"
        f"🔢 {numeros_seg}\n"
        f"🔗 `{hash_seg}`\n"
        f"📅 {t['fecha']}\n"
        f"📌 *Estado:* {estado}",
        parse_mode="Markdown")


# ——————————————————————————————————————————————————————————————————————————————
# 17) MIS TICKETS (usuario)
@requiere_activado
async def mis_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    propios = [(tid, t) for tid, t in sistema.tickets_verificados.items()
               if t.get("user_id") == uid]
    if not propios:
        return await update.message.reply_text(
            "❗ No tienes tickets verificados aún.")

    lineas = []
    for tid, t in propios:
        estado = "✅ Verificado" if t.get("verificado") else "❌ No verificado"
        nums = escape_markdown(", ".join(f"{int(n):02}"
                                         for n in t.get("numeros", [])),
                               version=1)
        fecha = t.get("fecha", "¿Sin fecha?")
        tid_esc = escape_markdown(tid, version=1)
        lineas.append(f"🎫 `{tid_esc}` • {nums} • {estado} • {fecha}")

    texto = "📋 *Tus tickets:*\n\n" + "\n".join(lineas)
    await update.message.reply_text(texto, parse_mode="Markdown")


# ——————————————————————————————————————————————————————————————————————————————
# 18) CONFIGURAR COMANDOS EN EL BOT
async def set_commands(app):
    # Comandos para usuarios normales
    await app.bot.set_my_commands(commands=[
        BotCommand("start", "Iniciar"),
        BotCommand("numeros", "Seleccionar números"),
        BotCommand("mis_tickets", "Consulta tus tickets")
    ],
                                  scope=BotCommandScopeDefault())
    # Comandos adicionales SOLO para el admin
    await app.bot.set_my_commands(
        commands=[
            BotCommand("start", "Iniciar"),
            BotCommand("numeros", "Seleccionar números"),
            BotCommand("estado", "Ver estado del sistema"),
            BotCommand("precio", "Ajustar precio"),
            BotCommand("rango", "Configurar rango de números"),
            BotCommand("reset", "Reiniciar sistema"),
            BotCommand("apagar", "Pausar bot"),
            BotCommand("encender", "Reanudar bot"),
            BotCommand("ticket", "Consultar ticket"),
            BotCommand("liberar", "Liberar número")
        ],
        scope=BotCommandScopeChat(chat_id=int(ADMIN_ID)))


# ——————————————————————————————————————————————————————————————————————————————
# 19) MANEJADOR GLOBAL DE EXCEPCIONES
async def manejo_excepciones(update: object,
                             context: ContextTypes.DEFAULT_TYPE):
    logger.error("Excepción no controlada en handler:", exc_info=context.error)
    mensaje_error = escape_markdown(str(context.error), version=1)
    await context.bot.send_message(
        chat_id=int(ADMIN_ID),
        text=f"❗ Ha ocurrido un error:\n`{mensaje_error}`",
        parse_mode="Markdown")


# ————————————————————————————————————————————————————————————————————

@requiere_activado
async def recibir_imagen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    # Verificar si el usuario tiene datos completos
    datos_usuario = sistema.user_datos.get(uid)
    if not datos_usuario or not all(
            key in datos_usuario
            for key in ['nombre', 'telefono', 'cedula', 'numeros']):
        return await update.message.reply_text(
            "❗ Primero completa tus datos con /numeros")

    # Verificar que haya imagen
    if not update.message.photo:
        return await update.message.reply_text(
            "❗ Envía una foto válida del comprobante")

    try:
        # Obtener la foto de mejor calidad
        foto = update.message.photo[-1]
        file_id = foto.file_id

        # Enviar al canal de comprobantes
        CANAL_COMPROBANTES = "-1002753190289"  # <-- Asegúrate de tener al bot como administrador
        ticket_id = str(uuid.uuid4())[:8].upper()

        await context.bot.send_photo(
            chat_id=CANAL_COMPROBANTES,
            photo=file_id,
            caption=f"📌 Comprobante de {datos_usuario['nombre']} - Ticket {ticket_id}"
        )

        # Guardar en Google Sheets con referencia "En canal"
        exito = respaldar_ticket(
            ticket_id=ticket_id,
            username_or_nombre=update.effective_user.username or datos_usuario["nombre"],
            user_id=uid,
            telefono=datos_usuario["telefono"],
            cedula=datos_usuario["cedula"],
            numeros=datos_usuario["numeros"],
            hash_pago="",
            estado="Pendiente ⏳",
            imagen_url="En canal",  # Usamos texto descriptivo
            precio=sistema.precio_global
        )

        if exito:
            # Guardar en memoria como pendiente
            sistema.tickets_pendientes[ticket_id] = {
                "ticket_id": ticket_id,
                "user_id": uid,
                "username": update.effective_user.username,
                "numeros": datos_usuario["numeros"],
                "nombre": datos_usuario["nombre"],
                "telefono": datos_usuario["telefono"],
                "cedula": datos_usuario["cedula"],
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "verificado": False,
                "imagen_url": "En canal"
            }

            await update.message.reply_text(
                "✅ Comprobante recibido y registrado correctamente!")

            # Notificar al admin
            await notificar_admin(update, context, datos_usuario, ticket_id, file_id)
        else:
            await update.message.reply_text(
                "⚠️ Se recibió tu comprobante pero hubo un error al guardarlo")

    except Exception as e:
        logger.error(f"Error al procesar imagen: {str(e)}")
        await update.message.reply_text(
            "❌ Ocurrió un error al procesar tu comprobante")

#——————————
# 20) MAIN
def main():
    inicializar_bd_al_arranque()
    # 1. Construir la aplicación con post_init
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    # 2. Inicializar sistema (inactivo hasta configuración)
    sistema.reset_completo()

    # 3. Intentar configuración automática desde Sheets
    configurado_desde_sheets = False
    try:
        configurado_desde_sheets = inicializar_tickets_desde_sheets()
    except Exception as e:
        logger.warning(f"No se pudo configurar automáticamente: {str(e)}")

    # 4. Manejador de errores
    app.add_error_handler(manejo_excepciones)

        # --- REEMPLÁZALO CON ESTO ---
        # 5. Registrar todos los handlers incondicionalmente
    registrar_todos_los_handlers(app)
    logger.info("Todos los handlers han sido registrados. El estado será controlado por el decorador.")

    # 6. Iniciar el bot
    app.run_polling()


def registrar_todos_los_handlers(app):
    # Admin
    app.add_handler(CommandHandler("rango", configurar_rango))
    app.add_handler(CommandHandler("apagar", apagar))
    app.add_handler(CommandHandler("encender", encender))
    app.add_handler(CommandHandler("reset", reset_sistema))
    app.add_handler(CommandHandler("estado", verificar_estado))
    app.add_handler(CommandHandler("precio", cambiar_precio))
    app.add_handler(CommandHandler("liberar", liberar_numero))
    app.add_handler(CommandHandler("ticket", consultar_ticket))
    app.add_handler(CallbackQueryHandler(handle_reset_confirmation, pattern="^(confirmar_reset|cancelar_reset)$"))

    # Usuario
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("numeros", mostrar_numeros))
    app.add_handler(CommandHandler("mis_tickets", mis_tickets))

    # Interacción de selección
    app.add_handler(CallbackQueryHandler(handle_random_selection, pattern=r"^random_select\|"))
    app.add_handler(CallbackQueryHandler(button, pattern=r"^(page_\d+|\d+|confirmar|noop)$"))

    # Comprobante (foto)
    app.add_handler(MessageHandler(filters.PHOTO, manejar_imagen_comprobante))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensajes))

    # *** SOLO el flujo nuevo de verificación ***
    app.add_handler(CallbackQueryHandler(manejar_verificacion_admin, pattern=r"^(verificar|rechazar)\|"))
    app.add_handler(CallbackQueryHandler(finalizar_verificacion_nuevo_ticket, pattern=r"^confirmar_nuevo\|"))
    app.add_handler(CallbackQueryHandler(cancelar_verificacion_nuevo_ticket, pattern=r"^cancelar_nuevo\|"))


if __name__ == "__main__":
    main()

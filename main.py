from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = "8119337796:AAHGQ8Qa2mdlhokn01FHyL0p3wqOj_rmoiU"
ADMIN_ID =  "7899842142"

numeros_disponibles = {f"{i:02d}": True for i in range(100)}
user_seleccion = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎉 Bienvenido al bot de Rifas. Usa /numeros para ver los números disponibles.")

async def mostrar_numeros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    fila = []
    count = 0
    for numero, disponible in numeros_disponibles.items():
        if disponible:
            fila.append(InlineKeyboardButton(numero, callback_data=numero))
        else:
            fila.append(InlineKeyboardButton("❌", callback_data="x"))
        count += 1
        if count % 5 == 0:
            keyboard.append(fila)
            fila = []
    if fila:
        keyboard.append(fila)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Elige un número disponible:", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    numero = query.data

    if numero == "x" or not numeros_disponibles.get(numero, False):
        await query.edit_message_text("❌ Este número ya no está disponible. Usa /numeros para ver los que quedan.")
        return

    numeros_disponibles[numero] = False
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name

    user_seleccion[user_id] = numero

    await query.edit_message_text(
        f"🛒 Elegiste el número: {numero}\n\n"
        "Por favor, realiza el pago de 1 USDT TRC20 a:\n"
        "`TMDxbKNrNNwrV8MbSczMUWiT4b9R3o2qQN`\n\n"
        "Cuando pagues, responde este mensaje con el *hash de la transacción*.",
        parse_mode="Markdown"
    )

async def recibir_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name
    hash_tx = update.message.text
    numero = user_seleccion.get(user_id, "Desconocido")

    await update.message.reply_text("✅ ¡Gracias! Tu participación fue registrada. Espera el sorteo 🎁")

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📥 NUEVO PARTICIPANTE:\n"
             f"👤 Usuario: @{username} (ID: {user_id})\n"
             f"🔢 Número: {numero}\n"
             f"🔗 Hash: `{hash_tx}`",
        parse_mode="Markdown"
    )

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("numeros", mostrar_numeros))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_hash))
app.run_polling()



from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot activo."

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

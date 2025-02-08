import unicodedata
import logging
from firebase_config import initialize_firebase

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
    CallbackContext
)
from fuzzywuzzy import process

# Configuração do logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Inicializa o Firebase
courses_ref = initialize_firebase()

# Estados para os ConversationHandlers
AD_NOME, AD_AREA, AD_LINK = range(3)
ED_NOME, ED_CAMPO, ED_VALOR = range(3, 6)
AP_NOME = 6

# Opções de áreas disponíveis
AREAS_DISPONIVEIS = [
    "humanas", "matematica", "ciencias da natureza", "redacao", "linguagens"
]

def normalize_text(text: str) -> str:
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    return text.lower().strip()

def get_effective_message(update: Update):
    """Retorna a mensagem efetiva, seja update.message ou update.callback_query.message."""
    if update.message:
        return update.message
    elif update.callback_query:
        return update.callback_query.message
    return None

def build_courses_message() -> str:
    """Constroi a mensagem com a lista de cursos agrupados por área."""
    courses = courses_ref.get() or {}
    if not courses:
        return "😔 Ainda não há cursos cadastrados."
    
    grouped = {}
    for curso_id, curso_info in courses.items():
        area = curso_info.get("area", "desconhecida")
        grouped.setdefault(area, []).append(curso_info["nome"])
    
    msg = "📚 *Cursos Disponíveis:*\n"
    for area, nomes in grouped.items():
        msg += f"\n🔸 *{area.capitalize()}*:\n" + "\n".join([f"  - {nome}" for nome in nomes]) + "\n"
    
    msg += (
        "\n\n🔎 Para visualizar os detalhes de um curso, digite o comando:\n"
        "`/curso <nome do curso>`\n"
        "Exemplo: `/curso Matemática`"
    )
    return msg

# --- Handler de Comando /start ---
async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("➕ Adicionar Curso", callback_data="adicionar_curso")],
        [InlineKeyboardButton("📚 Listar Cursos", callback_data="listar_cursos_btn")],
        [InlineKeyboardButton("✏️ Editar Curso", callback_data="editar_curso")],
        [InlineKeyboardButton("🗑️ Apagar Curso", callback_data="apagar_curso")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        "👋 Olá! Seja bem-vindo ao *Bot de Cursos*.\n\n"
        "Escolha uma das opções abaixo:"
    )
    effective_message = get_effective_message(update)
    await effective_message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

# --- Fluxo para Listar Cursos ---
async def list_courses_button(update: Update, context: CallbackContext):
    logger.info("Callback 'listar_cursos_btn' acionado.")
    query = update.callback_query
    await query.answer("Listando cursos...")
    msg = build_courses_message()
    try:
        await query.edit_message_text(text=msg, parse_mode="Markdown")
        logger.info("Mensagem editada com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao editar a mensagem: {e}")
        # Caso não seja possível editar a mensagem, envia uma nova mensagem
        await context.bot.send_message(chat_id=query.message.chat.id, text=msg, parse_mode="Markdown")

async def list_courses(update: Update, context: CallbackContext):
    msg = build_courses_message()
    await update.message.reply_text(msg, parse_mode="Markdown")

# --- ConversationHandlers omitidos para concisão ---

def main():
    application = Application.builder().token("SEU_TOKEN_AQUI").build()

    # Handlers de comando
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("listar_cursos", list_courses))
    
    # Handler para o botão "Listar Cursos" (callback_data: listar_cursos_btn)
    application.add_handler(CallbackQueryHandler(list_courses_button, pattern="^listar_cursos_btn$"))
    
    application.run_polling()

if __name__ == '__main__':
    main()

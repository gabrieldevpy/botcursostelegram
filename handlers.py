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
from telegram.error import BadRequest
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
    """Constrói a mensagem com a lista de cursos agrupados por área."""
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
async def list_courses(update: Update, context: CallbackContext):
    msg = build_courses_message()
    await update.message.reply_text(msg, parse_mode="Markdown")

async def list_courses_button(update: Update, context: CallbackContext):
    logger.info("Callback 'listar_cursos_btn' acionado.")
    query = update.callback_query
    await query.answer("Listando cursos...")
    
    msg = build_courses_message()

    if "Ainda não há cursos cadastrados" in msg:
        await query.message.reply_text(msg, parse_mode="Markdown")
        return

    try:
        await query.message.edit_text(text=msg, parse_mode="Markdown")
    except BadRequest as e:
        logger.warning(f"Erro de formatação: {e}")
        await query.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")

# --- Fluxo para Consultar Curso ---
async def get_course_link(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text(
            "❗ Para consultar um curso, utilize:\n`/curso <nome do curso>`",
            parse_mode="Markdown"
        )
        return

    user_input = " ".join(context.args).strip()
    courses = courses_ref.get() or {}

    course_list = []
    original_names = {}
    for curso_id, curso_info in courses.items():
        original = curso_info["nome"]
        normalized = normalize_text(original)
        course_list.append(normalized)
        original_names[normalized] = original

    if not course_list:
        await update.message.reply_text("😔 Não há cursos cadastrados no momento.")
        return

    normalized_input = normalize_text(user_input)
    matches = process.extract(normalized_input, course_list, limit=3)
    filtered_matches = [match for match in matches if match[1] > 70]

    if not filtered_matches:
        await update.message.reply_text(
            f"🤷‍♂️ Não encontrei nenhum curso parecido com *{user_input}*.",
            parse_mode="Markdown"
        )
        return

    best_match = filtered_matches[0][0]
    original_name = original_names[best_match]

    for curso_id, curso_info in courses.items():
        if normalize_text(curso_info["nome"]) == best_match:
            await update.message.reply_text(
                f"🔍 Acho que você quis dizer:\n\n🔗 *{original_name}*: {curso_info['link']}",
                parse_mode="Markdown"
            )
            return

    await update.message.reply_text(
        f"🤷‍♂️ Curso *{user_input}* não encontrado.",
        parse_mode="Markdown"
    )

# --- ConversationHandlers ---
add_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start, pattern="^adicionar_curso$")],
    states={},
    fallbacks=[]
)

edit_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start, pattern="^editar_curso$")],
    states={},
    fallbacks=[]
)

del_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start, pattern="^apagar_curso$")],
    states={},
    fallbacks=[]
)

def main():
    application = Application.builder().token("SEU_TOKEN_AQUI").build()

    # Handlers de comando
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("listar_cursos", list_courses))
    application.add_handler(CommandHandler("curso", get_course_link))
    
    # ConversationHandlers
    application.add_handler(add_conv)
    application.add_handler(edit_conv)
    application.add_handler(del_conv)
    
    # Handler para o botão "Listar Cursos"
    application.add_handler(CallbackQueryHandler(list_courses_button, pattern="^listar_cursos_btn$"))
    
    application.run_polling()

if __name__ == '__main__':
    main()

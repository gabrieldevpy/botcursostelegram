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

# --- Fluxo para Adicionar Curso ---
async def add_course_start(update: Update, context: CallbackContext):
    effective_message = get_effective_message(update)
    await effective_message.reply_text("🤔 Por favor, informe o nome do curso que deseja adicionar:")
    return AD_NOME

async def add_course_nome(update: Update, context: CallbackContext):
    nome = update.message.text.strip()
    if not nome:
        await update.message.reply_text("⚠️ Ops! Não recebi o nome. Tente novamente, por favor.")
        return AD_NOME

    context.user_data["add_nome"] = nome

    keyboard = [
        [InlineKeyboardButton(area.capitalize(), callback_data=area)]
        for area in AREAS_DISPONIVEIS
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🚀 Selecione a área do curso:", reply_markup=reply_markup)
    return AD_AREA

async def add_course_area_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Remove o indicador de carregamento do botão
    area = query.data
    context.user_data["add_area"] = area

    await query.edit_message_text(
        f"👍 Ótima escolha! Você selecionou *{area.capitalize()}*.\nAgora, envie o link do curso:",
        parse_mode="Markdown"
    )
    return AD_LINK

async def add_course_link(update: Update, context: CallbackContext):
    link = update.message.text.strip()
    nome = context.user_data.get("add_nome")
    area = context.user_data.get("add_area")

    course_data = {
        "nome": nome,
        "area": area,
        "link": link
    }
    courses_ref.push(course_data)

    await update.message.reply_text(
        f"🎉 O curso *{nome}* foi adicionado com sucesso!\n\nUtilize o botão *📚 Listar Cursos* para visualizar todos os cursos disponíveis.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# --- Fluxo para Listar Cursos ---
# Função para o comando /listar_cursos
async def list_courses(update: Update, context: CallbackContext):
    msg = build_courses_message()
    await update.message.reply_text(msg, parse_mode="Markdown")

# Função para o callback do botão "Listar Cursos"
async def list_courses_button(update: Update, context: CallbackContext):
    logger.info("Callback 'listar_cursos_btn' acionado.")
    query = update.callback_query
    await query.answer("Listando cursos...")

    try:
        msg = build_courses_message()
        await query.edit_message_text(text=msg, parse_mode="Markdown")
        logger.info("Mensagem editada com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao editar a mensagem: {e}")
        await context.bot.send_message(chat_id=query.message.chat.id, text=msg, parse_mode="Markdown")

# --- Fluxo para Consultar Curso (via comando) ---
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

# --- Fluxo para Editar Curso ---
async def edit_course_start(update: Update, context: CallbackContext):
    effective_message = get_effective_message(update)
    await effective_message.reply_text("✏️ Informe o nome do curso que deseja editar:")
    return ED_NOME

async def edit_course_nome(update: Update, context: CallbackContext):
    nome = update.message.text.strip()
    courses = courses_ref.get() or {}
    course_list = [curso_info["nome"] for curso_info in courses.values()]
    matches = process.extract(nome, course_list, limit=1)
    if not matches or matches[0][1] < 70:
        await update.message.reply_text("😕 Não consegui encontrar esse curso. Tente novamente!")
        return ConversationHandler.END

    best_match = matches[0][0]
    context.user_data["edit_nome"] = best_match

    await update.message.reply_text(
        f"✏️ Editando o curso *{best_match}*.\n\nPor favor, informe qual campo deseja alterar (digite *nome* ou *link*):",
        parse_mode="Markdown"
    )
    return ED_CAMPO

async def edit_course_field(update: Update, context: CallbackContext):
    field = update.message.text.strip().lower()
    if field not in ["nome", "link"]:
        await update.message.reply_text(
            "❗ Digite apenas *nome* ou *link* para indicar o campo a ser alterado.",
            parse_mode="Markdown"
        )
        return ED_CAMPO

    context.user_data["edit_field"] = field

    await update.message.reply_text(f"📝 Informe o novo valor para o campo *{field}*:")
    return ED_VALOR

async def edit_course_value(update: Update, context: CallbackContext):
    new_value = update.message.text.strip()
    courses = courses_ref.get() or {}
    edit_nome = context.user_data["edit_nome"]
    edit_field = context.user_data["edit_field"]

    for curso_id, curso_info in courses.items():
        if curso_info["nome"] == edit_nome:
            if edit_field == "nome":
                curso_info["nome"] = new_value
            elif edit_field == "link":
                curso_info["link"] = new_value
            courses_ref.update({curso_id: curso_info})
            await update.message.reply_text(
                f"🎉 O campo *{edit_field}* do curso *{edit_nome}* foi atualizado para: {new_value}",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

# --- Main Application Setup ---
def main():
    application = Application.builder().token("YOUR_BOT_TOKEN").build()

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AD_NOME: [MessageHandler(filters.TEXT, add_course_nome)],
            AD_AREA: [CallbackQueryHandler(add_course_area_callback)],
            AD_LINK: [MessageHandler(filters.TEXT, add_course_link)],
            ED_NOME: [MessageHandler(filters.TEXT, edit_course_nome)],
            ED_CAMPO: [MessageHandler(filters.TEXT, edit_course_field)],
            ED_VALOR: [MessageHandler(filters.TEXT, edit_course_value)],
        },
        fallbacks=[],
    )

    # Adiciona handlers ao aplicativo
    application.add_handler(conversation_handler)
    application.add_handler(CommandHandler("listar_cursos", list_courses))
    application.add_handler(CallbackQueryHandler(list_courses_button, pattern="^listar_cursos_btn$"))
    application.add_handler(CommandHandler("curso", get_course_link))

    # Inicia o bot
    application.run_polling()

if __name__ == "__main__":
    main()

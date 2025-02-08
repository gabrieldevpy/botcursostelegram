import unicodedata
import logging
import json
from firebase_config import initialize_firebase

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
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

# Estados para o ConversationHandler
AD_NOME, AD_AREA, AD_LINK = range(3)
ED_NOME, ED_CAMPO, ED_VALOR = range(3, 6)
AP_NOME = 6

# Opções de áreas disponíveis
AREAS_DISPONIVEIS = [
    "humanas", "matematica", "ciencias da natureza", "redacao", "linguagens"
]

# Função auxiliar para normalizar texto
def normalize_text(text: str) -> str:
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    return text.lower().strip()

# Função auxiliar para obter a mensagem efetiva (seja de update.message ou update.callback_query.message)
def get_effective_message(update: Update):
    if update.message:
        return update.message
    elif update.callback_query:
        return update.callback_query.message
    return None

# --- Handlers de Comandos ---

async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Adicionar Curso", callback_data="adicionar_curso")],
        [InlineKeyboardButton("Listar Cursos", callback_data="listar_cursos")],
        [InlineKeyboardButton("Consultar Curso", callback_data="curso")],
        [InlineKeyboardButton("Editar Curso", callback_data="editar_curso")],
        [InlineKeyboardButton("Apagar Curso", callback_data="apagar_curso")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        "👋 Olá! Eu sou o bot de cursos. Escolha uma opção abaixo ou utilize os comandos:\n"
        "/adicionar_curso, /listar_cursos, /curso, /editar_curso, /apagar_curso"
    )
    effective_message = get_effective_message(update)
    await effective_message.reply_text(msg, reply_markup=reply_markup)

# --- Callback para a tela inicial ---
async def home_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Remove o "loading" do botão
    data = query.data
    chat_id = update.effective_chat.id

    if data == "adicionar_curso":
        # Inicia a conversação para adicionar curso
        await context.bot.send_message(chat_id=chat_id, text="🔹 Qual é o nome do curso que deseja adicionar?")
        return AD_NOME
    elif data == "listar_cursos":
        await list_courses(update, context)
    elif data == "curso":
        await query.edit_message_text("🔹 Para consultar um curso, utilize o comando:\n/curso <nome do curso>")
    elif data == "editar_curso":
        await context.bot.send_message(chat_id=chat_id, text="🔹 Envie o nome do curso que deseja editar:")
        return ED_NOME
    elif data == "apagar_curso":
        await context.bot.send_message(chat_id=chat_id, text="🔹 Envie o nome do curso que deseja apagar:")
        return AP_NOME

# --- Adicionar Curso ---

async def add_course_start(update: Update, context: CallbackContext):
    effective_message = get_effective_message(update)
    await effective_message.reply_text("🔹 Qual é o nome do curso que deseja adicionar?")
    return AD_NOME

async def add_course_nome(update: Update, context: CallbackContext):
    nome = update.message.text.strip()
    if not nome:
        await update.message.reply_text("❗ Nome inválido. Por favor, tente novamente.")
        return AD_NOME

    context.user_data["add_nome"] = nome

    # Cria o teclado inline para a escolha da área
    keyboard = [
        [InlineKeyboardButton(area.capitalize(), callback_data=area)]
        for area in AREAS_DISPONIVEIS
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔹 Escolha a área do curso:", reply_markup=reply_markup)
    return AD_AREA

async def add_course_area_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Responde ao callback
    area = query.data
    context.user_data["add_area"] = area

    await query.edit_message_text("🔹 Agora, envie o link do curso:")
    return AD_LINK

async def add_course_link(update: Update, context: CallbackContext):
    link = update.message.text.strip()
    nome = context.user_data["add_nome"]
    area = context.user_data["add_area"]

    course_data = {
        'nome': nome,
        'area': area,
        'link': link
    }
    courses_ref.push(course_data)

    await update.message.reply_text(
        f"✅ Curso '{nome}' adicionado com sucesso!\n"
        "Use /listar_cursos para visualizar todos os cursos."
    )
    return ConversationHandler.END

# --- Listar Cursos ---

async def list_courses(update: Update, context: CallbackContext):
    courses = courses_ref.get() or {}
    if not courses:
        await update.message.reply_text("❗ Nenhum curso cadastrado.")
        return

    # Agrupa cursos por área
    grouped = {}
    for curso_id, curso_info in courses.items():
        area = curso_info.get("area", "desconhecida")
        grouped.setdefault(area, []).append(curso_info["nome"])

    msg = "📚 *Cursos Disponíveis:*\n"
    for area, nomes in grouped.items():
        msg += f"\n🔸 *{area.capitalize()}*:\n"
        msg += "\n".join([f"  - {nome}" for nome in nomes]) + "\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# --- Busca de Curso com Fuzzy Matching ---

async def get_course_link(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text("❗ Uso correto: /curso <nome do curso>")
        return

    user_input = " ".join(context.args).strip()
    courses = courses_ref.get() or {}

    # Prepara a lista de cursos para a busca
    course_list = []
    original_names = {}
    for curso_id, curso_info in courses.items():
        original = curso_info["nome"]
        normalized = normalize_text(original)
        course_list.append(normalized)
        original_names[normalized] = original

    if not course_list:
        await update.message.reply_text("❗ Nenhum curso cadastrado.")
        return

    normalized_input = normalize_text(user_input)
    matches = process.extract(normalized_input, course_list, limit=3)
    filtered_matches = [match for match in matches if match[1] > 70]

    if not filtered_matches:
        await update.message.reply_text(f"❗ Nenhum curso semelhante a '{user_input}' encontrado.")
        return

    best_match = filtered_matches[0][0]
    original_name = original_names[best_match]

    for curso_id, curso_info in courses.items():
        if normalize_text(curso_info["nome"]) == best_match:
            await update.message.reply_text(
                f"🔍 Provavelmente você quis dizer:\n\n"
                f"🔗 *{original_name}*: {curso_info['link']}",
                parse_mode="Markdown"
            )
            return

    await update.message.reply_text(f"❗ Curso '{user_input}' não encontrado.")

# --- Editar Curso ---

async def edit_course_start(update: Update, context: CallbackContext):
    effective_message = get_effective_message(update)
    await effective_message.reply_text("🔹 Envie o nome do curso que deseja editar:")
    return ED_NOME

async def edit_course_nome(update: Update, context: CallbackContext):
    nome = update.message.text.strip()
    courses = courses_ref.get() or {}

    course_list = [curso_info["nome"] for curso_info in courses.values()]
    matches = process.extract(nome, course_list, limit=1)

    if not matches or matches[0][1] < 70:
        await update.message.reply_text("❗ Curso não encontrado.")
        return ConversationHandler.END

    best_match = matches[0][0]
    context.user_data["edit_nome"] = best_match

    await update.message.reply_text(
        f"🔹 Editando curso: *{best_match}*\n"
        "Qual campo deseja alterar? (digite *nome* ou *link*)",
        parse_mode="Markdown"
    )
    return ED_CAMPO

async def edit_course_field(update: Update, context: CallbackContext):
    field = update.message.text.strip().lower()
    if field not in ["nome", "link"]:
        await update.message.reply_text("❗ Opção inválida. Por favor, digite 'nome' ou 'link'.")
        return ED_CAMPO

    context.user_data["edit_field"] = field
    await update.message.reply_text(f"🔹 Digite o novo {field}:")
    return ED_VALOR

async def edit_course_value(update: Update, context: CallbackContext):
    new_value = update.message.text.strip()
    if not new_value:
        await update.message.reply_text("❗ Valor inválido. Operação cancelada.")
        return ConversationHandler.END

    old_name = context.user_data["edit_nome"]
    field = context.user_data["edit_field"]

    courses = courses_ref.get() or {}
    for curso_id, curso_info in courses.items():
        if curso_info["nome"] == old_name:
            update_data = {field: new_value}
            courses_ref.child(curso_id).update(update_data)
            await update.message.reply_text("✅ Curso atualizado com sucesso!")
            return ConversationHandler.END

    await update.message.reply_text("❗ Erro ao atualizar o curso.")
    return ConversationHandler.END

# --- Apagar Curso ---

async def delete_course_start(update: Update, context: CallbackContext):
    effective_message = get_effective_message(update)
    await effective_message.reply_text("🔹 Envie o nome do curso que deseja apagar:")
    return AP_NOME

async def delete_course_confirm(update: Update, context: CallbackContext):
    nome = update.message.text.strip()
    courses = courses_ref.get() or {}

    course_list = [curso_info["nome"] for curso_info in courses.values()]
    matches = process.extract(nome, course_list, limit=1)

    if not matches or matches[0][1] < 70:
        await update.message.reply_text("❗ Curso não encontrado.")
        return ConversationHandler.END

    best_match = matches[0][0]
    for curso_id, curso_info in courses.items():
        if curso_info["nome"] == best_match:
            courses_ref.child(curso_id).delete()
            await update.message.reply_text(f"✅ Curso '{best_match}' apagado com sucesso!")
            return ConversationHandler.END

    await update.message.reply_text("❗ Erro ao apagar o curso.")
    return ConversationHandler.END

# --- Cancelar Operação ---

async def cancel(update: Update, context: CallbackContext):
    effective_message = get_effective_message(update)
    await effective_message.reply_text("🚫 Operação cancelada.")
    return ConversationHandler.END

# --- Conversation Handlers ---

# Conversation para adicionar curso (usa CallbackQueryHandler para a área)
add_conv = ConversationHandler(
    entry_points=[CommandHandler("adicionar_curso", add_course_start)],
    states={
        AD_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_course_nome)],
        AD_AREA: [CallbackQueryHandler(add_course_area_callback, pattern="^(" + "|".join(AREAS_DISPONIVEIS) + ")$")],
        AD_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_course_link)],
    },
    fallbacks=[CommandHandler("cancelar", cancel)]
)

# Conversation para editar curso
edit_conv = ConversationHandler(
    entry_points=[CommandHandler("editar_curso", edit_course_start)],
    states={
        ED_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_course_nome)],
        ED_CAMPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_course_field)],
        ED_VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_course_value)],
    },
    fallbacks=[CommandHandler("cancelar", cancel)]
)

# Conversation para apagar curso
del_conv = ConversationHandler(
    entry_points=[CommandHandler("apagar_curso", delete_course_start)],
    states={
        AP_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_course_confirm)],
    },
    fallbacks=[CommandHandler("cancelar", cancel)]
)

# --- Configuração do Application ---

def main():
    # Crie o Application com o token do seu bot
    application = Application.builder().token("SEU_TOKEN_AQUI").build()

    # Registra os handlers de comando
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("listar_cursos", list_courses))
    application.add_handler(CommandHandler("curso", get_course_link))

    # Adiciona os ConversationHandlers
    application.add_handler(add_conv)
    application.add_handler(edit_conv)
    application.add_handler(del_conv)

    # Handler para os botões inline da tela inicial
    application.add_handler(CallbackQueryHandler(home_callback, pattern="^(adicionar_curso|listar_cursos|curso|editar_curso|apagar_curso)$"))

    # Inicia o bot
    application.run_polling()

if __name__ == '__main__':
    main()

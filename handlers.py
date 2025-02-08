from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler
)
from fuzzywuzzy import process
import unicodedata
import logging
import os
from firebase_config import initialize_firebase

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

# Opções de áreas
AREAS_DISPONIVEIS = [
    "humanas", "matematica", "ciencias da natureza", "redacao", "linguagens"
]

# Função auxiliar para normalizar texto
def normalize_text(text):
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    return text.lower().strip()

# --- Menu Principal com Botões ---
async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("➕ Adicionar Curso", callback_data="add_course")],
        [InlineKeyboardButton("📚 Listar Cursos", callback_data="list_courses")],
        [InlineKeyboardButton("🔍 Consultar Curso", callback_data="search_course")],
        [InlineKeyboardButton("✏️ Editar Curso", callback_data="edit_course")],
        [InlineKeyboardButton("❌ Apagar Curso", callback_data="delete_course")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 Olá! Escolha uma opção:", reply_markup=reply_markup)

# --- Callback Handler para Botões ---
async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()  # Responde ao callback (obrigatório)

    if query.data == "add_course":
        await query.edit_message_text("🔹 Qual é o nome do curso que deseja adicionar?")
        return AD_NOME
    elif query.data == "list_courses":
        await list_courses(update, context)
    elif query.data == "search_course":
        await query.edit_message_text("🔍 Digite o nome do curso que deseja consultar:")
        return ED_NOME
    elif query.data == "edit_course":
        await query.edit_message_text("🔹 Envie o nome do curso que deseja editar:")
        return ED_NOME
    elif query.data == "delete_course":
        await query.edit_message_text("🔹 Envie o nome do curso que deseja apagar:")
        return AP_NOME

# --- Adicionar Curso ---
async def add_course_nome(update: Update, context: CallbackContext):
    nome = update.message.text.strip()
    if not nome:
        await update.message.reply_text("❗ Nome inválido. Tente novamente.")
        return AD_NOME
    
    context.user_data["add_nome"] = nome

    # Cria botões para as áreas
    keyboard = [
        [InlineKeyboardButton(area.capitalize(), callback_data=f"area_{idx}")]
        for idx, area in enumerate(AREAS_DISPONIVEIS)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔹 Escolha a área do curso:", reply_markup=reply_markup)
    return AD_AREA

async def add_course_area(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    area_idx = int(query.data.split("_")[1])
    area = AREAS_DISPONIVEIS[area_idx]
    context.user_data["add_area"] = area

    await query.edit_message_text("🔹 Agora envie o link do curso:")
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
        "Use /listar_cursos para ver todos."
    )
    return ConversationHandler.END

# --- Listar Cursos ---
async def list_courses(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    courses = courses_ref.get() or {}
    if not courses:
        await query.edit_message_text("❗ Nenhum curso cadastrado.")
        return
    
    grouped = {}
    for curso_id, curso_info in courses.items():
        area = curso_info.get("area", "Desconhecida")
        grouped.setdefault(area, []).append(curso_info["nome"])
    
    msg = "📚 Cursos disponíveis:\n"
    for area, nomes in grouped.items():
        msg += f"\n🔸 {area.capitalize()}:\n"
        msg += "\n".join([f"  - {nome}" for nome in nomes]) + "\n"
    
    msg += "\nPara consultar o link, use: /curso <nome do curso>"
    await query.edit_message_text(msg)

# --- Busca de Curso com Fuzzy Matching ---
async def get_course_link(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text("❗ Uso: /curso <nome do curso>")
        return
    
    user_input = " ".join(context.args).strip()
    courses = courses_ref.get() or {}
    
    # Preparar lista para busca
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
    
    # Busca aproximada
    normalized_input = normalize_text(user_input)
    matches = process.extract(normalized_input, course_list, limit=3)
    filtered_matches = [match for match in matches if match[1] > 70]
    
    if not filtered_matches:
        await update.message.reply_text(f"❗ Nenhum curso similar a '{user_input}' encontrado.")
        return
    
    best_match = filtered_matches[0][0]
    original_name = original_names[best_match]
    
    # Buscar link correspondente
    for curso_id, curso_info in courses.items():
        if normalize_text(curso_info["nome"]) == best_match:
            await update.message.reply_text(f"🔍 Provavelmente você quis dizer:\n\n🔗 {original_name}: {curso_info['link']}")
            return
    
    await update.message.reply_text(f"❗ Curso '{user_input}' não encontrado.")

# --- Editar Curso ---
async def edit_course_nome(update: Update, context: CallbackContext):
    nome = update.message.text.strip()
    courses = courses_ref.get() or {}
    
    # Busca fuzzy
    course_list = [curso_info["nome"] for curso_info in courses.values()]
    matches = process.extract(nome, course_list, limit=1)
    
    if not matches or matches[0][1] < 70:
        await update.message.reply_text("❗ Curso não encontrado.")
        return ConversationHandler.END
    
    best_match = matches[0][0]
    context.user_data["edit_nome"] = best_match
    
    # Cria botões para escolher o campo a editar
    keyboard = [
        [InlineKeyboardButton("✏️ Editar Nome", callback_data="edit_name")],
        [InlineKeyboardButton("🔗 Editar Link", callback_data="edit_link")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"🔹 Editando curso: {best_match}\nO que deseja alterar?", reply_markup=reply_markup)
    return ED_CAMPO

async def edit_course_field(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    field = query.data.split("_")[1]  # "name" ou "link"
    context.user_data["edit_field"] = field

    await query.edit_message_text(f"🔹 Digite o novo {field}:")
    return ED_VALOR

async def edit_course_value(update: Update, context: CallbackContext):
    new_value = update.message.text.strip()
    old_name = context.user_data["edit_nome"]
    field = context.user_data["edit_field"]
    
    courses = courses_ref.get() or {}
    for curso_id, curso_info in courses.items():
        if curso_info["nome"] == old_name:
            update_data = {field: new_value}
            courses_ref.child(curso_id).update(update_data)
            await update.message.reply_text(f"✅ Curso atualizado com sucesso!")
            return ConversationHandler.END
    
    await update.message.reply_text("❗ Erro ao atualizar o curso.")
    return ConversationHandler.END

# --- Apagar Curso ---
async def delete_course_confirm(update: Update, context: CallbackContext):
    nome = update.message.text.strip()
    courses = courses_ref.get() or {}
    
    # Busca fuzzy para confirmação
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
    await update.message.reply_text("🚫 Operação cancelada.")
    return ConversationHandler.END

# --- Conversation Handlers ---
add_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(button_handler, pattern="^add_course$")],
    states={
        AD_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_course_nome)],
        AD_AREA: [CallbackQueryHandler(add_course_area, pattern="^area_")],
        AD_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_course_link)],
    },
    fallbacks=[CommandHandler("cancelar", cancel)]
)

edit_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(button_handler, pattern="^edit_course$")],
    states={
        ED_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_course_nome)],
        ED_CAMPO: [CallbackQueryHandler(edit_course_field, pattern="^edit_")],
        ED_VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_course_value)],
    },
    fallbacks=[CommandHandler("cancelar", cancel)]
)

del_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(button_handler, pattern="^delete_course$")],
    states={
        AP_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_course_confirm)],
    },
    fallbacks=[CommandHandler("cancelar", cancel)]
)

# --- Configuração do Bot ---
def main():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("Token do bot não configurado!")

    app = Application.builder().token(bot_token).build()
    
    # Adiciona handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(add_conv)
    app.add_handler(edit_conv)
    app.add_handler(del_conv)
    app.add_handler(CommandHandler("listar_cursos", list_courses))
    app.add_handler(CommandHandler("curso", get_course_link))
    
    print("🤖 Bot iniciado!")
    app.run_polling()

if __name__ == "__main__":
    main()

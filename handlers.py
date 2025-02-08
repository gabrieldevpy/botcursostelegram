from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    CallbackContext
)
from fuzzywuzzy import process
import unicodedata
import logging
import json
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

# --- Handlers de Comandos ---
async def start(update: Update, context: CallbackContext):
    msg = (
        "👋 Olá! Eu sou o bot de cursos. Comandos disponíveis:\n"
        "/adicionar_curso - Adicionar novo curso\n"
        "/listar_cursos - Listar todos os cursos\n"
        "/curso <nome> - Consultar link de um curso\n"
        "/editar_curso - Editar um curso\n"
        "/apagar_curso - Apagar um curso\n"
        "/cancelar - Cancelar operação"
    )
    await update.message.reply_text(msg)

# --- Adicionar Curso ---
async def add_course_start(update: Update, context: CallbackContext):
    await update.message.reply_text("🔹 Qual é o nome do curso que deseja adicionar?")
    return AD_NOME

async def add_course_nome(update: Update, context: CallbackContext):
    nome = update.message.text.strip()
    if not nome:
        await update.message.reply_text("❗ Nome inválido. Tente novamente.")
        return AD_NOME
    
    context.user_data["add_nome"] = nome
    await update.message.reply_text(
        "🔹 Escolha a área do curso:\n" +
        "\n".join([f"{idx+1}. {area.capitalize()}" for idx, area in enumerate(AREAS_DISPONIVEIS)])
    )
    return AD_AREA

async def add_course_area(update: Update, context: CallbackContext):
    try:
        escolha = int(update.message.text.strip()) - 1
        if 0 <= escolha < len(AREAS_DISPONIVEIS):
            area = AREAS_DISPONIVEIS[escolha]
            context.user_data["add_area"] = area
            await update.message.reply_text("🔹 Agora envie o link do curso:")
            return AD_LINK
        else:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❗ Opção inválida. Escolha um número entre 1 e 5.")
        return AD_AREA

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
    courses = courses_ref.get() or {}
    if not courses:
        await update.message.reply_text("❗ Nenhum curso cadastrado.")
        return
    
    grouped = {}
    for curso_id, curso_info in courses.items():
        area = curso_info.get("area", "Desconhecida")
        grouped.setdefault(area, []).append(curso_info["nome"])
    
    msg = "📚 Cursos disponíveis:\n"
    for area, nomes in grouped.items():
        msg += f"\n🔸 {area.capitalize()}:\n"
        msg += "\n".join([f"  - {nome}" for nome in nomes]) + "\n"
    
    await update.message.reply_text(msg)

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
async def edit_course_start(update: Update, context: CallbackContext):
    await update.message.reply_text("🔹 Envie o nome do curso que deseja editar:")
    return ED_NOME

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
    
    await update.message.reply_text(
        f"🔹 Editando curso: {best_match}\n"
        "O que deseja alterar? (nome/link)"
    )
    return ED_CAMPO

async def edit_course_field(update: Update, context: CallbackContext):
    field = update.message.text.strip().lower()
    if field not in ["nome", "link"]:
        await update.message.reply_text("❗ Opção inválida. Digite 'nome' ou 'link'.")
        return ED_CAMPO
    
    context.user_data["edit_field"] = field
    await update.message.reply_text(f"🔹 Digite o novo {field}:")
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
async def delete_course_start(update: Update, context: CallbackContext):
    await update.message.reply_text("🔹 Envie o nome do curso que deseja apagar:")
    return AP_NOME

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
    entry_points=[CommandHandler("adicionar_curso", add_course_start)],
    states={
        AD_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_course_nome)],
        AD_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_course_area)],
        AD_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_course_link)],
    },
    fallbacks=[CommandHandler("cancelar", cancel)]
)

edit_conv = ConversationHandler(
    entry_points=[CommandHandler("editar_curso", edit_course_start)],
    states={
        ED_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_course_nome)],
        ED_CAMPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_course_field)],
        ED_VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_course_value)],
    },
    fallbacks=[CommandHandler("cancelar", cancel)]
)

del_conv = ConversationHandler(
    entry_points=[CommandHandler("apagar_curso", delete_course_start)],
    states={
        AP_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_course_confirm)],
    },
    fallbacks=[CommandHandler("cancelar", cancel)]
)

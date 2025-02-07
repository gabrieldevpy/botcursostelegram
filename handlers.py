import logging
import json
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    CallbackContext
)
from firebase_config import initialize_firebase  # Firebase configurado
from firebase_admin import db

# Configuração do logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializa o Firebase
courses_ref = initialize_firebase().reference("cursos")

# Estados para o ConversationHandler de adicionar curso
AD_NOME, AD_AREA, AD_LINK = range(3)
# Estados para editar curso
ED_NOME, ED_CAMPO, ED_VALOR = range(3, 6)
# Estado para apagar curso (apenas nome)
AP_NOME = 6

# Opções de áreas
AREAS_DISPONIVEIS = [
    "humanas", "matematica", "ciencias da natureza", "redacao", "linguagens"
]

# /start: Mostra o menu principal
async def start(update: Update, context: CallbackContext):
    msg = (
        "👋 Olá! Eu sou o bot de cursos. Comandos disponíveis:\n"
        "/adicionar_curso - Adicionar um novo curso\n"
        "/listar_cursos - Listar todos os cursos\n"
        "/curso <nome> - Consultar o link de um curso\n"
        "/editar_curso - Editar um curso\n"
        "/apagar_curso - Apagar um curso\n"
        "/cancelar - Cancelar a operação"
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
        "🔹 Qual é a área do curso? Escolha uma das opções abaixo:\n"
        "\n".join([f"{idx+1}. {area.capitalize()}" for idx, area in enumerate(AREAS_DISPONIVEIS)])
    )
    return AD_AREA

async def add_course_area(update: Update, context: CallbackContext):
    try:
        escolha = int(update.message.text.strip()) - 1
        if 0 <= escolha < len(AREAS_DISPONIVEIS):
            area = AREAS_DISPONIVEIS[escolha]
            context.user_data["add_area"] = area
            await update.message.reply_text("🔹 Agora, envie o link do curso:")
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
    
    # Salva no Firebase
    course_data = {
        'nome': nome,
        'area': area,
        'link': link
    }
    courses_ref.push(course_data)

    await update.message.reply_text(
        f"✅ Curso '{nome}' da área '{area}' adicionado com sucesso!\n"
        "Use /listar_cursos para ver os cursos."
    )
    return ConversationHandler.END

# --- Listar Cursos e Consultar Link ---
async def list_courses(update: Update, context: CallbackContext):
    # Recupera cursos do Firebase
    courses = courses_ref.get() or {}
    if not courses:
        await update.message.reply_text("❗ Nenhum curso cadastrado.")
        return
    msg = "📚 Cursos disponíveis:\n"
    grouped = {}
    for curso_id, curso_info in courses.items():
        area = curso_info.get("area", "Desconhecida")
        grouped.setdefault(area, []).append(curso_info["nome"])

    for area, nomes in grouped.items():
        msg += f"\n🔸 {area.capitalize()}:\n"
        for nome in nomes:
            msg += f"  - {nome}\n"
    msg += "\nPara consultar o link, use: /curso <nome do curso>"
    await update.message.reply_text(msg)

# /curso: Retorna o link do curso (argumento obrigatório)
async def get_course_link(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text("❗ Uso: /curso <nome do curso>")
        return
    nome = " ".join(context.args).strip()
    
    # Busca curso no Firebase
    courses = courses_ref.get() or {}
    found_course = None
    for curso_id, curso_info in courses.items():
        if curso_info["nome"].lower() == nome.lower():
            found_course = curso_info
            break

    if found_course:
        link = found_course["link"]
        await update.message.reply_text(f"🔗 Link do curso '{nome}': {link}")
    else:
        await update.message.reply_text(f"❗ Curso '{nome}' não encontrado.")

# Certifique-se de substituir o token pelo correto ao testar o bot.

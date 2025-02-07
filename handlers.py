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
from firebase_config import initialize_firebase

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

courses_ref = initialize_firebase()

AD_NOME, AD_AREA, AD_LINK = range(3)
ED_NOME, ED_CAMPO, ED_VALOR = range(3, 6)
AP_NOME = 6

AREAS_DISPONIVEIS = [
    "humanas", "matematica", "ciencias da natureza", "redacao", "linguagens"
]

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

async def list_courses(update: Update, context: CallbackContext):
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

async def get_course_link(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text("❗ Uso: /curso <nome do curso>")
        return
    nome = " ".join(context.args).strip()
    
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

async def edit_course_start(update: Update, context: CallbackContext):
    await update.message.reply_text("🔹 Envie o nome do curso que deseja editar:")
    return ED_NOME

async def edit_course_nome(update: Update, context: CallbackContext):
    nome = update.message.text.strip()
    courses = courses_ref.get() or {}
    curso_encontrado = None
    for curso_id, curso_info in courses.items():
        if curso_info["nome"].lower() == nome.lower():
            curso_encontrado = curso_info
            break

    if not curso_encontrado:
        await update.message.reply_text("❗ Curso não encontrado.")
        return ConversationHandler.END

    context.user_data["edit_nome"] = nome
    await update.message.reply_text(
        "🔹 O que deseja editar? Responda 'nome' para alterar o nome ou 'link' para alterar o link."
    )
    return ED_CAMPO

async def edit_course_field(update: Update, context: CallbackContext):
    field = update.message.text.strip().lower()
    if field not in ["nome", "link"]:
        await update.message.reply_text("❗ Opção inválida. Digite 'nome' ou 'link'.")
        return ED_CAMPO
    context.user_data["edit_field"] = field
    await update.message.reply_text(f"🔹 Envie o novo {field} para o curso:")
    return ED_VALOR

async def edit_course_value(update: Update, context: CallbackContext):
    new_val = update.message.text.strip()
    nome = context.user_data["edit_nome"]
    field = context.user_data["edit_field"]
    
    courses = courses_ref.get() or {}
    for curso_id, curso_info in courses.items():
        if curso_info["nome"].lower() == nome.lower():
            if field == "nome":
                curso_info["nome"] = new_val
            else:
                curso_info["link"] = new_val
            courses_ref.child(curso_id).update(curso_info)
            break

    await update.message.reply_text(f"✅ Curso '{nome}' atualizado com sucesso!")
    return ConversationHandler.END

async def delete_course_start(update: Update, context: CallbackContext):
    await update.message.reply_text("🔹 Envie o nome do curso que deseja apagar:")
    return AP_NOME

async def delete_course_confirm(update: Update, context: CallbackContext):
    nome = update.message.text.strip()
    courses = courses_ref.get() or {}
    curso_encontrado = None
    for curso_id, curso_info in courses.items():
        if curso_info["nome"].lower() == nome.lower():
            curso_encontrado = curso_id
            break

    if curso_encontrado:
        courses_ref.child(curso_encontrado).delete()
        await update.message.reply_text(f"✅ Curso '{nome}' apagado com sucesso!")
    else:
        await update.message.reply_text(f"❗ Curso '{nome}' não encontrado.")
    
    await start(update, context)
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text("🚫 Operação cancelada.")
    return ConversationHandler.END

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

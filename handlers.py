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
from firebase_admin import firestore

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Inicializa Firebase
db = initialize_firebase()
courses_ref = db.collection("cursos")

# Função para normalizar textos (remover acentos e converter para minúsculas)
def normalize_text(text):
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    return text.lower().strip()

# Modifique a função get_course_link
async def get_course_link(update: Update, context: CallbackContext):
    if not context.args:
        await update.message.reply_text("❗ Uso: /curso <nome do curso>")
        return
    
    # Junta o input do usuário
    user_input = " ".join(context.args).strip()
    
    try:
        # Busca cursos no Firebase
        courses = {doc.id: doc.to_dict() for doc in courses_ref.stream()}
    except Exception as e:
        logging.error(f"Erro ao acessar o Firebase: {e}")
        await update.message.reply_text("❗ Erro ao acessar a base de dados. Tente novamente mais tarde.")
        return
    
    if not courses:
        await update.message.reply_text("❗ Nenhum curso cadastrado.")
        return
    
    # Cria lista de nomes normalizados
    course_names = []
    original_names = {}
    for curso_id, curso_info in courses.items():
        original_name = curso_info.get("nome", "Nome desconhecido")
        normalized = normalize_text(original_name)
        course_names.append(normalized)
        original_names[normalized] = original_name  # Mapeia nomes normalizados para originais
    
    # Encontra o melhor match usando fuzzy matching
    normalized_input = normalize_text(user_input)
    matches = process.extract(normalized_input, course_names, limit=3)
    
    # Filtra matches com score maior que 70
    good_matches = [match for match in matches if match[1] > 70]
    
    if not good_matches:
        await update.message.reply_text(f"❗ Nenhum curso parecido com '{user_input}' encontrado.")
        return
    
    # Exibir até 3 sugestões
    response = "🔍 Cursos semelhantes encontrados:\n\n"
    for match in good_matches:
        best_match = match[0]
        original_name = original_names[best_match]
        
        # Busca o curso original
        found_course = None
        for curso_id, curso_info in courses.items():
            if normalize_text(curso_info.get("nome", "")) == best_match:
                found_course = curso_info
                break

        link = found_course.get("link", "Sem link disponível") if found_course else "Sem link disponível"
        response += f"🔗 {original_name}: {link}\n"
    
    await update.message.reply_text(response)

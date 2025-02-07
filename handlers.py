from fuzzywuzzy import process
import unicodedata

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
    
    # Busca cursos no Firebase
    courses = courses_ref.get() or {}
    
    # Cria lista de nomes normalizados
    course_names = []
    original_names = {}
    for curso_id, curso_info in courses.items():
        original_name = curso_info["nome"]
        normalized = normalize_text(original_name)
        course_names.append(normalized)
        original_names[normalized] = original_name  # Mapeia nomes normalizados para originais
    
    if not course_names:
        await update.message.reply_text("❗ Nenhum curso cadastrado.")
        return
    
    # Encontra o melhor match usando fuzzy matching
    normalized_input = normalize_text(user_input)
    matches = process.extract(normalized_input, course_names, limit=3)
    
    # Filtra matches com score maior que 70
    good_matches = [match for match in matches if match[1] > 70]
    
    if not good_matches:
        await update.message.reply_text(f"❗ Nenhum curso parecido com '{user_input}' encontrado.")
        return
    
    # Pega o melhor match
    best_match = good_matches[0][0]
    original_name = original_names[best_match]
    
    # Busca o curso original
    found_course = None
    for curso_id, curso_info in courses.items():
        if normalize_text(curso_info["nome"]) == best_match:
            found_course = curso_info
            break
    
    if found_course:
        link = found_course["link"]
        await update.message.reply_text(f"🔍 Talvez você quis dizer:\n\n🔗 {original_name}: {link}")
    else:
        await update.message.reply_text(f"❗ Curso '{user_input}' não encontrado.")

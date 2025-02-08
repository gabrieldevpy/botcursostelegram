import os
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from handlers import add_conv, edit_conv, del_conv, start, list_courses, get_course_link, list_courses_button
from dotenv import load_dotenv

load_dotenv()

def main():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("Token do bot não configurado!")

    app = Application.builder().token(bot_token).build()
    
    # Adiciona os CommandHandlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("listar_cursos", list_courses))
    app.add_handler(CommandHandler("curso", get_course_link))
    
    # Adiciona o CallbackQueryHandler para o botão "listar_cursos"
    app.add_handler(CallbackQueryHandler(list_courses_button, pattern="^listar_cursos$"), group=-1)
    
    # Adiciona os ConversationHandlers
    app.add_handler(add_conv)
    app.add_handler(edit_conv)
    app.add_handler(del_conv)
    
    print("🤖 Bot iniciado!")
    app.run_polling()

if __name__ == "__main__":
    main()
import os
from telegram.ext import Application
from handlers import add_conv, edit_conv, del_conv, start, list_courses, get_course_link
from dotenv import load_dotenv

load_dotenv()

def main():
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("Token do bot não configurado!")

    app = Application.builder().token(bot_token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("listar_cursos", list_courses))
    app.add_handler(CommandHandler("curso", get_course_link))
    
    app.add_handlers([add_conv, edit_conv, del_conv])
    
    print("🤖 Bot iniciado!")
    app.run_polling()

if __name__ == "__main__":
    main()

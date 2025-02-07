import os
import json
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv

load_dotenv()

def initialize_firebase():
    try:
        # Cria um dicionário com as credenciais do Firebase
        firebase_config = {
            "type": os.getenv("FIREBASE_TYPE"),
            "project_id": os.getenv("FIREBASE_PROJECT_ID"),
            "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "client_id": os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
            "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
            "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
            "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL")
        }

        # Inicializa o Firebase
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://bottelegram-6937f-default-rtdb.firebaseio.com'
        })
        print("✅ Firebase inicializado com sucesso!")
        return db.reference('courses')
    except Exception as e:
        print(f"❌ Erro crítico no Firebase: {str(e)}")
        raise

# Teste de conexão com o Firebase
if __name__ == "__main__":
    ref = initialize_firebase()  # Corrigido: indentação aqui
    print("Conexão testada com sucesso!")
    print(ref.get())
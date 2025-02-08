FROM python:3.9-slim

# Define o diretório de trabalho
WORKDIR /app

# Copia os arquivos do projeto
COPY . /app

# Instala as dependências
RUN pip install --upgrade pip && pip install -r requirements.txt

# Define as variáveis de ambiente (ou configure-as via Railway)
# ENV VARIAVEL=valor

# Comando para rodar o script
CMD ["python", "update_courses.py"]

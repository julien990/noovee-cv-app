FROM python:3.11-slim

# Installer LibreOffice pour conversion PDF
RUN apt-get update && apt-get install -y \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier les fichiers
COPY requirements.txt .
COPY app_final.py .
COPY .env.example .env

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Créer les dossiers
RUN mkdir -p /app/PDF /app/backups /app/.streamlit

# Copier la config Streamlit
COPY .streamlit/config.toml /app/.streamlit/

# Exposer le port
EXPOSE 8501

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Lancer Streamlit
CMD ["streamlit", "run", "app_final.py", "--server.port=8501", "--server.address=0.0.0.0"]

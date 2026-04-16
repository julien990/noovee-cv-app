import streamlit as st
import os, re, json, time, base64
import pandas as pd
import urllib.request
import urllib.parse
import unicodedata
from datetime import datetime
from pptx import Presentation
# Assurez-vous d'avoir pypdf dans votre requirements.txt
from pypdf import PdfReader

# ---------------------------------------------------------------------------
# 1. CONFIGURATION ET CHEMINS (INDUSTRIALISÉS)
# ---------------------------------------------------------------------------
# On définit les dossiers par rapport à l'emplacement de l'application
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PATH_DOSSIER = os.path.join(BASE_DIR, "data")
PATH_PDF = os.path.join(PATH_DOSSIER, "PDF")
PATH_DB  = os.path.join(PATH_DOSSIER, "contacts_db.json")
NO_DATA  = "---"

# Création des dossiers si inexistants
os.makedirs(PATH_PDF, exist_ok=True)

# URLs APIs
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
GROQ_URL      = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL    = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
MISTRAL_URL   = "https://api.mistral.ai/v1/chat/completions"
OPENAI_URL    = "https://api.openai.com/v1/chat/completions"

def charger_toutes_les_cles():
    """Charge les clés depuis st.secrets (Cloud) ou variables d'env"""
    cles_a_charger = [
        "ANTHROPIC_API_KEY", "MISTRAL_API_KEY", "OPENAI_API_KEY", 
        "GEMINI_API_KEY", "GROQ_API_KEY"
    ]
    cles = {}
    for k in cles_a_charger:
        # Priorité à st.secrets (Streamlit Cloud), puis variables d'environnement
        val = st.secrets.get(k) or os.environ.get(k)
        if val:
            cles[k] = val
    return cles

# ---------------------------------------------------------------------------
# 2. LOGIQUE BASE DE DONNÉES (JSON LOCAL)
# ---------------------------------------------------------------------------
def charger_db():
    if os.path.exists(PATH_DB):
        try:
            with open(PATH_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def sauvegarder_db(db):
    with open(PATH_DB, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

# ---------------------------------------------------------------------------
# 3. EXTRACTION ET IA
# ---------------------------------------------------------------------------
def extraire_texte_pdf(chemin_pdf):
    texte = ""
    try:
        reader = PdfReader(chemin_pdf)
        for page in reader.pages:
            t = page.extract_text()
            if t: texte += t + "\n"
    except Exception as e:
        st.error(f"Erreur lecture PDF: {e}")
    return texte

def appel_ia(prompt, system_prompt, cles):
    """Version simplifiée pour l'exemple, priorise Anthropic ou OpenAI"""
    if "ANTHROPIC_API_KEY" in cles:
        headers = {
            "x-api-key": cles["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        data = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}]
        }
        req = urllib.request.Request(ANTHROPIC_URL, headers=headers, data=json.dumps(data).encode())
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            return res["content"][0]["text"]
    # ... (Ajouter les autres fallback si besoin)
    return None

# ---------------------------------------------------------------------------
# 4. INTERFACE STREAMLIT
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Noovee - Base de Contacts IA", layout="wide")

# Injection CSS pour le branding Noovee
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@700&family=DM+Sans:wght@400;500&display=swap');
    html, body, [class*="st-"] { font-family: 'DM Sans', sans-serif; }
    h1, h2, h3 { font-family: 'Syne', sans-serif; color: #093F28; }
    .stButton>button { background-color: #093F28; color: white; border-radius: 8px; }
    </style>
    """, unsafe_allow_value=True)

st.title("📂 Noovee - Base de Contacts IA")

cles = charger_toutes_les_cles()
if not cles:
    st.warning("⚠️ Aucune clé API configurée dans les Secrets Streamlit.")

tabs = st.tabs(["📊 Dashboard", "📤 Ajouter des CV", "🔍 Recherche & Filtres"])

# --- TAB 2: AJOUT DE CV ---
with tabs[1]:
    st.subheader("Uploader des CV (PDF)")
    uploaded_files = st.file_uploader("Choisir les fichiers PDF", type="pdf", accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("Lancer l'analyse IA"):
            db = charger_db()
            progress_bar = st.progress(0)
            
            for i, uploaded_file in enumerate(uploaded_files):
                # Sauvegarde temporaire du PDF
                nom_fichier = uploaded_file.name
                chemin_sauvegarde = os.path.join(PATH_PDF, nom_fichier)
                with open(chemin_sauvegarde, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Extraction & IA
                texte = extraire_texte_pdf(chemin_sauvegarde)
                # Note: Ici vous mettriez votre prompt
# config.py

COLORS = {
    "primary":    "#093F28",
    "secondary":  "#1A6B45",
    "background": "#F5F7FA",
    "indigo":     "#4F46E5",
    "card":       "#FFFFFF",
    "border":     "#E2E8F0",
    "text":       "#1A202C",
    "muted":      "#64748B",
}

# Accents conserves pour matcher avec ce qui est stocke en base
DOMAINES = [
    "Conformité/RGPD", "Finance", "Achats", "RH", "Marketing",
    "Commercial", "IT/Digital", "Data/BI", "Juridique", "Risk/Audit",
    "Supply Chain", "Transformation", "PMO", "Stratégie", "Comptabilité",
    "Cybersécurité", "Immobilier", "Communication", "RSE",
]

# ── Prompt extraction CV ───────────────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """Tu es un expert en extraction d'information de CVs professionnels.
Analyse le CV fourni et retourne UNIQUEMENT un objet JSON valide, sans markdown, sans commentaires.

Structure JSON :
{
  "prenom": "string ou null",
  "nom": "string ou null",
  "email": "string ou null",
  "telephone": "string ou null",
  "poste": "string ou null",
  "annees_experience": 0,
  "competences": ["1 a 15 termes courts 1-3 mots"],
  "domaines_fonctionnels": ["1 a 3 domaines parmi la liste"],
  "entreprises": [{"nom": "string", "secteur": "string", "annees": 0}],
  "experiences": [{"poste": "string", "entreprise": "string", "domaine": "string", "annees": 0, "mots_cles": []}]
}

Domaines autorises (1 a 3 max) :
Conformite/RGPD, Finance, Achats, RH, Marketing, Commercial, IT/Digital,
Data/BI, Juridique, Risk/Audit, Supply Chain, Transformation, PMO, Strategie, Comptabilite,
Cybersecurite, Immobilier, Communication, RSE

Regles : competences 1-3 mots, domaines max 3, null/0/[] si absent. JSON uniquement."""

EXTRACTION_USER_TEMPLATE = "CV a analyser :\n\n---\n{cv_text}\n---\n\nRetourne le JSON."


# ── Prompt extraction AO avec expansion semantique ────────────────────────────

AO_EXTRACTION_SYSTEM_PROMPT = """Tu es un expert en analyse d'appels d'offres et en matching de profils RH.
Analyse le texte fourni et retourne UNIQUEMENT un JSON valide, sans markdown.

Structure JSON attendue :
{
  "poste": "intitule du poste ou null",
  "resume": "resume du besoin en 1 phrase",
  "mots_cles": ["termes exacts issus du texte, 5 a 15 termes"],
  "mots_cles_expanded": ["liste etendue : mots_cles + synonymes + abreviations + termes equivalents, 20 a 50 termes"],
  "competences": ["competences techniques ou metier requises"],
  "domaines": ["domaines parmi la liste autorisee, max 3"],
  "annees_min": 0
}

IMPORTANT - Pour mots_cles_expanded :
Enrichis chaque terme avec tous ses synonymes, variantes et termes proches utilises dans les CVs.
Exemples :
- "RGPD" : ajouter DPO, conformite, CNIL, PIA, DPIA, registre des traitements, RoPA, donnees personnelles, data protection, privacy, protection des donnees, mise en conformite
- "transformation digitale" : ajouter digitalisation, change management, conduite du changement, transition numerique
- "finance" : ajouter controle de gestion, reporting, budget, P&L, tresorerie, comptabilite, DAF
- "immobilier" : ajouter property, foncier, asset management, transaction, bail, promotion immobiliere
- "risque" : ajouter risk management, audit, controle interne, conformite, cartographie des risques
- "juridique" : ajouter droit, contentieux, contrats, avocat, juriste, compliance
- "IT" : ajouter informatique, DSI, systemes d information, digital, tech, developpement
- "data" : ajouter BI, business intelligence, analytique, reporting, SQL, tableau de bord
- "achat" : ajouter procurement, sourcing, appel d offres, fournisseurs, negociation

Domaines autorises : Conformite/RGPD, Finance, Achats, RH, Marketing, Commercial, IT/Digital,
Data/BI, Juridique, Risk/Audit, Supply Chain, Transformation, PMO, Strategie, Comptabilite,
Cybersecurite, Immobilier, Communication, RSE

Retourne UNIQUEMENT le JSON."""

AO_EXTRACTION_USER_TEMPLATE = "Texte a analyser :\n\n---\n{ao_text}\n---\n\nRetourne le JSON avec expansion semantique."


# ── Prompt generation message ──────────────────────────────────────────────────

MESSAGE_SYSTEM_PROMPT = """Tu es un chasseur de tetes experimente chez Noovee.
Tu rediges des messages de prise de contact courts, directs et chaleureux pour des consultants independants.

Le message doit :
- Commencer par Bonjour [prenom],
- Presenter l opportunite en 2-3 phrases, sans jargon
- Mentionner le lieu et la duree si fournis
- Demander si la personne est disponible et interessee
- Rester sous 8 lignes au total
- Ne PAS inclure de signature

Canal WhatsApp : ton plus decontracte. Email : un peu plus formel.
Retourne UNIQUEMENT le texte du message."""

MESSAGE_USER_TEMPLATE = """Canal : {channel}
Prenom : {prenom}
Poste actuel : {poste}
Domaines : {domaines}

Contexte de la mission :
{context}

Redige le message."""

MAX_CV_TEXT_CHARS = 8000
MAX_COMPETENCES   = 15
MAX_DOMAINES      = 3

import os
CV_STORAGE_PATH = os.getenv("CV_STORAGE_PATH", "./cv_storage")

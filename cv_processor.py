# cv_processor.py

import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional

from config import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_TEMPLATE, MAX_CV_TEXT_CHARS, CV_STORAGE_PATH
from ai_providers import call_ai_json


def ensure_storage() -> Path:
    path = Path(CV_STORAGE_PATH)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_cv_file(uploaded_file) -> str:
    storage = ensure_storage()
    dest    = storage / uploaded_file.name
    counter = 1
    stem, suffix = Path(uploaded_file.name).stem, Path(uploaded_file.name).suffix
    while dest.exists():
        dest = storage / f"{stem}_{counter}{suffix}"
        counter += 1
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return dest.name


def delete_cv_file(filename: str):
    path = Path(CV_STORAGE_PATH) / filename
    if path.exists():
        path.unlink()


# ── Extraction texte selon le type de fichier ──────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> str:
    parts = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for page in doc:
        parts.append(page.get_text("text"))
    doc.close()
    return "\n".join(parts).strip()[:MAX_CV_TEXT_CHARS]


def extract_text_from_docx(file_bytes: bytes) -> str:
    import io
    from docx import Document
    doc   = Document(io.BytesIO(file_bytes))
    parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text.strip())
    # Inclure aussi les tableaux
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    parts.append(cell.text.strip())
    return "\n".join(parts)[:MAX_CV_TEXT_CHARS]


def extract_text_from_pptx(file_bytes: bytes) -> str:
    import io
    from pptx import Presentation
    prs   = Presentation(io.BytesIO(file_bytes))
    parts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                parts.append(shape.text.strip())
    return "\n".join(parts)[:MAX_CV_TEXT_CHARS]


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """Extrait le texte selon l'extension du fichier."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in (".docx", ".doc"):
        return extract_text_from_docx(file_bytes)
    elif ext in (".pptx", ".ppt"):
        return extract_text_from_pptx(file_bytes)
    else:
        raise ValueError(f"Format non supporte : {ext}")


# ── Analyse IA ─────────────────────────────────────────────────────────────────

def analyze_cv_with_ai(cv_text: str) -> tuple:
    if not cv_text.strip():
        raise ValueError("Fichier vide ou non lisible.")
    user_prompt = EXTRACTION_USER_TEMPLATE.format(cv_text=cv_text)
    data, provider = call_ai_json(EXTRACTION_SYSTEM_PROMPT, user_prompt, preferred_provider="mistral")
    return _clean(data), provider


def _clean(data: dict) -> dict:
    from config import MAX_COMPETENCES, MAX_DOMAINES, DOMAINES

    for field in ("nom", "prenom", "email", "telephone", "poste"):
        val = data.get(field)
        data[field] = val.strip() if isinstance(val, str) and val.strip() else None

    try:
        data["annees_experience"] = max(0, int(data.get("annees_experience") or 0))
    except Exception:
        data["annees_experience"] = 0

    comp = data.get("competences", [])
    data["competences"] = [str(c).strip() for c in (comp if isinstance(comp, list) else [])][:MAX_COMPETENCES]

    dom = data.get("domaines_fonctionnels", [])
    data["domaines_fonctionnels"] = [d for d in (dom if isinstance(dom, list) else []) if d in DOMAINES][:MAX_DOMAINES]

    ent = data.get("entreprises", [])
    data["entreprises"] = [
        {"nom": str(e.get("nom","")).strip(), "secteur": str(e.get("secteur","")).strip(), "annees": max(0, int(e.get("annees",0) or 0))}
        for e in (ent if isinstance(ent, list) else []) if isinstance(e, dict)
    ]

    exp = data.get("experiences", [])
    data["experiences"] = [
        {"poste": str(x.get("poste","")).strip(), "entreprise": str(x.get("entreprise","")).strip(),
         "domaine": str(x.get("domaine","")).strip(), "annees": max(0, int(x.get("annees",0) or 0)),
         "mots_cles": [str(m).strip() for m in (x.get("mots_cles",[]) if isinstance(x.get("mots_cles"), list) else [])]}
        for x in (exp if isinstance(exp, list) else []) if isinstance(x, dict)
    ]
    return data


# ── Pipeline upload ────────────────────────────────────────────────────────────

def process_uploaded_cv(uploaded_file) -> tuple:
    """
    Pipeline complet pour un fichier uploade (PDF, DOCX, PPTX).
    Retourne : (donnees_extraites, nom_fichier_sauve, provider_utilise)
    """
    filename   = save_cv_file(uploaded_file)
    file_bytes = uploaded_file.getbuffer()
    cv_text    = extract_text_from_file(bytes(file_bytes), uploaded_file.name)

    if not cv_text.strip():
        raise ValueError("Le fichier ne contient pas de texte lisible.")

    data, provider = analyze_cv_with_ai(cv_text)
    data["texte_brut"]  = cv_text
    data["cv_filename"] = filename
    return data, filename, provider


# ── Scan automatique au demarrage ──────────────────────────────────────────────

def scan_and_import_new_cvs() -> dict:
    import database as db
    storage   = ensure_storage()
    tracked   = db.get_tracked_filenames()
    all_files = [
        f for f in storage.iterdir()
        if f.suffix.lower() in (".pdf", ".docx", ".doc", ".pptx", ".ppt")
        and f.name not in tracked
    ]
    report = {"imported": [], "failed": [], "skipped": len(tracked)}

    for file_path in sorted(all_files):
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            cv_text = extract_text_from_file(file_bytes, file_path.name)
            if not cv_text.strip():
                report["failed"].append({"filename": file_path.name, "error": "Fichier vide ou non lisible"})
                continue
            data, provider = analyze_cv_with_ai(cv_text)
            data["texte_brut"]  = cv_text
            data["cv_filename"] = file_path.name
            db.insert_contact(data)
            name = f"{data.get('prenom') or ''} {data.get('nom') or ''}".strip() or file_path.name
            report["imported"].append({"filename": file_path.name, "name": name, "provider": provider})
        except Exception as e:
            report["failed"].append({"filename": file_path.name, "error": str(e)})

    return report

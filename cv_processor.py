# cv_processor.py

import fitz
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


def extract_text_from_pdf(file_bytes: bytes) -> str:
    parts = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for page in doc:
        parts.append(page.get_text("text"))
    doc.close()
    return "\n".join(parts).strip()[:MAX_CV_TEXT_CHARS]


def analyze_cv_with_ai(cv_text: str) -> tuple:
    if not cv_text.strip():
        raise ValueError("PDF vide ou non lisible.")
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


def process_uploaded_cv(uploaded_file) -> tuple:
    filename       = save_cv_file(uploaded_file)
    cv_text        = extract_text_from_pdf(uploaded_file.getbuffer())
    data, provider = analyze_cv_with_ai(cv_text)
    data["texte_brut"]  = cv_text
    data["cv_filename"] = filename
    return data, filename, provider


def scan_and_import_new_cvs() -> dict:
    import database as db
    storage  = ensure_storage()
    tracked  = db.get_tracked_filenames()
    new_files = [f for f in sorted(storage.glob("*.pdf")) if f.name not in tracked]
    report   = {"imported": [], "failed": [], "skipped": len(tracked)}

    for pdf_path in new_files:
        try:
            with open(pdf_path, "rb") as f:
                file_bytes = f.read()
            cv_text = extract_text_from_pdf(file_bytes)
            if not cv_text.strip():
                report["failed"].append({"filename": pdf_path.name, "error": "PDF vide ou non lisible"})
                continue
            data, provider = analyze_cv_with_ai(cv_text)
            data["texte_brut"]  = cv_text
            data["cv_filename"] = pdf_path.name
            db.insert_contact(data)
            name = f"{data.get('prenom') or ''} {data.get('nom') or ''}".strip() or pdf_path.name
            report["imported"].append({"filename": pdf_path.name, "name": name, "provider": provider})
        except Exception as e:
            report["failed"].append({"filename": pdf_path.name, "error": str(e)})

    return report

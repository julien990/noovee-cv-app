# scoring.py

import re
import unicodedata
from typing import List

from config import AO_EXTRACTION_SYSTEM_PROMPT, AO_EXTRACTION_USER_TEMPLATE
from ai_providers import call_ai_json


# ── Normalisation (accents + casse) ───────────────────────────────────────────

def normalize(s: str) -> str:
    """Supprime les accents et met en minuscules pour une comparaison robuste."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").lower().strip()


# ── Mots vides ─────────────────────────────────────────────────────────────────

STOP_WORDS = {
    "a", "au", "aux", "ce", "ces", "cet", "cette", "d", "de", "des",
    "du", "en", "et", "je", "la", "le", "les", "ma", "me", "mes",
    "mon", "ou", "par", "pour", "que", "qui", "sa", "se", "ses",
    "si", "son", "sur", "ta", "te", "tes", "ton", "tu", "un", "une", "y",
    "an", "ans", "annee", "annees",
    "environ", "minimum", "min", "max", "maximum",
    "experience", "experiences",
    "recherche", "cherche", "besoin",
    "avec", "dans", "avoir", "etre", "fait", "plus", "tres",
    "idealement", "solide", "bonne", "bon", "fort",
    "profil", "candidat", "personne", "souhait",
}


def clean_keywords(words: List[str]) -> List[str]:
    result = []
    for w in words:
        w_clean = normalize(w).rstrip("'")
        if w_clean not in STOP_WORDS and len(w_clean) >= 3 and not w_clean.isdigit():
            result.append(w.strip())
    return result


def extract_annees_from_query(query: str) -> int:
    for pattern in [r"(\d+)\s*ans?\s*d['\s]?exp", r"(\d+)\s*ans?\s*minimum", r"(\d+)\s*ans?\b"]:
        m = re.search(pattern, query.lower())
        if m:
            return int(m.group(1))
    return 0


# ── Extraction criteres depuis texte AO ───────────────────────────────────────

def extract_criteria_from_text(text: str) -> dict:
    user_prompt = AO_EXTRACTION_USER_TEMPLATE.format(ao_text=text[:6000])
    criteria, provider = call_ai_json(
        AO_EXTRACTION_SYSTEM_PROMPT, user_prompt, preferred_provider="mistral"
    )
    criteria.setdefault("mots_cles", [])
    criteria.setdefault("mots_cles_expanded", [])
    criteria.setdefault("competences", [])
    criteria.setdefault("domaines", [])
    criteria.setdefault("annees_min", 0)
    criteria.setdefault("poste", None)
    criteria.setdefault("resume", "")
    criteria["_provider"] = provider

    if not criteria["mots_cles_expanded"]:
        criteria["mots_cles_expanded"] = criteria["mots_cles"]

    return criteria


# ── Matching ───────────────────────────────────────────────────────────────────

def _match_count(text: str, keywords: List[str]) -> int:
    """Nombre de mots-cles distincts trouves dans le texte (normalise)."""
    if not text or not keywords:
        return 0
    text_norm = normalize(text)
    return sum(1 for kw in keywords if kw.strip() and normalize(kw) in text_norm)


def _domains_match(contact_domains: List[str], ao_domains: List[str]) -> int:
    """Comparaison domaines insensible aux accents et a la casse."""
    contact_norm = [normalize(d) for d in contact_domains]
    return sum(1 for d in ao_domains if normalize(d) in contact_norm)


# ── Scoring ────────────────────────────────────────────────────────────────────

def score_contact(contact: dict, criteria: dict) -> dict:
    """
    Score un contact par rapport aux criteres d'un AO.

    Formule competences :
      - Mots-cles EXACTS (du texte AO)  : 70% du score
      - Mots-cles EXPANDED (synonymes)   : 30% du score
    Chaque partie a son propre denominateur -> pas de dilution.

    Comparaisons insensibles aux accents et a la casse.
    """
    kw_exact    = criteria.get("mots_cles", [])
    kw_expanded = criteria.get("mots_cles_expanded", []) or kw_exact
    comp_req    = criteria.get("competences", [])
    domaines_ao = criteria.get("domaines", [])
    annees_min  = int(criteria.get("annees_min") or 0)

    # Deduplication
    all_exact    = list(set(kw_exact + comp_req))
    all_expanded = list(set(kw_expanded + comp_req))

    # ── Texte du contact ───────────────────────────────────────────────────
    contact_comp = " ".join(contact.get("competences", []))
    contact_brut = contact.get("texte_brut", "") or ""
    contact_exp  = " ".join(
        f"{e.get('poste','')} {e.get('domaine','')} {' '.join(e.get('mots_cles', []))}"
        for e in contact.get("experiences", [])
    )
    contact_ent  = " ".join(
        f"{e.get('nom','')} {e.get('secteur','')}"
        for e in contact.get("entreprises", [])
    )
    full_text = f"{contact_comp} {contact_brut} {contact_exp} {contact_ent}"

    # ── D2 : Score competences ─────────────────────────────────────────────

    # Partie 1 : mots-cles exacts (70%)
    # Competences declarees : poids x3 | Texte complet : poids x1
    if all_exact:
        found_exact_comp = _match_count(contact_comp, all_exact)
        found_exact_full = _match_count(full_text,    all_exact)
        ratio_exact      = (found_exact_comp * 3 + found_exact_full) / (len(all_exact) * 4)
    else:
        ratio_exact = 0.5

    # Partie 2 : mots-cles expanded / synonymes (30%)
    if all_expanded and all_expanded != all_exact:
        found_exp_full = _match_count(full_text, all_expanded)
        ratio_expanded = found_exp_full / len(all_expanded)
    else:
        ratio_expanded = ratio_exact

    score_competences = min(100, (ratio_exact * 0.70 + ratio_expanded * 0.30) * 100)

    # Mots trouves pour l'affichage (termes exacts en priorite)
    mots_trouves = [kw for kw in kw_exact if normalize(kw) in normalize(full_text)]
    # Completer avec des termes expanded non redondants
    exp_bonus = [
        kw for kw in kw_expanded
        if normalize(kw) in normalize(full_text) and kw not in kw_exact
    ][:4]
    mots_trouves = mots_trouves + exp_bonus

    # ── D3 : Score anciennete ──────────────────────────────────────────────
    annees_contact = int(contact.get("annees_experience") or 0)
    if annees_min > 0:
        score_anciennete = min(100, (annees_contact / annees_min) * 100)
    else:
        score_anciennete = min(100, annees_contact * 10)

    # ── D1 : Score domaine (insensible aux accents) ────────────────────────
    contact_domaines = contact.get("domaines_fonctionnels", [])
    nb_match_dom     = _domains_match(contact_domaines, domaines_ao) if domaines_ao else 0
    bonus_domaine    = nb_match_dom > 0

    if domaines_ao:
        score_domaine = (nb_match_dom / len(domaines_ao)) * 100
        years_in_dom  = sum(
            e.get("annees", 0) for e in contact.get("experiences", [])
            if any(normalize(e.get("domaine","")) == normalize(d) for d in domaines_ao)
        )
        profondeur    = min(100, years_in_dom * 15)
        score_domaine = score_domaine * 0.5 + profondeur * 0.5
    else:
        score_domaine = 50

    # ── Total ──────────────────────────────────────────────────────────────
    total = (
        score_competences * 0.50 +
        score_anciennete  * 0.25 +
        score_domaine     * 0.25
    )
    if bonus_domaine:
        total = min(100, total + 8)

    return {
        "total":         round(total),
        "competences":   round(score_competences),
        "anciennete":    round(score_anciennete),
        "domaine":       round(score_domaine),
        "bonus_domaine": bonus_domaine,
        "mots_trouves":  mots_trouves,
    }


def rank_contacts(contacts: List[dict], criteria: dict, top_n: int = None) -> List[dict]:
    results = []
    for c in contacts:
        scores = score_contact(c, criteria)
        if scores["total"] > 0:
            results.append({**c, "score": scores})
    results.sort(key=lambda x: x["score"]["total"], reverse=True)
    return results[:top_n] if top_n else results


def keyword_criteria(query: str) -> dict:
    raw_words  = [m.strip() for m in re.split(r"[\s,;]+", query) if m.strip()]
    clean_kw   = clean_keywords(raw_words)
    annees_min = extract_annees_from_query(query)
    return {
        "mots_cles":          clean_kw,
        "mots_cles_expanded": clean_kw,
        "competences":        [],
        "domaines":           [],
        "annees_min":         annees_min,
    }

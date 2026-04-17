# scoring.py

import re
import math
import unicodedata
from typing import List

from config import AO_EXTRACTION_SYSTEM_PROMPT, AO_EXTRACTION_USER_TEMPLATE
from ai_providers import call_ai_json


# ── Normalisation ──────────────────────────────────────────────────────────────

def normalize(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").lower().strip()


# ── Mots vides + villes ────────────────────────────────────────────────────────

STOP_WORDS = {
    # Articles, prepositions
    "a", "au", "aux", "ce", "ces", "cet", "cette", "d", "de", "des",
    "du", "en", "et", "je", "la", "le", "les", "ma", "me", "mes",
    "mon", "ou", "par", "pour", "que", "qui", "sa", "se", "ses",
    "si", "son", "sur", "ta", "te", "tes", "ton", "tu", "un", "une", "y",
    # Temps et duree
    "an", "ans", "annee", "annees", "mois",
    "environ", "minimum", "min", "max", "maximum",
    "experience", "experiences",
    # Qualificatifs generiques
    "recherche", "cherche", "besoin", "avec", "dans", "avoir", "etre",
    "fait", "plus", "tres", "idealement", "solide", "bonne", "bon", "fort",
    "profil", "candidat", "personne", "souhait",
    # Villes et lieux communs
    "paris", "lyon", "marseille", "bordeaux", "toulouse", "nantes", "lille",
    "strasbourg", "nice", "rennes", "grenoble", "montpellier", "tours",
    "france", "idf", "remote", "teletravail", "hybride", "presentiel",
    "region", "ville", "lieu",
}


def clean_keywords(words: List[str]) -> List[str]:
    """Filtre les mots vides, villes et chiffres. Ne garde que les termes metier."""
    result = []
    for w in words:
        w_clean = normalize(w).rstrip("'")
        if (
            w_clean not in STOP_WORDS
            and len(w_clean) >= 3
            and not w_clean.isdigit()
            and not re.match(r"^\d+$", w_clean)
        ):
            result.append(w.strip())
    return result


def extract_annees_from_query(query: str) -> int:
    for pattern in [r"(\d+)\s*ans?\s*d['\s]?exp", r"(\d+)\s*ans?\s*minimum", r"(\d+)\s*ans?\b"]:
        m = re.search(pattern, query.lower())
        if m:
            return int(m.group(1))
    return 0


# ── Courbe non-lineaire ────────────────────────────────────────────────────────

def nonlinear_score(ratio: float) -> float:
    """
    0%  -> 0
    20% -> 50
    40% -> 75
    60% -> 88
    100% -> 100
    """
    if ratio <= 0: return 0.0
    if ratio >= 1: return 100.0
    k = 4.0
    return min(100.0, 100 * (1 - math.exp(-k * ratio)) / (1 - math.exp(-k)))


# ── Extraction criteres AO ─────────────────────────────────────────────────────

def extract_criteria_from_text(text: str) -> dict:
    user_prompt = AO_EXTRACTION_USER_TEMPLATE.format(ao_text=text[:6000])
    criteria, provider = call_ai_json(AO_EXTRACTION_SYSTEM_PROMPT, user_prompt, preferred_provider="mistral")
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
    if not text or not keywords: return 0
    text_norm = normalize(text)
    return sum(1 for kw in keywords if kw.strip() and normalize(kw) in text_norm)


def _domains_match(contact_domains: List[str], ao_domains: List[str]) -> int:
    contact_norm = [normalize(d) for d in contact_domains]
    return sum(1 for d in ao_domains if normalize(d) in contact_norm)


# ── D4 : Multiplicateur profondeur ────────────────────────────────────────────

def compute_experience_multiplier(contact: dict, all_keywords: List[str]) -> tuple:
    if not all_keywords: return 1.0, 0, []
    matching_exps = []
    for exp in contact.get("experiences", []):
        exp_text = " ".join([
            exp.get("poste", ""), exp.get("domaine", ""),
            exp.get("entreprise", ""), " ".join(exp.get("mots_cles", [])),
        ])
        n = _match_count(exp_text, all_keywords)
        if n > 0:
            matching_exps.append({
                "poste": exp.get("poste", ""), "entreprise": exp.get("entreprise", ""),
                "annees": exp.get("annees", 0), "matches": n,
            })
    nb         = len(matching_exps)
    multiplier = 1.0 + min(0.50, nb * 0.10)
    return multiplier, nb, matching_exps


# ── Scoring principal ──────────────────────────────────────────────────────────

def score_contact(contact: dict, criteria: dict) -> dict:
    """
    D2 competences : 50%
    D3 anciennete  : 20%
    D1 domaine     : 30% (poids augmente — cle pour eviter les faux positifs)
    D4 profondeur  : multiplicateur x1.0 a x1.5 sur D2

    Pour la recherche locale (keyword_criteria) :
    - On ne score que sur competences declarees + experiences
    - Le texte brut est IGNORE pour eviter les faux positifs
    - Les domaines fonctionnels sont fortement penalises si pas de match
    """
    kw_exact    = criteria.get("mots_cles", [])
    kw_expanded = criteria.get("mots_cles_expanded", []) or kw_exact
    comp_req    = criteria.get("competences", [])
    domaines_ao = criteria.get("domaines", [])
    annees_min  = int(criteria.get("annees_min") or 0)
    use_brut    = criteria.get("use_texte_brut", True)  # False pour recherche locale

    all_exact    = list(set(kw_exact + comp_req))
    all_expanded = list(set(kw_expanded + comp_req))

    # ── Textes du contact ──────────────────────────────────────────────────
    contact_comp = " ".join(contact.get("competences", []))
    contact_brut = contact.get("texte_brut", "") or "" if use_brut else ""
    contact_exp  = " ".join(
        f"{e.get('poste','')} {e.get('domaine','')} {' '.join(e.get('mots_cles', []))}"
        for e in contact.get("experiences", [])
    )
    contact_ent = " ".join(
        f"{e.get('nom','')} {e.get('secteur','')}"
        for e in contact.get("entreprises", [])
    )

    # Texte complet = competences + experiences + entreprises (+ brut si AO)
    full_text = f"{contact_comp} {contact_exp} {contact_ent}"
    if use_brut:
        full_text += f" {contact_brut}"

    # ── D2 : Score competences ─────────────────────────────────────────────
    if all_exact:
        # Competences declarees : poids fort (x3)
        # Texte experiences/entreprises : poids moyen (x1)
        found_comp = _match_count(contact_comp, all_exact)
        found_full = _match_count(full_text, all_exact)
        ratio_exact = (found_comp * 3 + found_full) / (len(all_exact) * 4)
    else:
        ratio_exact = 0.5

    if all_expanded and all_expanded != all_exact and use_brut:
        found_exp_full = _match_count(full_text, all_expanded)
        ratio_expanded = found_exp_full / len(all_expanded)
    else:
        ratio_expanded = ratio_exact

    ratio_combined    = ratio_exact * 0.70 + ratio_expanded * 0.30
    score_comp_base   = nonlinear_score(ratio_combined)

    # ── D4 : Multiplicateur profondeur ─────────────────────────────────────
    multiplier, nb_exp_match, exp_detail = compute_experience_multiplier(contact, all_exact or all_expanded)
    score_competences = min(100, score_comp_base * multiplier)

    # Mots trouves pour affichage
    mots_trouves = [kw for kw in kw_exact if normalize(kw) in normalize(full_text)]
    if use_brut:
        exp_bonus = [kw for kw in kw_expanded if normalize(kw) in normalize(full_text) and kw not in kw_exact][:4]
        mots_trouves += exp_bonus

    # ── D3 : Anciennete ────────────────────────────────────────────────────
    annees_contact = int(contact.get("annees_experience") or 0)
    if annees_min > 0:
        score_anciennete = min(100, (annees_contact / annees_min) * 100)
    else:
        score_anciennete = min(100, annees_contact * 10)

    # ── D1 : Domaine (poids augmente a 30%) ───────────────────────────────
    contact_domaines = contact.get("domaines_fonctionnels", [])
    nb_match_dom     = _domains_match(contact_domaines, domaines_ao) if domaines_ao else 0
    bonus_domaine    = nb_match_dom > 0

    if domaines_ao:
        score_domaine = (nb_match_dom / len(domaines_ao)) * 100
        years_in_dom  = sum(
            e.get("annees", 0) for e in contact.get("experiences", [])
            if any(normalize(e.get("domaine", "")) == normalize(d) for d in domaines_ao)
        )
        profondeur    = min(100, years_in_dom * 15)
        score_domaine = score_domaine * 0.5 + profondeur * 0.5
    else:
        score_domaine = 50

    # ── PENALITE : pas de domaine match + recherche locale ────────────────
    # Si on cherche "RGPD" et que le contact n'a pas "Conformite/RGPD" dans ses domaines,
    # on applique une penalite sur le score competences pour eviter les faux positifs
    if domaines_ao and nb_match_dom == 0 and not use_brut:
        score_competences = score_competences * 0.4  # Penalite forte

    # ── Total (poids reequilibres) ─────────────────────────────────────────
    total = (
        score_competences * 0.50 +
        score_anciennete  * 0.20 +
        score_domaine     * 0.30   # Domaine pese plus (30% au lieu de 25%)
    )
    if bonus_domaine:
        total = min(100, total + 8)

    return {
        "total":           round(total),
        "competences":     round(score_competences),
        "comp_base":       round(score_comp_base),
        "anciennete":      round(score_anciennete),
        "domaine":         round(score_domaine),
        "bonus_domaine":   bonus_domaine,
        "mots_trouves":    mots_trouves,
        "multiplicateur":  round(multiplier, 2),
        "nb_exp_match":    nb_exp_match,
        "exp_detail":      exp_detail,
    }


def rank_contacts(contacts: List[dict], criteria: dict, top_n: int = None) -> List[dict]:
    results = []
    for c in contacts:
        scores = score_contact(c, criteria)
        if scores["total"] > 0:
            results.append({**c, "score": scores})
    results.sort(key=lambda x: x["score"]["total"], reverse=True)
    return results[:top_n] if top_n else results


# ── Criteres depuis mot-cle (sans IA) ─────────────────────────────────────────

def keyword_criteria(query: str) -> dict:
    """
    Recherche locale sans IA.
    - Filtre les villes et mots vides
    - N'utilise PAS le texte brut pour scorer (evite les faux positifs)
    - Tente de detecter le domaine depuis les mots-cles
    """
    raw_words  = [m.strip() for m in re.split(r"[\s,;]+", query) if m.strip()]
    clean_kw   = clean_keywords(raw_words)
    annees_min = extract_annees_from_query(query)

    # Detection automatique du domaine depuis la requete
    domaines_detectes = _detect_domaines_from_query(query)

    return {
        "mots_cles":          clean_kw,
        "mots_cles_expanded": clean_kw,
        "competences":        [],
        "domaines":           domaines_detectes,
        "annees_min":         annees_min,
        "use_texte_brut":     False,  # Cle pour desactiver le texte brut
    }


# ── Detection automatique du domaine ──────────────────────────────────────────

DOMAINE_KEYWORDS = {
    "Conformite/RGPD": ["rgpd", "dpo", "cnil", "conformite", "gdpr", "donnees personnelles", "pia", "dpia", "privacy"],
    "Finance":         ["finance", "financier", "daf", "tresorerie", "budget", "p&l", "reporting financier"],
    "Achats":          ["achat", "achats", "procurement", "sourcing", "appel offres"],
    "RH":              ["rh", "ressources humaines", "recrutement", "paie", "sirh", "grh"],
    "Marketing":       ["marketing", "communication", "digital marketing", "seo", "sem"],
    "Commercial":      ["commercial", "vente", "business development", "crm", "sales"],
    "IT/Digital":      ["it", "informatique", "dsi", "digital", "developpement", "tech"],
    "Data/BI":         ["data", "bi", "business intelligence", "sql", "analytique", "tableau"],
    "Juridique":       ["juridique", "droit", "avocat", "juriste", "contrat", "contentieux"],
    "Risk/Audit":      ["audit", "risk", "risque", "controle interne", "compliance"],
    "Supply Chain":    ["supply chain", "logistique", "transport", "stock", "entrepot"],
    "Transformation":  ["transformation", "change management", "conduite changement"],
    "PMO":             ["pmo", "chef projet", "project manager", "gestion projet"],
    "Strategie":       ["strategie", "strategy", "conseil", "consulting"],
    "Comptabilite":    ["comptable", "comptabilite", "tresorerie", "bilan"],
    "Cybersecurite":   ["cybersecurite", "ssi", "securite informatique", "pentest"],
    "Immobilier":      ["immobilier", "asset management", "foncier", "bail", "property"],
    "Communication":   ["communication", "relations presse", "rp", "media"],
    "RSE":             ["rse", "esg", "developpement durable", "impact"],
}

def _detect_domaines_from_query(query: str) -> List[str]:
    query_norm = normalize(query)
    detected   = []
    for domaine, keywords in DOMAINE_KEYWORDS.items():
        if any(kw in query_norm for kw in keywords):
            detected.append(domaine)
    return detected[:3]

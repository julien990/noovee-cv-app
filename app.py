import streamlit as st
import os, re, json, subprocess, shutil
import urllib.request
import pandas as pd
import urllib.parse
from datetime import datetime
from pptx import Presentation

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
PATH_DOSSIER = os.environ.get(
    "NOOVEE_CV_PATH",
    "/Users/juliensac/Library/CloudStorage/GoogleDrive-julien@miint.pro/Drive partag\u00e9s/Noovee - CV"
)
PATH_PDF = os.path.join(PATH_DOSSIER, "PDF")
PATH_DB  = os.path.join(PATH_DOSSIER, "contacts_db.json")
NO_TEL   = "---"

CORRECTIONS_TEL = {
    "20260407 - CV ASO TEST - Neoli": "0640275779",
}

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


# ---------------------------------------------------------------------------
# EXTRACTION IA
# ---------------------------------------------------------------------------
def extraire_infos_ia(texte_cv):
    if not texte_cv or len(texte_cv) < 20:
        return None, None, None
    try:
        prompt = (
            "Voici le texte brut d'un CV. "
            "Extrais uniquement le nom de famille, le prenom, et le numero de telephone mobile francais (06 ou 07). "
            "Reponds UNIQUEMENT avec un objet JSON valide, sans markdown, sans explication. "
            "Format exact: {\"nom\": \"DUPONT\", \"prenom\": \"Marie\", \"telephone\": \"0612345678\"} "
            "Si une info est absente mets null. "
            "Texte du CV:\n\n" + texte_cv[:3000]
        )
        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": prompt}]
        }).encode("utf-8")

        req = urllib.request.Request(
            ANTHROPIC_API_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            texte_reponse = result["content"][0]["text"].strip()
            # Nettoyer si markdown present
            texte_reponse = texte_reponse.replace("```json", "").replace("```", "").strip()
            infos = json.loads(texte_reponse)
            return (
                infos.get("nom") or None,
                infos.get("prenom") or None,
                infos.get("telephone") or None,
            )
    except Exception:
        return None, None, None


# ---------------------------------------------------------------------------
# BASE DE CONTACTS
# ---------------------------------------------------------------------------
def charger_db():
    if os.path.exists(PATH_DB):
        with open(PATH_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def sauvegarder_db(db):
    with open(PATH_DB, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def tel_valide(tel):
    return bool(tel) and tel not in (NO_TEL, "", "None", "null") and len(str(tel)) >= 10


# ---------------------------------------------------------------------------
# EXTRACTION DE TEXTE
# ---------------------------------------------------------------------------
def extraire_texte_pptx(path):
    try:
        prs = Presentation(path)
        texte = ""
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    texte += " " + shape.text
        return texte.strip() or None
    except Exception:
        return None


def extraire_texte_pdf(path):
    try:
        import pypdf
        texte = ""
        with open(path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                texte += " " + (page.extract_text() or "")
        return texte.strip() or None
    except Exception:
        return None


def extraire_telephone_texte(texte):
    match = re.search(r"(0[67](?:[\s.\-]*\d{2}){4})", texte or "")
    if match:
        return "".join(re.findall(r"\d", match.group(1)))
    return NO_TEL


# ---------------------------------------------------------------------------
# CONVERSION PPTX -> PDF
# ---------------------------------------------------------------------------
def trouver_libreoffice():
    for c in [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        shutil.which("soffice"),
        shutil.which("libreoffice"),
    ]:
        if c and os.path.exists(c):
            return c
    return None


def convertir_pptx_en_pdf(path_dossier, path_pdf):
    soffice = trouver_libreoffice()
    if not soffice:
        st.error("LibreOffice non installe. Voir https://www.libreoffice.org")
        return 0, 0
    os.makedirs(path_pdf, exist_ok=True)
    fichiers = [f for f in os.listdir(path_dossier) if f.endswith(".pptx")]
    nb_ok = nb_err = 0
    progress = st.progress(0, text="Conversion...")
    for i, f in enumerate(fichiers):
        cible = os.path.join(path_pdf, f.replace(".pptx", ".pdf"))
        if os.path.exists(cible):
            nb_ok += 1
        else:
            try:
                r = subprocess.run(
                    [soffice, "--headless", "--convert-to", "pdf",
                     "--outdir", path_pdf, os.path.join(path_dossier, f)],
                    capture_output=True, timeout=30
                )
                nb_ok += 1 if r.returncode == 0 else 0
                nb_err += 0 if r.returncode == 0 else 1
            except Exception:
                nb_err += 1
        progress.progress((i + 1) / len(fichiers))
    progress.empty()
    return nb_ok, nb_err


# ---------------------------------------------------------------------------
# CHARGEMENT DES CVS
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Chargement des CVs...")
def charger_tous_les_cvs(path_dossier, path_pdf):
    entrees = {}

    def ajouter(base, texte, source, pdf_path):
        if base not in entrees:
            entrees[base] = {"texte": texte or "", "source": source, "pdf_path": pdf_path}
        else:
            if not entrees[base]["texte"] and texte:
                entrees[base]["texte"] = texte
            if not entrees[base]["pdf_path"] and pdf_path:
                entrees[base]["pdf_path"] = pdf_path

    for f in sorted(os.listdir(path_dossier)):
        if not f.endswith(".pptx"):
            continue
        base = f.replace(".pptx", "")
        texte = extraire_texte_pptx(os.path.join(path_dossier, f))
        pdf_path = None
        for c in [os.path.join(path_pdf, base + ".pdf"), os.path.join(path_dossier, base + ".pdf")]:
            if os.path.exists(c):
                pdf_path = c
                break
        if texte is None and pdf_path:
            texte = extraire_texte_pdf(pdf_path)
            source = "pdf"
        elif texte is None:
            source = "illisible"
        else:
            source = "pptx"
        ajouter(base, texte, source, pdf_path)

    if os.path.exists(path_pdf):
        for f in sorted(os.listdir(path_pdf)):
            if not f.endswith(".pdf"):
                continue
            base = f.replace(".pdf", "")
            pdf_path = os.path.join(path_pdf, f)
            texte = None if (base in entrees and entrees[base]["texte"]) else extraire_texte_pdf(pdf_path)
            ajouter(base, texte, "pdf", pdf_path)

    for f in sorted(os.listdir(path_dossier)):
        if not f.endswith(".pdf"):
            continue
        base = f.replace(".pdf", "")
        pdf_path = os.path.join(path_dossier, f)
        texte = None if (base in entrees and entrees[base]["texte"]) else extraire_texte_pdf(pdf_path)
        ajouter(base, texte, "pdf", pdf_path)

    return entrees


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def normaliser(texte):
    return texte.lower().replace("\u2019", "'").replace("\u2018", "'").replace("\u2032", "'")


def parser_nom_prenom(base):
    parts = base.split("-")
    if len(parts) < 2:
        return base.upper(), "Candidat"
    mots = parts[1].strip().split()
    return (mots[0].upper() if mots else "INCONNU"), (" ".join(mots[1:]) if len(mots) > 1 else "Candidat")


def get_telephone(base, texte, db):
    if base in CORRECTIONS_TEL:
        return CORRECTIONS_TEL[base]
    tel_db = db.get(base, {}).get("telephone", NO_TEL)
    if tel_valide(tel_db):
        return tel_db
    tel_texte = extraire_telephone_texte(texte)
    return tel_texte if tel_valide(tel_texte) else NO_TEL


def lien_whatsapp(telephone, message):
    return "https://web.whatsapp.com/send?phone=33" + telephone[1:] + "&text=" + urllib.parse.quote(message)


def filtrer_cvs(entrees, query, db):
    termes = normaliser(query).split()
    resultats = []
    for base, data in entrees.items():
        haystack = normaliser(base + " " + data["texte"])
        if not all(t in haystack for t in termes):
            continue
        nom, prenom = parser_nom_prenom(base)
        tel = get_telephone(base, data["texte"], db)
        resultats.append({
            "Selec.":    False,
            "Nom":       db.get(base, {}).get("nom", nom),
            "Prenom":    db.get(base, {}).get("prenom", prenom),
            "Telephone": tel,
            "PDF":       "OK" if data["pdf_path"] else "Non",
            "IA":        "OK" if db.get(base, {}).get("ia_enrichi") else "-",
            "Fichier":   base,
            "_pdf_path": data["pdf_path"],
        })
    return resultats


# ---------------------------------------------------------------------------
# INTERFACE
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Noovee Contacts", layout="wide")
st.title("Noovee - Base de Contacts")

if not os.path.exists(PATH_DOSSIER):
    st.error("Dossier introuvable : " + PATH_DOSSIER)
    st.stop()

os.makedirs(PATH_PDF, exist_ok=True)

entrees_cvs = charger_tous_les_cvs(PATH_DOSSIER, PATH_PDF)
db = charger_db()

# Enregistrement automatique des nouveaux CVs
modif = False
for base, data in entrees_cvs.items():
    if base not in db:
        nom, prenom = parser_nom_prenom(base)
        tel = get_telephone(base, data["texte"], {})
        db[base] = {
            "nom": nom, "prenom": prenom,
            "telephone": tel,
            "ia_enrichi": False,
            "date_ajout": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "whatsapp_envoye": False,
        }
        modif = True
if modif:
    sauvegarder_db(db)

# ============================
# ONGLETS
# ============================
tab_recherche, tab_contacts, tab_outils = st.tabs(["Recherche", "Base de contacts", "Outils"])


# ============================
# ONGLET 1 — RECHERCHE
# ============================
with tab_recherche:
    query = st.text_input("Rechercher un profil (ex: duval paris...)", "")
    st.caption(str(len(entrees_cvs)) + " CVs indexes")

    if query:
        resultats = filtrer_cvs(entrees_cvs, query, db)

        if resultats:
            st.write("### " + str(len(resultats)) + " resultat(s)")

            df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in resultats])
            edited_df = st.data_editor(
                df,
                column_config={"Selec.": st.column_config.CheckboxColumn("Selec.")},
                hide_index=True,
                use_container_width=True,
            )

            # Sauvegarde automatique des modifications
            for i, row in edited_df.iterrows():
                base = resultats[i]["Fichier"]
                if base in db:
                    new_tel = str(row["Telephone"]).strip()
                    new_nom = str(row["Nom"]).strip()
                    new_pre = str(row["Prenom"]).strip()
                    if (db[base].get("telephone") != new_tel or
                        db[base].get("nom") != new_nom or
                        db[base].get("prenom") != new_pre):
                        db[base]["telephone"] = new_tel
                        db[base]["nom"]       = new_nom
                        db[base]["prenom"]    = new_pre
                        sauvegarder_db(db)

            indices_sel = edited_df[edited_df["Selec."] == True].index.tolist()
            selection   = [resultats[i] for i in indices_sel]

            if selection:
                st.divider()
                st.subheader("Envoyer un message WhatsApp")
                msg = st.text_area("Message :", "Bonjour...")

                for row in selection:
                    tel = get_telephone(row["Fichier"], entrees_cvs.get(row["Fichier"], {}).get("texte", ""), db)
                    col_wa, col_dl = st.columns([3, 1])

                    with col_wa:
                        if tel_valide(tel):
                            st.link_button(
                                "Envoyer WA a " + row["Prenom"] + " " + row["Nom"] + " (" + tel + ")",
                                lien_whatsapp(tel, msg)
                            )
                            if st.button("Marquer WA comme envoye", key="mark_" + row["Fichier"]):
                                db[row["Fichier"]]["whatsapp_envoye"] = True
                                db[row["Fichier"]]["date_wa"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                                sauvegarder_db(db)
                                st.rerun()
                        else:
                            st.warning("Pas de numero pour " + row["Prenom"] + " " + row["Nom"])
                            tel_saisi = st.text_input("Saisir le numero :", key="tel_" + row["Fichier"], placeholder="0612345678")
                            if tel_saisi and st.button("Sauvegarder", key="save_" + row["Fichier"]):
                                db[row["Fichier"]]["telephone"] = tel_saisi.strip()
                                sauvegarder_db(db)
                                st.rerun()

                    with col_dl:
                        pdf_path = row["_pdf_path"]
                        if pdf_path and os.path.exists(pdf_path):
                            with open(pdf_path, "rb") as f:
                                st.download_button(
                                    label="Telecharger PDF",
                                    data=f,
                                    file_name=os.path.basename(pdf_path),
                                    mime="application/pdf",
                                    key="dl_" + row["Fichier"],
                                )
        else:
            st.info("Aucun resultat.")


# ============================
# ONGLET 2 — BASE DE CONTACTS
# ============================
with tab_contacts:
    st.subheader("Tous les contacts (" + str(len(db)) + ")")

    if db:
        rows = []
        for base, info in db.items():
            rows.append({
                "Nom":        info.get("nom", ""),
                "Prenom":     info.get("prenom", ""),
                "Telephone":  info.get("telephone", NO_TEL),
                "IA":         "OK" if info.get("ia_enrichi") else "-",
                "WA envoye":  "Oui" if info.get("whatsapp_envoye") else "Non",
                "Date ajout": info.get("date_ajout", ""),
                "Fichier":    base,
            })

        df_contacts = pd.DataFrame(rows)
        edited_contacts = st.data_editor(
            df_contacts,
            column_config={
                "Nom":       st.column_config.TextColumn("Nom"),
                "Prenom":    st.column_config.TextColumn("Prenom"),
                "Telephone": st.column_config.TextColumn("Telephone"),
            },
            disabled=["IA", "WA envoye", "Date ajout", "Fichier"],
            hide_index=True,
            use_container_width=True,
        )

        if st.button("Sauvegarder les modifications"):
            for i, row in edited_contacts.iterrows():
                base = row["Fichier"]
                if base in db:
                    db[base]["nom"]       = str(row["Nom"]).strip()
                    db[base]["prenom"]    = str(row["Prenom"]).strip()
                    db[base]["telephone"] = str(row["Telephone"]).strip()
            sauvegarder_db(db)
            st.success("Base de contacts sauvegardee !")
            st.rerun()

        st.divider()
        st.subheader("Ajouter un contact manuellement")
        col1, col2, col3 = st.columns(3)
        with col1:
            new_nom    = st.text_input("Nom", placeholder="DUPONT")
        with col2:
            new_prenom = st.text_input("Prenom", placeholder="Marie")
        with col3:
            new_tel    = st.text_input("Telephone", placeholder="0612345678")

        if st.button("Ajouter le contact"):
            if new_nom and new_prenom and new_tel:
                base_key = "MANUEL-" + new_nom + " " + new_prenom
                db[base_key] = {
                    "nom": new_nom.upper(),
                    "prenom": new_prenom,
                    "telephone": new_tel.strip(),
                    "ia_enrichi": False,
                    "date_ajout": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "whatsapp_envoye": False,
                }
                sauvegarder_db(db)
                st.success("Contact ajoute !")
                st.rerun()
            else:
                st.warning("Veuillez remplir tous les champs.")
    else:
        st.info("Aucun contact dans la base.")


# ============================
# ONGLET 3 — OUTILS
# ============================
with tab_outils:
    col_r, col_p, col_ia = st.columns(3)

    with col_r:
        if st.button("Actualiser les CVs"):
            charger_tous_les_cvs.clear()
            st.rerun()

    with col_p:
        if st.button("Convertir tous les CVs en PDF"):
            nb_ok, nb_err = convertir_pptx_en_pdf(PATH_DOSSIER, PATH_PDF)
            charger_tous_les_cvs.clear()
            st.success(str(nb_ok) + " PDF(s) generes - " + str(nb_err) + " erreur(s)")
            st.rerun()

    with col_ia:
        non_enrichis = [b for b, v in db.items() if not v.get("ia_enrichi")]
        if st.button("Enrichir avec IA (" + str(len(non_enrichis)) + " CVs)"):
            if non_enrichis:
                progress = st.progress(0, text="Analyse IA en cours...")
                for i, base in enumerate(non_enrichis):
                    texte = entrees_cvs.get(base, {}).get("texte", "")
                    nom_ia, prenom_ia, tel_ia = extraire_infos_ia(texte)
                    if nom_ia:
                        db[base]["nom"] = nom_ia
                    if prenom_ia:
                        db[base]["prenom"] = prenom_ia
                    if tel_ia and tel_valide(tel_ia):
                        db[base]["telephone"] = tel_ia
                    db[base]["ia_enrichi"] = True
                    progress.progress(
                        (i + 1) / len(non_enrichis),
                        text="Analyse : " + base[:40]
                    )
                sauvegarder_db(db)
                progress.empty()
                st.success("Enrichissement IA termine !")
                st.rerun()
            else:
                st.info("Tous les CVs sont deja enrichis.")

    st.divider()
    st.caption("Dossier CV : " + PATH_DOSSIER)
    st.caption("Dossier PDF : " + PATH_PDF)
    st.caption("Base de contacts : " + PATH_DB)

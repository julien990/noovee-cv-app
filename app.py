# app.py — Noovee

import streamlit as st
import streamlit.components.v1 as components
import json
import base64
import re
from urllib.parse import quote
from pathlib import Path

st.set_page_config(page_title="Noovee", page_icon="🟢", layout="wide", initial_sidebar_state="expanded")

from dotenv import load_dotenv
load_dotenv()

import database as db
import cv_processor as cvp
import scoring as sc
from ai_providers import get_providers_status, generate_contact_message
from config import COLORS, DOMAINES, CV_STORAGE_PATH

db.init_db()
db.clean_null_strings()

if "startup_done"      not in st.session_state: st.session_state.startup_done      = False
if "startup_report"    not in st.session_state: st.session_state.startup_report    = None
if "selected_ids"      not in st.session_state: st.session_state.selected_ids      = set()
if "campaign_messages" not in st.session_state: st.session_state.campaign_messages = {}
if "campaign_open"     not in st.session_state: st.session_state.campaign_open     = False
if "confirm_reset"     not in st.session_state: st.session_state.confirm_reset     = False
if "dup_selected"      not in st.session_state: st.session_state.dup_selected      = set()

if not st.session_state.startup_done:
    with st.spinner("Scan du dossier CV..."):
        st.session_state.startup_report = cvp.scan_and_import_new_cvs()
    st.session_state.startup_done = True

# ── CSS minimal — uniquement pour la sidebar et les boutons ───────────────────
st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap');
  html, body, [class*="css"] {{ font-family:'DM Sans',sans-serif; }}
  h1,h2,h3,h4 {{ font-family:'Syne',sans-serif !important; }}
  section[data-testid="stSidebar"] {{ background:{COLORS['primary']}; }}
  section[data-testid="stSidebar"] * {{ color:#fff !important; }}
  div.stButton > button[kind="primary"] {{
      background:{COLORS['primary']} !important;
      color:white !important; border:none !important;
      border-radius:8px !important; font-weight:600 !important;
  }}
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def display_name(c: dict) -> str:
    prenom = c.get("prenom") or ""
    nom    = c.get("nom") or ""
    name   = f"{prenom} {nom}".strip()
    return name if name else (f"Contact #{c['id']}" if c.get("id") else "Nouveau contact")

def score_emoji(s):
    if s >= 65: return "🟢"
    if s >= 40: return "🟡"
    return "⚪"

def wa_number(phone):
    if not phone: return ""
    d = re.sub(r"\D", "", phone)
    return "33" + d[1:] if d.startswith("0") and len(d) == 10 else d

def show_pdf(filename):
    # Priorite 1 : URL Supabase publique (persiste entre redemarrages)
    supabase_url = cvp.get_supabase_url(filename)
    if supabase_url:
        st.markdown(
            f'<iframe src="{supabase_url}" width="100%" height="680" '
            f'style="border-radius:10px;"></iframe>',
            unsafe_allow_html=True,
        )
        return
    # Priorite 2 : fichier local
    path = Path(CV_STORAGE_PATH) / filename
    if path.exists():
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="680" '
            f'style="border-radius:10px;"></iframe>',
            unsafe_allow_html=True,
        )
        return
    st.info("Fichier non disponible. Uploadez-le a nouveau pour le visualiser.")

def current_context():
    for key in ("ao_criteria", "ai_criteria"):
        c = st.session_state.get(key)
        if c:
            parts = []
            if c.get("poste"):  parts.append("Poste : " + c["poste"])
            if c.get("resume"): parts.append(c["resume"])
            if c.get("annees_min") and int(c["annees_min"]) > 0:
                parts.append(str(c["annees_min"]) + " ans minimum.")
            if parts: return "\n".join(parts)
    if st.session_state.get("unified_query"):
        return "Mission : " + st.session_state["unified_query"]
    return ""


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🟢 Noovee")
    st.caption("Base de Contacts IA")
    st.divider()
    page = st.radio("Navigation",
        ["🏠 Accueil", "📤 Upload CV", "👥 Base de Contacts"],
        label_visibility="collapsed")
    st.divider()
    status = get_providers_status()
    st.markdown("**Providers IA**")
    for k in ["mistral", "openai", "anthropic"]:
        st.markdown(f"{'🟢' if status[k] else '🔴'} {k.capitalize()}")
    st.divider()
    st.metric("Contacts", db.count_contacts())
    n_sel = len(st.session_state.selected_ids)
    if n_sel:
        st.markdown(f"**{n_sel} selectionne(s)**")
    st.divider()
    if st.button("🔄 Re-scanner", use_container_width=True):
        st.session_state.startup_done = False
        st.rerun()
    st.divider()
    if st.session_state.confirm_reset:
        st.warning("⚠️ Confirmer ?")
        col_ok, col_no = st.columns(2)
        if col_ok.button("✅ Oui", use_container_width=True):
            for c in db.get_all_contacts():
                db.delete_contact(c["id"])
                if c.get("cv_filename"): cvp.delete_cv_file(c["cv_filename"])
            st.session_state.confirm_reset = False
            st.session_state.selected_ids  = set()
            st.rerun()
        if col_no.button("❌ Non", use_container_width=True):
            st.session_state.confirm_reset = False
            st.rerun()
    else:
        if st.button("🗑️ Vider la base", use_container_width=True):
            st.session_state.confirm_reset = True
            st.rerun()


# ── Notifications + doublons ───────────────────────────────────────────────────

def show_notifications():
    r = st.session_state.get("startup_report") or {}
    if r.get("imported"):
        st.success("✅ CV importes : " + ", ".join(f"**{x['name']}**" for x in r["imported"]))
    if r.get("failed"):
        with st.expander(f"⚠️ {len(r['failed'])} fichier(s) non importe(s)"):
            for f in r["failed"]:
                st.warning(f"`{f['filename']}` — {f['error']}")

    dups = db.find_duplicates()
    if not dups: return

    with st.expander(f"⚠️ {len(dups)} doublon(s) detecte(s)"):
        if st.session_state.dup_selected:
            n_dup = len(st.session_state.dup_selected)
            if st.button(f"🗑️ Supprimer {n_dup} selectionne(s)", type="primary"):
                for cid in list(st.session_state.dup_selected):
                    all_c = db.get_all_contacts()
                    c = next((x for x in all_c if x["id"] == cid), None)
                    if c:
                        db.delete_contact(cid)
                        if c.get("cv_filename"): cvp.delete_cv_file(c["cv_filename"])
                st.session_state.dup_selected = set()
                st.rerun()
        st.divider()
        for gi, group in enumerate(dups):
            names = " / ".join(display_name(c) for c in group)
            st.warning(f"⚠️ Doublon : {names}")
            for c in group:
                cid  = c["id"]
                col_chk, col_info = st.columns([0.5, 9])
                with col_chk:
                    checked = st.checkbox("", value=cid in st.session_state.dup_selected,
                                          key=f"dup_chk_{gi}_{cid}", label_visibility="collapsed")
                    if checked: st.session_state.dup_selected.add(cid)
                    else:       st.session_state.dup_selected.discard(cid)
                with col_info:
                    st.write(f"**{display_name(c)}** · {c.get('poste','—')} · {c.get('email','—')} · _{c.get('created_at','')[:10]}_")
            st.divider()


# ── Score detail ───────────────────────────────────────────────────────────────

def show_score_detail(scores: dict):
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 Competences", f"{scores['competences']}/100")
    c2.metric("📅 Anciennete",  f"{scores['anciennete']}/100")
    c3.metric("🏢 Domaine",     f"{scores['domaine']}/100")

    nb_exp    = scores.get("nb_exp_match", 0)
    mult      = scores.get("multiplicateur", 1.0)
    comp_base = scores.get("comp_base", scores["competences"])

    if nb_exp > 0:
        pct = int((mult - 1.0) * 100)
        st.info(f"🔁 x{mult} profondeur · {nb_exp} experience(s) pertinente(s) · +{pct}% ({comp_base} → {scores['competences']})")
        for exp in scores.get("exp_detail", []):
            label = exp.get("poste", "—")
            if exp.get("entreprise"): label += f" — {exp['entreprise']}"
            if exp.get("annees"):     label += f" ({exp['annees']} an{'s' if exp['annees'] > 1 else ''})"
            st.write(f"✅ {label} · {exp.get('matches',0)} mot(s)")

    if scores.get("bonus_domaine"):
        st.caption("✨ Bonus domaine (+8 pts)")
    if scores.get("mots_trouves"):
        st.write("**Mots trouves :** " + " · ".join(scores["mots_trouves"][:15]))


# ── Barre campagne ─────────────────────────────────────────────────────────────

def show_campaign_bar():
    n = len(st.session_state.selected_ids)
    if not n: return
    st.info(f"✅ **{n} contact{'s' if n > 1 else ''} selectionne{'s' if n > 1 else ''}**")
    c1, c2, _ = st.columns([2, 1.5, 5])
    with c1:
        if st.button("📧 Preparer la campagne", type="primary", use_container_width=True):
            st.session_state.campaign_open = not st.session_state.campaign_open
            st.rerun()
    with c2:
        if st.button("✖ Tout deselectionner", use_container_width=True):
            st.session_state.selected_ids      = set()
            st.session_state.campaign_messages = {}
            st.session_state.campaign_open     = False
            st.rerun()


def show_campaign_panel():
    if not st.session_state.campaign_open: return
    if not st.session_state.selected_ids:  return
    selected = [c for c in db.get_all_contacts() if c["id"] in st.session_state.selected_ids]
    if not selected: return

    st.subheader("📧 Campagne email")
    ca, cb, cc = st.columns(3)
    mission = ca.text_area("Mission", value=current_context(), height=100, key="camp_mission")
    lieu    = cb.text_input("Lieu", placeholder="Ex : Paris / Full remote", key="camp_lieu")
    duree   = cc.text_input("Duree", placeholder="Ex : 3 mois renouvelables", key="camp_duree")
    context_full = mission.strip()
    if lieu:  context_full += f"\nLieu : {lieu}"
    if duree: context_full += f"\nDuree : {duree}"

    st.divider()
    cg, _ = st.columns([2, 5])
    with cg:
        gen_all = st.button(
            f"✨ Generer {len(selected)} message{'s' if len(selected) > 1 else ''}",
            type="primary", use_container_width=True, disabled=not context_full.strip(),
        )
    if gen_all:
        prog = st.progress(0)
        for i, c in enumerate(selected):
            prog.progress((i + 1) / len(selected), text=f"Redaction pour {display_name(c)}...")
            try:
                msg, _ = generate_contact_message(c, context_full, "email")
                st.session_state.campaign_messages[c["id"]] = msg
            except Exception as e:
                st.session_state.campaign_messages[c["id"]] = f"[Erreur : {e}]"
        prog.empty()
        st.rerun()

    if st.session_state.campaign_messages:
        mailto_list = []
        for c in selected:
            cid   = c["id"]
            name  = display_name(c)
            email = c.get("email") or ""
            with st.expander(f"{'✅' if email else '⚠️'} {name}", expanded=True):
                msg = st.text_area("Message", value=st.session_state.campaign_messages.get(cid, ""),
                                   height=160, key=f"camp_msg_{cid}", label_visibility="collapsed")
                st.session_state.campaign_messages[cid] = msg
                if email:
                    subject = quote(f"Opportunite pour {name}")
                    mailto_list.append(f"mailto:{email}?subject={subject}&body={quote(msg)}")
                    st.link_button("📧 Ouvrir dans Outlook", f"mailto:{email}?subject={subject}&body={quote(msg)}")
                else:
                    st.warning("Email non renseigne.")
        if mailto_list:
            st.divider()
            links_js = json.dumps(mailto_list)
            components.html(f"""
            <button onclick="openAll()" style="background:{COLORS['primary']};color:white;border:none;
                border-radius:8px;padding:10px 22px;font-size:0.92rem;font-weight:600;cursor:pointer;width:100%;">
                📧 Tout ouvrir dans Outlook ({len(mailto_list)} emails)
            </button>
            <script>
            function openAll() {{
                const links = {links_js};
                links.forEach((href, i) => {{
                    setTimeout(() => {{
                        const a = document.createElement('a');
                        a.href = href; document.body.appendChild(a); a.click(); document.body.removeChild(a);
                    }}, i * 1500);
                }});
            }}
            </script>
            """, height=55)
    st.divider()


# ── Carte contact — 100% composants natifs Streamlit ──────────────────────────

def show_contact_card(c: dict, rank: int = None, key_prefix: str = ""):
    cid    = c["id"]
    name   = display_name(c)
    poste  = c.get("poste") or "—"
    annees = c.get("annees_experience", 0)
    scores = c.get("score")
    is_sel = cid in st.session_state.selected_ids
    doms   = c.get("domaines_fonctionnels", [])
    comps  = c.get("competences", [])[:7]

    chk_col, card_col = st.columns([0.5, 11])

    with chk_col:
        st.write("")
        st.write("")
        checked = st.checkbox("", value=is_sel, key=f"chk_{key_prefix}_{cid}", label_visibility="collapsed")
        if checked: st.session_state.selected_ids.add(cid)
        else:       st.session_state.selected_ids.discard(cid)

    with card_col:
        with st.container(border=True):
            col_info, col_score = st.columns([9, 1])

            with col_info:
                rank_str = f"**#{rank}**  " if rank else ""
                mult_str = ""
                if scores and scores.get("multiplicateur", 1.0) > 1.0:
                    mult_str = f"  ·  🔁 x{scores['multiplicateur']} ({scores.get('nb_exp_match',0)} exp.)"
                # Nom + poste en une ligne — texte pur, pas de HTML
                st.markdown(f"{rank_str}**{name}**  \n_{poste} · {annees} ans{mult_str}_")
                # Domaines
                if doms:
                    st.write("🏷️ " + "  ·  ".join(doms))
                # Competences
                if comps:
                    st.write("🔧 " + "  ·  ".join(comps))

            with col_score:
                if scores:
                    s = scores["total"]
                    st.metric("", f"{score_emoji(s)} {s}")

            # CV
            filename = c.get("cv_filename")
            if filename:
                with st.expander("📄 Voir le CV"):
                    show_pdf(filename)

            # Score
            if scores:
                with st.expander("📊 Detail du score"):
                    show_score_detail(scores)

            # Modifier
            with st.expander("✏️ Modifier / Supprimer"):
                with st.form(key=f"editform_{cid}"):
                    r1, r2 = st.columns(2)
                    prenom  = r1.text_input("Prenom",    value=c.get("prenom") or "")
                    nom_v   = r2.text_input("Nom",       value=c.get("nom") or "")
                    email_v = r1.text_input("Email",     value=c.get("email") or "")
                    tel_v   = r2.text_input("Telephone", value=c.get("telephone") or "")
                    poste_v = st.text_input("Poste",     value=c.get("poste") or "")
                    ann_v   = st.number_input("Annees d'experience", min_value=0, max_value=50,
                                               value=int(c.get("annees_experience") or 0))
                    doms_v  = st.multiselect("Domaines (max 3)", DOMAINES,
                                              default=[d for d in c.get("domaines_fonctionnels", []) if d in DOMAINES],
                                              max_selections=3)
                    comp_v  = st.text_area("Competences (une par ligne)",
                                           value="\n".join(c.get("competences", [])), height=80)
                    cs, cd  = st.columns([3, 1])
                    saved   = cs.form_submit_button("💾 Sauvegarder", type="primary", use_container_width=True)
                    delet   = cd.form_submit_button("🗑️ Supprimer", use_container_width=True)

                if saved:
                    db.update_contact(cid, {
                        **c,
                        "prenom": prenom.strip() or None, "nom": nom_v.strip() or None,
                        "email": email_v.strip() or None, "telephone": tel_v.strip() or None,
                        "poste": poste_v.strip() or None, "annees_experience": int(ann_v),
                        "domaines_fonctionnels": doms_v,
                        "competences": [x.strip() for x in comp_v.split("\n") if x.strip()],
                    })
                    st.success("✅ Sauvegarde !")
                    st.rerun()
                if delet:
                    db.delete_contact(cid)
                    if c.get("cv_filename"): cvp.delete_cv_file(c["cv_filename"])
                    st.rerun()

            # Contacter
            with st.expander("📬 Contacter"):
                email_c = c.get("email") or ""
                phone_c = c.get("telephone") or ""
                if email_c:
                    subject = quote(f"Opportunite pour {name}")
                    st.link_button("📧 Ouvrir dans Outlook", f"mailto:{email_c}?subject={subject}", use_container_width=True)
                else:
                    st.warning("Email non renseigne.")
                wa = wa_number(phone_c)
                if wa:
                    st.link_button("💬 Ouvrir WhatsApp", f"https://wa.me/{wa}", use_container_width=True)
                else:
                    st.warning("Telephone non renseigne.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ACCUEIL
# ══════════════════════════════════════════════════════════════════════════════

def page_home():
    st.title("🏠 Recherche & Matching")
    show_notifications()
    contacts = db.get_all_contacts()
    if not contacts:
        st.warning("Base vide. Uploadez des CVs via **📤 Upload CV**.")
        return

    show_campaign_bar()
    show_campaign_panel()

    tab1, tab2 = st.tabs(["🔍 Recherche", "🎯 Matching Appel d'Offres"])

    with tab1:
        query = st.text_input("Recherche", placeholder="Ex : RGPD, consultant immobilier 5 ans...",
                               key="unified_query", label_visibility="collapsed")
        top_n = st.slider("Resultats", 3, 20, 10, key="search_top_n")

        if query and len(query.strip()) >= 2:
            results = db.search_contacts(query)
            if not results:
                st.info(f"Aucun resultat pour « {query} »")
            else:
                crit_local = sc.keyword_criteria(query)
                ranked     = sc.rank_contacts(results, crit_local, top_n=top_n)
                doms_detectes = crit_local.get("domaines", [])
                caption = f"**{len(ranked)} profil(s)**"
                if doms_detectes:
                    caption += f" · Domaine detecte : {' · '.join(doms_detectes)}"
                st.caption(caption)

                ca, _ = st.columns([2, 5])
                with ca:
                    if st.button("🤖 Affiner avec l'IA", key="ai_btn", use_container_width=True):
                        with st.spinner("Analyse..."):
                            try:
                                crit_ai = sc.extract_criteria_from_text(query)
                                crit_ai["use_texte_brut"] = True
                                st.session_state["ai_results"]  = sc.rank_contacts(contacts, crit_ai, top_n=top_n)
                                st.session_state["ai_criteria"] = crit_ai
                                st.session_state["ai_query"]    = query
                            except Exception as e:
                                st.error(str(e))

                ai_res  = st.session_state.get("ai_results")
                ai_crit = st.session_state.get("ai_criteria")
                ai_q    = st.session_state.get("ai_query")

                if ai_res and ai_q == query:
                    poste_ia = ai_crit.get("poste","—")
                    doms_ia  = " · ".join(ai_crit.get("domaines",[]))
                    prov_ia  = ai_crit.get("_provider","?").capitalize()
                    st.info(f"🤖 **IA** via {prov_ia} — Poste : {poste_ia}" + (f" · {doms_ia}" if doms_ia else ""))
                    for i, c in enumerate(ai_res, 1):
                        show_contact_card(c, rank=i, key_prefix=f"ai{i}")
                else:
                    for i, c in enumerate(ranked, 1):
                        show_contact_card(c, rank=i, key_prefix=f"loc{i}")

        elif not query:
            for k in ["ai_results", "ai_criteria", "ai_query"]:
                st.session_state.pop(k, None)

    with tab2:
        method = st.radio("Mode", ["📋 Coller le texte", "📄 Uploader un PDF"], horizontal=True, key="ao_method")
        ao_text = ""
        if method == "📋 Coller le texte":
            ao_text = st.text_area("Texte AO", placeholder="Collez l'AO ici...", height=200, key="ao_text")
        else:
            f = st.file_uploader("PDF AO", type=["pdf"], key="ao_pdf")
            if f:
                ao_text = cvp.extract_text_from_pdf(f.getbuffer())
                st.caption(f"✅ {len(ao_text)} caracteres extraits")

        top_ao = st.slider("Profils", 3, 10, 5, key="ao_top_n")

        if st.button("🎯 Lancer le matching", type="primary", key="ao_btn", disabled=not ao_text.strip()):
            with st.spinner("Analyse AO..."):
                try:
                    crit = sc.extract_criteria_from_text(ao_text)
                    crit["use_texte_brut"] = True
                    st.session_state["ao_criteria"] = crit
                except Exception as e:
                    st.error(str(e)); st.stop()

            col_a, col_b = st.columns(2)
            with col_a:
                st.write(f"**Poste :** {crit.get('poste') or '—'}")
                st.write(f"**Annees min :** {crit.get('annees_min', 0)}")
                st.write(f"**Resume :** {crit.get('resume', '—')}")
            with col_b:
                if crit.get("domaines"):  st.write("**Domaines :** " + " · ".join(crit["domaines"]))
                if crit.get("mots_cles"): st.write("**Mots-cles :** " + " · ".join(crit["mots_cles"][:12]))
            st.caption(f"Analyse via {crit.get('_provider','?').capitalize()}")
            st.divider()

            with st.spinner("Scoring..."):
                ranked = sc.rank_contacts(contacts, crit, top_n=top_ao)

            if not ranked:
                st.info("Aucun profil correspondant.")
            else:
                st.subheader(f"🏆 Top {len(ranked)} profils")
                for i, c in enumerate(ranked, 1):
                    show_contact_card(c, rank=i, key_prefix=f"ao{i}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def page_upload():
    st.title("📤 Upload CV")
    st.write("Formats acceptes : **PDF, Word (.docx), PowerPoint (.pptx)**")

    if "pending" not in st.session_state: st.session_state.pending = {}
    if "errors"  not in st.session_state: st.session_state.errors  = {}

    files = st.file_uploader("Choisir des fichiers",
                              type=["pdf", "docx", "doc", "pptx", "ppt"],
                              accept_multiple_files=True)
    if files:
        if st.button("🤖 Analyser avec l'IA", type="primary"):
            st.session_state.pending = {}
            st.session_state.errors  = {}
            prog = st.progress(0)
            for i, f in enumerate(files):
                prog.progress((i + 1) / len(files), text=f"Analyse de {f.name}...")
                try:
                    data, filename, prov = cvp.process_uploaded_cv(f)
                    data["_provider"] = prov
                    st.session_state.pending[filename] = data
                except Exception as e:
                    st.session_state.errors[f.name] = str(e)
            prog.empty()

    for fname, err in st.session_state.errors.items():
        st.error(f"❌ **{fname}** — {err}")

    for filename, data in list(st.session_state.pending.items()):
        name = display_name(data) or filename
        with st.expander(f"📋 {name}", expanded=True):
            st.caption(f"Extrait via {data.get('_provider','?').capitalize()}")
            with st.form(key=f"form_confirm_{filename}"):
                c1, c2 = st.columns(2)
                prenom = c1.text_input("Prenom",    value=data.get("prenom") or "")
                nom    = c2.text_input("Nom",       value=data.get("nom") or "")
                email  = c1.text_input("Email",     value=data.get("email") or "")
                tel    = c2.text_input("Telephone", value=data.get("telephone") or "")
                poste  = st.text_input("Poste",     value=data.get("poste") or "")
                annees = st.number_input("Annees", min_value=0, max_value=50,
                                         value=int(data.get("annees_experience") or 0))
                doms   = st.multiselect("Domaines (max 3)", DOMAINES,
                                        default=[d for d in data.get("domaines_fonctionnels", []) if d in DOMAINES],
                                        max_selections=3)
                comps  = st.text_area("Competences", value="\n".join(data.get("competences", [])), height=80)
                ents   = st.text_area("Entreprises (JSON)", value=json.dumps(data.get("entreprises", []), ensure_ascii=False, indent=2), height=80)
                exps   = st.text_area("Experiences (JSON)", value=json.dumps(data.get("experiences", []), ensure_ascii=False, indent=2), height=100)
                txt    = st.text_area("Texte brut", value=data.get("texte_brut", ""), height=80)
                ok, no = st.columns(2)
                confirmed = ok.form_submit_button("✅ Enregistrer", type="primary", use_container_width=True)
                discarded = no.form_submit_button("🗑️ Ignorer", use_container_width=True)

            if confirmed:
                try:
                    competences = [x.strip() for x in comps.split("\n") if x.strip()]
                    try:    entreprises = json.loads(ents)
                    except: entreprises = data.get("entreprises", [])
                    try:    experiences = json.loads(exps)
                    except: experiences = data.get("experiences", [])
                    cid = db.insert_contact({
                        "prenom": prenom.strip() or None, "nom": nom.strip() or None,
                        "email": email.strip() or None,   "telephone": tel.strip() or None,
                        "poste": poste.strip() or None,   "annees_experience": int(annees),
                        "competences": competences, "domaines_fonctionnels": doms,
                        "entreprises": entreprises, "experiences": experiences,
                        "texte_brut": txt, "cv_filename": filename,
                    })
                    del st.session_state.pending[filename]
                    st.success(f"✅ **{prenom} {nom}** enregistre (#{cid})")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            if discarded:
                cvp.delete_cv_file(filename)
                del st.session_state.pending[filename]
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE BASE DE CONTACTS
# ══════════════════════════════════════════════════════════════════════════════

def page_contacts():
    st.title("👥 Base de Contacts")
    show_campaign_bar()
    show_campaign_panel()
    contacts = db.get_all_contacts()
    if not contacts:
        st.info("Aucun contact.")
        return
    q = st.text_input("🔍 Filtrer", placeholder="nom, poste, competence...")
    if q: contacts = db.search_contacts(q)
    st.caption(f"**{len(contacts)} contact(s)**")
    for i, c in enumerate(contacts):
        show_contact_card(c, key_prefix=f"base{i}")


# ── Router ─────────────────────────────────────────────────────────────────────

if   "🏠" in page: page_home()
elif "📤" in page: page_upload()
elif "👥" in page: page_contacts()

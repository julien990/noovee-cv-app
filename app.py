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

if not st.session_state.startup_done:
    with st.spinner("Scan du dossier CV..."):
        st.session_state.startup_report = cvp.scan_and_import_new_cvs()
    st.session_state.startup_done = True

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap');
  html, body, [class*="css"] {{ font-family:'DM Sans',sans-serif; background:{COLORS['background']}; color:{COLORS['text']}; }}
  h1,h2,h3 {{ font-family:'Syne',sans-serif; }}
  section[data-testid="stSidebar"] {{ background:{COLORS['primary']}; }}
  section[data-testid="stSidebar"] * {{ color:#fff !important; }}
  .noovee-card {{ background:{COLORS['card']}; border:1px solid {COLORS['border']}; border-radius:12px; padding:16px 20px; margin-bottom:6px; box-shadow:0 1px 4px rgba(0,0,0,0.06); }}
  .noovee-card.selected {{ border:2px solid {COLORS['primary']}; background:#F0FDF4; }}
  .badge {{ display:inline-block; background:#EEF2FF; color:{COLORS['indigo']}; border:1px solid #C7D2FE; border-radius:6px; padding:2px 8px; font-size:0.75rem; font-weight:500; margin:2px; }}
  .badge-domain {{ display:inline-block; background:#DCFCE7; color:{COLORS['primary']}; border:1px solid #BBF7D0; border-radius:6px; padding:2px 8px; font-size:0.75rem; font-weight:600; margin:2px; }}
  .badge-found {{ display:inline-block; background:#FEF3C7; color:#92400E; border:1px solid #FDE68A; border-radius:6px; padding:2px 8px; font-size:0.75rem; font-weight:500; margin:2px; }}
  .score-circle {{ display:inline-flex; align-items:center; justify-content:center; width:50px; height:50px; border-radius:50%; font-family:'Syne',sans-serif; font-size:1rem; font-weight:800; }}
  .score-green  {{ background:#DCFCE7; color:#166534; border:2px solid #86EFAC; }}
  .score-orange {{ background:#FEF3C7; color:#92400E; border:2px solid #FDE68A; }}
  .score-red    {{ background:#FEE2E2; color:#991B1B; border:2px solid #FECACA; }}
  .provider-pill {{ display:inline-block; background:{COLORS['primary']}; color:white; border-radius:20px; padding:3px 12px; font-size:0.73rem; font-weight:600; }}
  .multiplier-pill {{ display:inline-block; background:#4F46E5; color:white; border-radius:20px; padding:3px 12px; font-size:0.73rem; font-weight:700; }}
  .section-title {{ font-family:'Syne',sans-serif; font-size:1rem; font-weight:700; color:{COLORS['primary']}; border-left:3px solid {COLORS['primary']}; padding-left:10px; margin:14px 0 8px 0; }}
  .rank-badge {{ display:inline-flex; align-items:center; justify-content:center; width:26px; height:26px; border-radius:50%; background:{COLORS['primary']}; color:white; font-family:'Syne',sans-serif; font-size:0.82rem; font-weight:700; }}
  .ai-box {{ background:#EEF2FF; border:1px solid #C7D2FE; border-radius:10px; padding:12px 16px; margin-bottom:12px; font-size:0.87rem; }}
  .campaign-bar {{ background:{COLORS['primary']}; color:white; border-radius:12px; padding:14px 20px; margin-bottom:18px; }}
  .dup-card {{ background:#FFFBEB; border:1px solid #FDE68A; border-radius:10px; padding:12px 16px; margin-bottom:8px; }}
  .exp-row {{ background:#F8FAFC; border:1px solid {COLORS['border']}; border-radius:8px; padding:8px 12px; margin:4px 0; font-size:0.83rem; }}
  hr.light {{ border:none; border-top:1px solid {COLORS['border']}; margin:12px 0; }}
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def display_name(c: dict) -> str:
    prenom = c.get("prenom") or ""
    nom    = c.get("nom") or ""
    name   = f"{prenom} {nom}".strip()
    return name if name else f"Contact #{c['id']}"

def score_css(s):
    return "score-green" if s >= 65 else ("score-orange" if s >= 40 else "score-red")

def wa_number(phone):
    if not phone: return ""
    d = re.sub(r"\D", "", phone)
    return "33" + d[1:] if d.startswith("0") and len(d) == 10 else d

def show_pdf(filename):
    path = Path(CV_STORAGE_PATH) / filename
    if not path.exists():
        st.warning("Fichier introuvable.")
        return
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="680" '
        f'style="border:1px solid {COLORS["border"]};border-radius:10px;"></iframe>',
        unsafe_allow_html=True,
    )

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
    st.markdown('<h1 style="font-family:Syne,sans-serif;font-size:1.5rem;margin-bottom:2px;">🟢 Noovee</h1>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:0.78rem;opacity:0.7;margin-top:0;">Base de Contacts IA</p>', unsafe_allow_html=True)
    st.markdown("---")

    page = st.radio("Navigation",
        ["🏠 Accueil", "📤 Upload CV", "👥 Base de Contacts"],
        label_visibility="collapsed")

    st.markdown("---")
    status = get_providers_status()
    st.markdown("**Providers IA**")
    for k in ["mistral", "openai", "anthropic"]:
        st.markdown(f"{'🟢' if status[k] else '🔴'} {k.capitalize()}")

    st.markdown("---")
    st.metric("Contacts", db.count_contacts())

    n_sel = len(st.session_state.selected_ids)
    if n_sel:
        st.markdown(f"**{n_sel} selectionne(s)**")

    if st.button("🔄 Re-scanner", use_container_width=True):
        st.session_state.startup_done = False
        st.rerun()


# ── Notifications ──────────────────────────────────────────────────────────────

def show_notifications():
    r = st.session_state.get("startup_report") or {}
    if r.get("imported"):
        st.success("CV importes : " + ", ".join(f"**{x['name']}**" for x in r["imported"]))
    if r.get("failed"):
        with st.expander(f"⚠️ {len(r['failed'])} CV non importe(s)"):
            for f in r["failed"]:
                st.warning(f"`{f['filename']}` — {f['error']}")
    dups = db.find_duplicates()
    if dups:
        with st.expander(f"⚠️ {len(dups)} doublon(s) detecte(s)"):
            for gi, group in enumerate(dups):
                names = " / ".join(display_name(c) for c in group)
                st.markdown(f'<div class="dup-card"><b>⚠️</b> {names}</div>', unsafe_allow_html=True)
                for c in group:
                    ci, cd = st.columns([5, 1])
                    ci.markdown(f"**{display_name(c)}** · {c.get('poste','—')} · {c.get('email','—')}")
                    if cd.button("🗑️", key=f"dup_{gi}_{c['id']}"):
                        db.delete_contact(c["id"])
                        if c.get("cv_filename"): cvp.delete_cv_file(c["cv_filename"])
                        st.rerun()


# ── Score detail ───────────────────────────────────────────────────────────────

def show_score_detail(scores: dict):
    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 Competences", f"{scores['competences']}/100")
    c2.metric("📅 Anciennete",  f"{scores['anciennete']}/100")
    c3.metric("🏢 Domaine",     f"{scores['domaine']}/100")
    st.markdown('<hr class="light">', unsafe_allow_html=True)

    nb_exp     = scores.get("nb_exp_match", 0)
    mult       = scores.get("multiplicateur", 1.0)
    comp_base  = scores.get("comp_base", scores["competences"])
    exp_detail = scores.get("exp_detail", [])

    if nb_exp > 0:
        pct = int((mult - 1.0) * 100)
        st.markdown(
            f'<span class="multiplier-pill">🔁 x{mult} profondeur</span>'
            f'&nbsp;<span style="font-size:0.85rem;color:{COLORS["muted"]};">'
            f'{nb_exp} experience(s) — +{pct}% ({comp_base} → {scores["competences"]})</span>',
            unsafe_allow_html=True,
        )
        for exp in exp_detail:
            label = exp.get("poste", "—")
            if exp.get("entreprise"): label += f" — {exp['entreprise']}"
            if exp.get("annees"):     label += f" ({exp['annees']} an{'s' if exp['annees'] > 1 else ''})"
            st.markdown(f'<div class="exp-row">✅ {label} &nbsp;<span class="badge">{exp.get("matches",0)} mot(s)</span></div>', unsafe_allow_html=True)

    if scores.get("bonus_domaine"):
        st.caption("✨ Bonus domaine (+8 pts)")
    if scores.get("mots_trouves"):
        html = " ".join(f'<span class="badge-found">{m}</span>' for m in scores["mots_trouves"][:15])
        st.markdown(f"**Mots cles trouves :** {html}", unsafe_allow_html=True)


# ── Barre campagne ─────────────────────────────────────────────────────────────

def show_campaign_bar():
    n = len(st.session_state.selected_ids)
    if not n: return
    st.markdown(f"""
    <div class="campaign-bar">
        <span style="font-family:Syne,sans-serif;font-size:1.05rem;font-weight:700;">
            ✅ {n} contact{'s' if n > 1 else ''} selectionne{'s' if n > 1 else ''}
        </span>
    </div>
    """, unsafe_allow_html=True)
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

    st.markdown('<div class="section-title">📧 Campagne email</div>', unsafe_allow_html=True)
    ca, cb, cc = st.columns(3)
    mission = ca.text_area("Mission", value=current_context(), height=100,
                            placeholder="Ex : Mission DPO externalise...", key="camp_mission")
    lieu    = cb.text_input("Lieu",  placeholder="Ex : Paris / Full remote", key="camp_lieu")
    duree   = cc.text_input("Duree", placeholder="Ex : 3 mois renouvelables", key="camp_duree")

    context_full = mission.strip()
    if lieu:  context_full += f"\nLieu : {lieu}"
    if duree: context_full += f"\nDuree : {duree}"

    st.markdown('<hr class="light">', unsafe_allow_html=True)
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
        st.markdown('<div class="section-title">Messages — modifiables</div>', unsafe_allow_html=True)
        mailto_list = []
        for c in selected:
            cid   = c["id"]
            name  = display_name(c)
            email = c.get("email") or ""
            label = f"{'✅' if email else '⚠️'} {name}" + ("" if email else " (email manquant)")
            with st.expander(label, expanded=True):
                msg = st.text_area("Message", value=st.session_state.campaign_messages.get(cid, ""),
                                   height=160, key=f"camp_msg_{cid}", label_visibility="collapsed")
                st.session_state.campaign_messages[cid] = msg
                if email:
                    subject = quote(f"Opportunite pour {name}")
                    body    = quote(msg)
                    mailto_list.append(f"mailto:{email}?subject={subject}&body={body}")
                    st.link_button("📧 Ouvrir dans Outlook", f"mailto:{email}?subject={subject}&body={body}")
                else:
                    st.warning("Email non renseigne.")

        if mailto_list:
            st.markdown('<hr class="light">', unsafe_allow_html=True)
            links_js = json.dumps(mailto_list)
            components.html(f"""
            <button onclick="openAll()" style="background:{COLORS['primary']};color:white;border:none;
                border-radius:8px;padding:10px 22px;font-size:0.92rem;font-weight:600;cursor:pointer;width:100%;">
                📧 Tout ouvrir dans Outlook ({len(mailto_list)} emails)
            </button>
            <p id="st" style="font-size:0.78rem;color:#64748B;margin-top:6px;"></p>
            <script>
            function openAll() {{
                const links = {links_js};
                const el = document.getElementById('st');
                links.forEach((href, i) => {{
                    setTimeout(() => {{
                        const a = document.createElement('a');
                        a.href = href; document.body.appendChild(a); a.click(); document.body.removeChild(a);
                        el.textContent = 'Email ' + (i+1) + '/' + links.length + ' ouvert';
                    }}, i * 1500);
                }});
            }}
            </script>
            """, height=75)
    st.markdown('<hr class="light">', unsafe_allow_html=True)


# ── Carte contact ──────────────────────────────────────────────────────────────

def show_contact_card(c: dict, rank: int = None, key_prefix: str = ""):
    cid    = c["id"]
    name   = display_name(c)
    poste  = c.get("poste") or "—"
    annees = c.get("annees_experience", 0)
    scores = c.get("score")
    is_sel = cid in st.session_state.selected_ids

    dom_h  = " ".join(f'<span class="badge-domain">{d}</span>' for d in c.get("domaines_fonctionnels", []))
    comp_h = " ".join(f'<span class="badge">{x}</span>'        for x in c.get("competences", [])[:7])
    rank_h = f'<span class="rank-badge">#{rank}</span>&nbsp;' if rank else ""
    scr_h  = f'<span class="score-circle {score_css(scores["total"])}">{scores["total"]}</span>' if scores else ""
    mult_h = ""
    if scores and scores.get("multiplicateur", 1.0) > 1.0:
        mult_h = f'&nbsp;<span class="multiplier-pill">x{scores["multiplicateur"]} ({scores.get("nb_exp_match",0)} exp.)</span>'

    cls = "noovee-card selected" if is_sel else "noovee-card"

    chk_col, card_col = st.columns([0.5, 11])

    with chk_col:
        st.markdown("<div style='padding-top:14px;'>", unsafe_allow_html=True)
        checked = st.checkbox("", value=is_sel,
                              key=f"chk_{key_prefix}_{cid}",
                              label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)
        if checked: st.session_state.selected_ids.add(cid)
        else:       st.session_state.selected_ids.discard(cid)

    with card_col:
        st.markdown(f"""
        <div class="{cls}">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    {rank_h}
                    <span style="font-family:Syne,sans-serif;font-size:1.02rem;font-weight:700;">{name}</span>
                    &nbsp;<span style="color:{COLORS['muted']};font-size:0.85rem;">{poste} · {annees} ans</span>
                    {mult_h}
                </div>
                {scr_h}
            </div>
            <div style="margin-top:7px;">{dom_h}</div>
            <div style="margin-top:4px;">{comp_h}</div>
        </div>
        """, unsafe_allow_html=True)

        # PDF
        filename = c.get("cv_filename")
        if filename and Path(CV_STORAGE_PATH, filename).exists():
            with st.expander("📄 Voir le CV"):
                show_pdf(filename)

        # Score detail
        if scores:
            with st.expander("📊 Detail du score"):
                show_score_detail(scores)

        # Edition
        with st.expander("✏️ Modifier / Supprimer"):
            with st.form(key=f"form_{key_prefix}_{cid}"):
                r1, r2 = st.columns(2)
                prenom = r1.text_input("Prenom",    value=c.get("prenom") or "")
                nom    = r2.text_input("Nom",       value=c.get("nom") or "")
                email  = r1.text_input("Email",     value=c.get("email") or "")
                tel    = r2.text_input("Telephone", value=c.get("telephone") or "")
                poste_e = st.text_input("Poste",    value=c.get("poste") or "")
                annees_e = st.number_input("Annees", min_value=0, max_value=50,
                                           value=int(c.get("annees_experience") or 0))
                doms   = st.multiselect("Domaines (max 3)", DOMAINES,
                                        default=[d for d in c.get("domaines_fonctionnels", []) if d in DOMAINES],
                                        max_selections=3)
                comps  = st.text_area("Competences (une par ligne)",
                                      value="\n".join(c.get("competences", [])), height=80)
                cs, cd = st.columns([3, 1])
                saved  = cs.form_submit_button("💾 Sauvegarder", type="primary", use_container_width=True)
                delet  = cd.form_submit_button("🗑️ Supprimer", use_container_width=True)

            if saved:
                db.update_contact(cid, {
                    **c,
                    "prenom": prenom.strip() or None, "nom": nom.strip() or None,
                    "email": email.strip() or None,   "telephone": tel.strip() or None,
                    "poste": poste_e.strip() or None, "annees_experience": int(annees_e),
                    "domaines_fonctionnels": doms,
                    "competences": [x.strip() for x in comps.split("\n") if x.strip()],
                })
                st.success("Sauvegarde.")
                st.rerun()

            if delet:
                db.delete_contact(cid)
                if c.get("cv_filename"): cvp.delete_cv_file(c["cv_filename"])
                st.rerun()

        # Email / WA
        email_c = c.get("email") or ""
        phone_c = c.get("telephone") or ""
        col_m, col_w, _ = st.columns([1.5, 1.5, 5])
        with col_m:
            if email_c:
                subject = quote(f"Opportunite pour {name}")
                st.link_button("📧 Email", f"mailto:{email_c}?subject={subject}", use_container_width=True)
            else:
                st.button("📧 Email", disabled=True, key=f"mail_dis_{key_prefix}_{cid}", use_container_width=True)
        with col_w:
            wa = wa_number(phone_c)
            if wa:
                st.link_button("💬 WhatsApp", f"https://wa.me/{wa}", use_container_width=True)
            else:
                st.button("💬 WA", disabled=True, key=f"wa_dis_{key_prefix}_{cid}", use_container_width=True)

    st.markdown('<hr class="light">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE ACCUEIL
# ══════════════════════════════════════════════════════════════════════════════

def page_home():
    st.markdown('<h1 style="font-family:Syne,sans-serif;font-size:1.8rem;">🏠 Recherche & Matching</h1>', unsafe_allow_html=True)
    show_notifications()

    contacts = db.get_all_contacts()
    if not contacts:
        st.warning("Base vide. Uploadez des CVs via **📤 Upload CV**.")
        return

    show_campaign_bar()
    show_campaign_panel()

    tab1, tab2 = st.tabs(["🔍 Recherche", "🎯 Matching Appel d'Offres"])

    with tab1:
        st.markdown("Tapez un mot, plusieurs mots ou une phrase. Cochez les profils qui vous interessent.")
        query = st.text_input("Recherche", placeholder="Ex : RGPD, consultant immobilier 5 ans...",
                               key="unified_query", label_visibility="collapsed")
        top_n = st.slider("Resultats", 3, 20, 10, key="search_top_n")

        if query and len(query.strip()) >= 2:
            results = db.search_contacts(query)
            if not results:
                st.info(f"Aucun resultat pour {query}")
            else:
                crit_local = sc.keyword_criteria(query)
                ranked     = sc.rank_contacts(results, crit_local, top_n=top_n)
                st.caption(f"**{len(ranked)} profil(s)** — tries par pertinence")

                ca, _ = st.columns([2, 5])
                with ca:
                    if st.button("🤖 Affiner avec l'IA", key="ai_btn", use_container_width=True):
                        with st.spinner("Analyse..."):
                            try:
                                crit_ai = sc.extract_criteria_from_text(query)
                                st.session_state["ai_results"]  = sc.rank_contacts(contacts, crit_ai, top_n=top_n)
                                st.session_state["ai_criteria"] = crit_ai
                                st.session_state["ai_query"]    = query
                            except Exception as e:
                                st.error(str(e))

                ai_res  = st.session_state.get("ai_results")
                ai_crit = st.session_state.get("ai_criteria")
                ai_q    = st.session_state.get("ai_query")

                if ai_res and ai_q == query:
                    parts = []
                    if ai_crit.get("poste"):     parts.append(f"<b>Poste :</b> {ai_crit['poste']}")
                    if ai_crit.get("domaines"):  parts.append("&nbsp;".join(f'<span class="badge-domain">{d}</span>' for d in ai_crit["domaines"]))
                    if ai_crit.get("mots_cles"): parts.append("&nbsp;".join(f'<span class="badge">{k}</span>' for k in ai_crit["mots_cles"][:10]))
                    if parts:
                        st.markdown(
                            '<div class="ai-box">🤖 <b>Interpretation IA</b> '
                            f'<span class="provider-pill" style="margin-left:8px;">via {ai_crit.get("_provider","?").capitalize()}</span>'
                            '<br><br>' + " &nbsp;·&nbsp; ".join(parts) + '</div>',
                            unsafe_allow_html=True,
                        )
                    for i, c in enumerate(ai_res, 1):
                        show_contact_card(c, rank=i, key_prefix=f"ai{i}")
                else:
                    for i, c in enumerate(ranked, 1):
                        show_contact_card(c, rank=i, key_prefix=f"loc{i}")

        elif not query:
            for k in ["ai_results", "ai_criteria", "ai_query"]:
                st.session_state.pop(k, None)

    with tab2:
        st.markdown("Collez le texte de votre appel d'offres ou uploadez un PDF.")
        method = st.radio("Mode", ["📋 Coller le texte", "📄 Uploader un PDF"], horizontal=True, key="ao_method")
        ao_text = ""
        if method == "📋 Coller le texte":
            ao_text = st.text_area("Texte AO", placeholder="Collez l'AO ici...", height=200, key="ao_text")
        else:
            f = st.file_uploader("PDF AO", type=["pdf"], key="ao_pdf")
            if f:
                ao_text = cvp.extract_text_from_pdf(f.getbuffer())
                st.caption(f"✅ {len(ao_text)} caracteres extraits")
                with st.expander("Voir le texte"):
                    st.text(ao_text[:2000] + ("..." if len(ao_text) > 2000 else ""))

        top_ao = st.slider("Profils", 3, 10, 5, key="ao_top_n")

        if st.button("🎯 Lancer le matching", type="primary", key="ao_btn", disabled=not ao_text.strip()):
            with st.spinner("Analyse AO..."):
                try:
                    crit = sc.extract_criteria_from_text(ao_text)
                    st.session_state["ao_criteria"] = crit
                except Exception as e:
                    st.error(str(e)); st.stop()

            st.markdown('<div class="section-title">Criteres extraits</div>', unsafe_allow_html=True)
            ca, cb = st.columns(2)
            with ca:
                st.markdown(f"**Poste :** {crit.get('poste') or '—'}")
                st.markdown(f"**Annees min :** {crit.get('annees_min', 0)}")
                st.markdown(f"**Resume :** {crit.get('resume', '—')}")
            with cb:
                if crit.get("domaines"):  st.markdown(" ".join(f'<span class="badge-domain">{d}</span>' for d in crit["domaines"]), unsafe_allow_html=True)
                if crit.get("mots_cles"): st.markdown(" ".join(f'<span class="badge">{k}</span>' for k in crit["mots_cles"][:12]), unsafe_allow_html=True)
            st.markdown(f'<span class="provider-pill">via {crit.get("_provider","?").capitalize()}</span>', unsafe_allow_html=True)
            st.markdown('<hr class="light">', unsafe_allow_html=True)

            with st.spinner("Scoring..."):
                ranked = sc.rank_contacts(contacts, crit, top_n=top_ao)

            if not ranked:
                st.info("Aucun profil correspondant.")
            else:
                st.markdown(f'<div class="section-title">🏆 Top {len(ranked)} profils</div>', unsafe_allow_html=True)
                for i, c in enumerate(ranked, 1):
                    show_contact_card(c, rank=i, key_prefix=f"ao{i}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def page_upload():
    st.markdown('<h1 style="font-family:Syne,sans-serif;font-size:1.8rem;">📤 Upload CV</h1>', unsafe_allow_html=True)

    if "pending" not in st.session_state: st.session_state.pending = {}
    if "errors"  not in st.session_state: st.session_state.errors  = {}

    files = st.file_uploader("Choisir des PDFs", type=["pdf"], accept_multiple_files=True)
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
            st.markdown(f'<span class="provider-pill">via {data.get("_provider","?").capitalize()}</span>', unsafe_allow_html=True)
            with st.form(key=f"form_confirm_{filename}"):
                c1, c2 = st.columns(2)
                prenom = c1.text_input("Prenom",    value=data.get("prenom") or "")
                nom    = c2.text_input("Nom",       value=data.get("nom") or "")
                email  = c1.text_input("Email",     value=data.get("email") or "")
                tel    = c2.text_input("Telephone", value=data.get("telephone") or "")
                poste  = st.text_input("Poste",     value=data.get("poste") or "")
                annees = st.number_input("Annees", min_value=0, max_value=50, value=int(data.get("annees_experience") or 0))
                doms   = st.multiselect("Domaines (max 3)", DOMAINES,
                                        default=[d for d in data.get("domaines_fonctionnels", []) if d in DOMAINES],
                                        max_selections=3)
                comps  = st.text_area("Competences (une par ligne)", value="\n".join(data.get("competences", [])), height=80)
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
    st.markdown('<h1 style="font-family:Syne,sans-serif;font-size:1.8rem;">👥 Base de Contacts</h1>', unsafe_allow_html=True)

    show_campaign_bar()
    show_campaign_panel()

    contacts = db.get_all_contacts()
    if not contacts:
        st.info("Aucun contact.")
        return

    q = st.text_input("🔍 Filtrer", placeholder="nom, poste, competence...")
    if q: contacts = db.search_contacts(q)
    st.markdown(f"**{len(contacts)} contact(s)**")

    for i, c in enumerate(contacts):
        show_contact_card(c, key_prefix=f"base{i}")


# ── Router ─────────────────────────────────────────────────────────────────────

if   "🏠" in page: page_home()
elif "📤" in page: page_upload()
elif "👥" in page: page_contacts()

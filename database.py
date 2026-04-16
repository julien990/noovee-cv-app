# database.py — Compatible SQLite (local) et PostgreSQL (cloud)

import os
import json
import re
from datetime import datetime
from typing import Optional

DATABASE_URL = os.getenv("DATABASE_URL")

# Si DATABASE_URL est defini -> PostgreSQL, sinon -> SQLite local
USE_POSTGRES = bool(DATABASE_URL)


# ── Connexion ──────────────────────────────────────────────────────────────────

def get_connection():
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        import sqlite3
        from pathlib import Path
        conn = sqlite3.connect(Path("noovee.db"))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn


def placeholder(n: int = 1) -> str:
    """Retourne le bon placeholder selon le driver (%s pour PG, ? pour SQLite)."""
    if USE_POSTGRES:
        return ", ".join(["%s"] * n)
    return ", ".join(["?"] * n)


def ph() -> str:
    """Placeholder unique."""
    return "%s" if USE_POSTGRES else "?"


# ── Init DB ────────────────────────────────────────────────────────────────────

def init_db():
    conn = get_connection()
    try:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS contacts (
                    id                    SERIAL PRIMARY KEY,
                    nom                   TEXT,
                    prenom                TEXT,
                    email                 TEXT,
                    telephone             TEXT,
                    poste                 TEXT,
                    annees_experience     INTEGER DEFAULT 0,
                    competences           TEXT DEFAULT '[]',
                    domaines_fonctionnels TEXT DEFAULT '[]',
                    entreprises           TEXT DEFAULT '[]',
                    experiences           TEXT DEFAULT '[]',
                    texte_brut            TEXT,
                    cv_filename           TEXT,
                    created_at            TEXT,
                    updated_at            TEXT
                )
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS contacts (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom                   TEXT,
                    prenom                TEXT,
                    email                 TEXT,
                    telephone             TEXT,
                    poste                 TEXT,
                    annees_experience     INTEGER DEFAULT 0,
                    competences           TEXT DEFAULT '[]',
                    domaines_fonctionnels TEXT DEFAULT '[]',
                    entreprises           TEXT DEFAULT '[]',
                    experiences           TEXT DEFAULT '[]',
                    texte_brut            TEXT,
                    cv_filename           TEXT,
                    created_at            TEXT,
                    updated_at            TEXT
                )
            """)
        conn.commit()
    finally:
        conn.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _encode(value) -> str:
    return json.dumps(value, ensure_ascii=False) if value else "[]"

def _decode(value) -> list:
    if not value:
        return []
    try:
        return json.loads(value)
    except Exception:
        return []

def _clean_str(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if s.lower() in ("null", "none", "", "n/a", "na"):
        return None
    return s

def _row_to_dict(row, cursor=None) -> dict:
    if USE_POSTGRES:
        cols = [desc[0] for desc in cursor.description]
        d = dict(zip(cols, row))
    else:
        d = dict(row)

    for field in ("nom", "prenom", "email", "telephone", "poste"):
        d[field] = _clean_str(d.get(field))
    for field in ("competences", "domaines_fonctionnels", "entreprises", "experiences"):
        d[field] = _decode(d.get(field))
    return d


def _rows_to_dicts(rows, cursor) -> list:
    return [_row_to_dict(row, cursor) for row in rows]


# ── CRUD ───────────────────────────────────────────────────────────────────────

def insert_contact(data: dict) -> int:
    now = datetime.now().isoformat()
    p   = ph()
    sql = f"""
        INSERT INTO contacts (
            nom, prenom, email, telephone, poste,
            annees_experience, competences, domaines_fonctionnels,
            entreprises, experiences, texte_brut, cv_filename,
            created_at, updated_at
        ) VALUES ({placeholder(14)})
    """
    values = (
        _clean_str(data.get("nom")),
        _clean_str(data.get("prenom")),
        _clean_str(data.get("email")),
        _clean_str(data.get("telephone")),
        _clean_str(data.get("poste")),
        data.get("annees_experience", 0),
        _encode(data.get("competences", [])),
        _encode(data.get("domaines_fonctionnels", [])),
        _encode(data.get("entreprises", [])),
        _encode(data.get("experiences", [])),
        (data.get("texte_brut", "") or "")[:8000],
        data.get("cv_filename"),
        now, now,
    )

    conn = get_connection()
    try:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute(sql + " RETURNING id", values)
            new_id = cur.fetchone()[0]
        else:
            cur.execute(sql, values)
            new_id = cur.lastrowid
        conn.commit()
        return new_id
    finally:
        conn.close()


def update_contact(contact_id: int, data: dict):
    now = datetime.now().isoformat()
    p   = ph()
    sql = f"""
        UPDATE contacts SET
            nom={p}, prenom={p}, email={p}, telephone={p}, poste={p},
            annees_experience={p}, competences={p}, domaines_fonctionnels={p},
            entreprises={p}, experiences={p}, texte_brut={p}, updated_at={p}
        WHERE id={p}
    """
    values = (
        _clean_str(data.get("nom")),
        _clean_str(data.get("prenom")),
        _clean_str(data.get("email")),
        _clean_str(data.get("telephone")),
        _clean_str(data.get("poste")),
        data.get("annees_experience", 0),
        _encode(data.get("competences", [])),
        _encode(data.get("domaines_fonctionnels", [])),
        _encode(data.get("entreprises", [])),
        _encode(data.get("experiences", [])),
        (data.get("texte_brut", "") or "")[:8000],
        now,
        contact_id,
    )
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, values)
        conn.commit()
    finally:
        conn.close()


def delete_contact(contact_id: int):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM contacts WHERE id={ph()}", (contact_id,))
        conn.commit()
    finally:
        conn.close()


def get_all_contacts() -> list:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM contacts ORDER BY created_at DESC")
        rows = cur.fetchall()
        return _rows_to_dicts(rows, cur)
    finally:
        conn.close()


def search_contacts(query: str) -> list:
    words = [w.strip() for w in re.split(r"[\s,;]+", query.lower()) if len(w.strip()) >= 2]
    if not words:
        return get_all_contacts()

    p = ph()
    conditions, params = [], []
    for word in words:
        q = f"%{word}%"
        if USE_POSTGRES:
            conditions.append("""(
                lower(nom) LIKE %s OR lower(prenom) LIKE %s OR lower(poste) LIKE %s
                OR lower(competences) LIKE %s OR lower(domaines_fonctionnels) LIKE %s
                OR lower(entreprises) LIKE %s OR lower(texte_brut) LIKE %s
            )""")
        else:
            conditions.append("""(
                lower(nom) LIKE ? OR lower(prenom) LIKE ? OR lower(poste) LIKE ?
                OR lower(competences) LIKE ? OR lower(domaines_fonctionnels) LIKE ?
                OR lower(entreprises) LIKE ? OR lower(texte_brut) LIKE ?
            )""")
        params.extend([q, q, q, q, q, q, q])

    where = " OR ".join(conditions)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM contacts WHERE {where} ORDER BY created_at DESC", params)
        rows = cur.fetchall()
        return _rows_to_dicts(rows, cur)
    finally:
        conn.close()


def count_contacts() -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM contacts")
        return cur.fetchone()[0]
    finally:
        conn.close()


def get_tracked_filenames() -> set:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT cv_filename FROM contacts WHERE cv_filename IS NOT NULL")
        return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def find_duplicates() -> list:
    contacts = get_all_contacts()
    groups = {}
    for c in contacts:
        keys = []
        email  = (c.get("email") or "").lower().strip()
        nom    = (c.get("nom") or "").lower().strip()
        prenom = (c.get("prenom") or "").lower().strip()
        if email: keys.append(f"email:{email}")
        if nom and prenom: keys.append(f"name:{prenom}_{nom}")
        for key in keys:
            if key not in groups: groups[key] = []
            if not any(x["id"] == c["id"] for x in groups[key]):
                groups[key].append(c)

    duplicates = [g for g in groups.values() if len(g) > 1]
    unique, seen_ids = [], []
    for group in duplicates:
        ids = frozenset(c["id"] for c in group)
        if ids not in seen_ids:
            seen_ids.append(ids)
            unique.append(group)
    return unique


def clean_null_strings():
    """Nettoie les chaines null existantes en base."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        for field in ("nom", "prenom", "email", "telephone", "poste"):
            cur.execute(f"""
                UPDATE contacts SET {field} = NULL
                WHERE lower(trim(CAST({field} AS TEXT))) IN ('null', 'none', 'n/a', 'na', '')
            """)
        conn.commit()
    finally:
        conn.close()

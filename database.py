# database.py

import sqlite3
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path("noovee.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
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


def _encode(value) -> str:
    return json.dumps(value, ensure_ascii=False) if value else "[]"

def _decode(value: Optional[str]) -> list:
    if not value:
        return []
    try:
        return json.loads(value)
    except Exception:
        return []

def _row_to_dict(row) -> dict:
    d = dict(row)
    for field in ("competences", "domaines_fonctionnels", "entreprises", "experiences"):
        d[field] = _decode(d.get(field))
    return d


def insert_contact(data: dict) -> int:
    now = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO contacts (
                nom, prenom, email, telephone, poste,
                annees_experience, competences, domaines_fonctionnels,
                entreprises, experiences, texte_brut, cv_filename,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get("nom"), data.get("prenom"),
            data.get("email"), data.get("telephone"), data.get("poste"),
            data.get("annees_experience", 0),
            _encode(data.get("competences", [])),
            _encode(data.get("domaines_fonctionnels", [])),
            _encode(data.get("entreprises", [])),
            _encode(data.get("experiences", [])),
            (data.get("texte_brut", "") or "")[:8000],
            data.get("cv_filename"), now, now,
        ))
        conn.commit()
        return cursor.lastrowid


def update_contact(contact_id: int, data: dict):
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute("""
            UPDATE contacts SET
                nom=?, prenom=?, email=?, telephone=?, poste=?,
                annees_experience=?, competences=?, domaines_fonctionnels=?,
                entreprises=?, experiences=?, texte_brut=?, updated_at=?
            WHERE id=?
        """, (
            data.get("nom"), data.get("prenom"),
            data.get("email"), data.get("telephone"), data.get("poste"),
            data.get("annees_experience", 0),
            _encode(data.get("competences", [])),
            _encode(data.get("domaines_fonctionnels", [])),
            _encode(data.get("entreprises", [])),
            _encode(data.get("experiences", [])),
            (data.get("texte_brut", "") or "")[:8000],
            now, contact_id,
        ))
        conn.commit()


def delete_contact(contact_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
        conn.commit()


def get_all_contacts() -> list:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM contacts ORDER BY created_at DESC").fetchall()
    return [_row_to_dict(r) for r in rows]


def search_contacts(query: str) -> list:
    words = [w.strip() for w in re.split(r"[\s,;]+", query.lower()) if len(w.strip()) >= 2]
    if not words:
        return get_all_contacts()

    conditions, params = [], []
    for word in words:
        q = f"%{word}%"
        conditions.append("""(
            lower(nom) LIKE ? OR lower(prenom) LIKE ? OR lower(poste) LIKE ?
            OR lower(competences) LIKE ? OR lower(domaines_fonctionnels) LIKE ?
            OR lower(entreprises) LIKE ? OR lower(texte_brut) LIKE ?
        )""")
        params.extend([q, q, q, q, q, q, q])

    where = " OR ".join(conditions)
    with get_connection() as conn:
        rows = conn.execute(f"SELECT * FROM contacts WHERE {where} ORDER BY created_at DESC", params).fetchall()
    return [_row_to_dict(r) for r in rows]


def count_contacts() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]


def get_tracked_filenames() -> set:
    with get_connection() as conn:
        rows = conn.execute("SELECT cv_filename FROM contacts WHERE cv_filename IS NOT NULL").fetchall()
    return {r["cv_filename"] for r in rows}


def find_duplicates() -> list:
    contacts = get_all_contacts()
    groups = {}

    for c in contacts:
        keys = []
        email  = (c.get("email") or "").lower().strip()
        nom    = (c.get("nom") or "").lower().strip()
        prenom = (c.get("prenom") or "").lower().strip()

        if email:
            keys.append(f"email:{email}")
        if nom and prenom:
            keys.append(f"name:{prenom}_{nom}")

        for key in keys:
            if key not in groups:
                groups[key] = []
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

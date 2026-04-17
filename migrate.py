import sqlite3, os
from dotenv import load_dotenv
load_dotenv()
import psycopg2

conn_local = sqlite3.connect('noovee.db')
conn_local.row_factory = sqlite3.Row
rows = conn_local.execute('SELECT * FROM contacts').fetchall()
conn_local.close()
print(f"{len(rows)} contacts trouves en local")

conn_pg = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn_pg.cursor()
ok = 0
for r in rows:
    try:
        cur.execute("""
            INSERT INTO contacts (nom,prenom,email,telephone,poste,
                annees_experience,competences,domaines_fonctionnels,
                entreprises,experiences,texte_brut,cv_filename,
                created_at,updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            r['nom'], r['prenom'], r['email'], r['telephone'], r['poste'],
            r['annees_experience'], r['competences'], r['domaines_fonctionnels'],
            r['entreprises'], r['experiences'],
            (r['texte_brut'] or '')[:8000],
            r['cv_filename'], r['created_at'], r['updated_at']
        ))
        ok += 1
    except Exception as e:
        print(f'Erreur: {e}')

conn_pg.commit()
conn_pg.close()
print(f"{ok}/{len(rows)} contacts migres avec succes")

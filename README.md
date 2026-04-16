# 📄 Noovee - CV Manager Pro

Une **plateforme intelligente** de gestion de CV et matching automatique avec IA. Analysez, catégorisez et matchchez les CV avec les appels d'offres en quelques secondes.

## ✨ Fonctionnalités principales

### 🤖 Intelligence Artificielle
- **Extraction automatique** des infos CV (Mistral + Claude)
- **Analyse multi-fournisseurs** IA pour fiabilité maximale
- **Scoring intelligent** basé sur les compétences
- **Matching automatique** CV ↔ Appel d'offres

### 📤 Import flexible
- ✅ Support **PPTX** (PowerPoint)
- ✅ Support **DOCX** (Word)
- ✅ Support **PDF**
- ✅ Conversion auto en PDF via LibreOffice

### 📊 Gestion complète
- Extraction de **15+ champs** par CV :
  - Infos de base (nom, email, téléphone)
  - Profils (LinkedIn, GitHub)
  - Compétences (liste complète)
  - Formations et certifications
  - Langues et disponibilité
  - Salaire attendu
  - Localisation et notes

- **Base de données JSON** avec :
  - Métadonnées complètes
  - Historique des modifications
  - Système de favoris
  - Tags personnalisés
  - Notes internes

### 🔍 Recherche avancée
- Recherche par compétence
- Filtrage par secteur
- Recherche textuelle complète
- Suggestions intelligentes

### 📈 Outils professionnels
- Export CSV / JSON
- Backup automatique
- Statistiques en temps réel
- Gestion des versions

## 🚀 Installation rapide

### Prérequis
- Python 3.8+
- LibreOffice (pour conversion PDF)
- Clés API (Mistral, Claude, ou similaire)

### Étapes

1. **Cloner le repo**
```bash
git clone https://github.com/yourusername/noovee.git
cd noovee
```

2. **Créer un environnement virtuel**
```bash
python -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate
```

3. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

4. **Configurer les clés API**
```bash
cp .env.example .env
# Éditer .env et ajouter vos clés API
nano .env
```

5. **Lancer l'application**
```bash
streamlit run app_final.py
```

L'app s'ouvre sur `http://localhost:8501`

## 📖 Guide d'utilisation

### 1. Ajouter un CV

1. Allez à l'onglet **➕ Ajouter CV**
2. Uploadez un fichier (PPTX, DOCX, PDF)
3. L'IA analyse automatiquement le CV
4. Validez/modifiez les infos extraites
5. Cliquez "✅ Valider" → Sauvegarde auto

### 2. Gérer les CVs

- **Onglet 📋 Mes CVs** : Voir tous les CVs, rechercher, modifier
- Cliquez sur "📋" pour voir les détails complets
- Marquez en favoris avec "⭐"
- Supprimez avec "🗑"

### 3. Rechercher

**Onglet 🔍 Recherche** :
- Filtrer par compétence
- Filtrer par secteur
- Combinaison des deux

### 4. Scorer un appel d'offres

**Onglet ⭐ Scoring** :
1. Entrez les compétences requises
2. Le système score automatiquement chaque CV
3. Classement par score ↓

### 5. Exporter les données

**Onglet 📊 Export** :
- Télécharger CSV (pour Excel)
- Télécharger JSON (pour intégration)

## 🔧 Configuration

### Variables d'environnement (.env)

```env
# Fournisseurs IA (minimum 1 requis)
MISTRAL_API_KEY=xxx        # Recommandé pour extraction
ANTHROPIC_API_KEY=xxx      # Claude (fallback)
OPENAI_API_KEY=xxx         # GPT-4o (fallback)

# Optionnel
GROQ_API_KEY=xxx
GEMINI_API_KEY=xxx
```

### Chemins de stockage

Modifiez dans le code (ligne 20-30) si nécessaire :
```python
PATH_LOCAL = "/chemin/vers/dossier/CVs"
PATH_DOSSIER = ...  # Dossier des fichiers
PATH_PDF = ...      # Dossier des PDFs
PATH_DB = ...       # Base de données JSON
PATH_BACKUP = ...   # Dossiers des backups
```

## 📊 Structure des données

### Fiche contact (contacts_db.json)

```json
{
  "cv_123": {
    "id": "cv_123",
    "nom": "Dupont",
    "prenom": "Jean",
    "email": "jean@example.com",
    "telephone": "+33612345678",
    "linkedin": "https://linkedin.com/in/jean-dupont",
    "github": "https://github.com/jeandupont",
    "secteur": "Tech",
    "poste": "Senior Developer Python",
    "competences": ["Python", "FastAPI", "PostgreSQL", ...],
    "experience_ans": "8",
    "location": "Paris",
    "formations": ["Master Informatique - Sorbonne - 2015"],
    "certifications": ["AWS Solutions Architect - 2023"],
    "salaire_attendu": "65000€",
    "disponibilite": "2 semaines",
    "langues": ["Français", "Anglais", "Allemand"],
    "notes": "Excellent candidat, forte expérience cloud",
    "date_ajout": "2025-04-16T10:30:00",
    "date_modif": "2025-04-16T10:45:00",
    "tags": ["python", "senior", "aws"],
    "favoris": true,
    "score_global": 85,
    "ia_enrichi": true,
    "whatsapp_envoye": false,
    "notes_personnelles": "À recontacter semaine prochaine",
    "historique": [],
    "matches": []
  }
}
```

## 🤖 Fournisseurs IA supportés

| Fournisseur | Pour | Priorité | Coût |
|---|---|---|---|
| **Mistral** 🇫🇷 | Extraction | 1️⃣ | Très abordable |
| **Claude** (Anthropic) | Extraction/Fallback | 2️⃣ | Moyen |
| **GPT-4o** (OpenAI) | Scoring | 3️⃣ | Moyen |
| **Groq** | Fallback | 4️⃣ | Gratuit (limité) |
| **Gemini** | Fallback | 5️⃣ | Gratuit (limité) |

### Coûts estimés (par 1000 CVs)

- Mistral : ~3€
- Claude : ~5€
- GPT-4o : ~8€
- Groq : 0€ (limité)

## 📁 Structure du projet

```
noovee/
├── app_final.py              # Application principale
├── requirements.txt          # Dépendances Python
├── .env.example             # Exemple de configuration
├── .gitignore              # Fichiers à ignorer
├── README.md               # Ce fichier
├── LICENSE                 # Licence
└── docs/
    ├── INSTALLATION.md
    ├── API.md
    └── TROUBLESHOOTING.md
```

## 🔐 Sécurité

### Recommandations

1. **Ne jamais commiter .env** → Utiliser `.env.example`
2. **Clés API en variables d'environnement** → Jamais en dur dans le code
3. **HTTPS en production** → Toujours utiliser SSL/TLS
4. **Backups réguliers** → Auto-créés, à stocker sécurisé
5. **Données sensibles** → Pas de données réelles en dev

### Données sensibles

Le fichier `contacts_db.json` contient des données personnelles :
- Emails
- Téléphones
- CVs
- Salaires

**À protéger comme confidentiel !**

## 🐛 Troubleshooting

### "LibreOffice non installé"
```bash
# macOS
brew install libreoffice

# Linux (Ubuntu/Debian)
sudo apt-get install libreoffice

# Windows
# Télécharger depuis https://www.libreoffice.org/
```

### "Erreur extraction PDF"
- Vérifier que pypdf est installé
- Le PDF n'est pas un scan/image → Utiliser OCR
- Convertir manuellement en texte d'abord

### "Clé API invalid"
- Vérifier le format de la clé
- Vérifier qu'elle est active sur le tableau de bord du fournisseur
- Tester avec cURL : `curl -H "Authorization: Bearer YOUR_KEY" ...`

### "Streamlit très lent"
- Réduire le nombre de CVs (paginer)
- Optimiser les recherches (indexation)
- Utiliser un cache (Redis)

## 📈 Roadmap v3.0

- [ ] Interface web React/Next.js
- [ ] Authentification multi-utilisateurs
- [ ] API REST pour intégrations
- [ ] Webhooks WhatsApp
- [ ] OCR pour scans
- [ ] Analytics avancées
- [ ] Déploiement Cloud (Docker)
- [ ] Support multiple langues

## 🤝 Contribution

Les contributions sont bienvenues !

1. **Fork** le repo
2. **Créer une branche** : `git checkout -b feature/ma-feature`
3. **Committer** : `git commit -m "Add ma-feature"`
4. **Push** : `git push origin feature/ma-feature`
5. **Pull Request**

## 📝 License

MIT - Voir `LICENSE` pour les détails

## 💬 Support

- 📧 Email : support@noovee.io
- 🐛 Issues : GitHub Issues
- 💡 Discussions : GitHub Discussions
- 📚 Docs : [docs.noovee.io](https://docs.noovee.io)

## 👨‍💻 Auteur

Créé par l'équipe Noovee

## 🙏 Remerciements

- Streamlit pour la framework
- Mistral pour l'IA extraction
- Anthropic Claude pour le fallback
- La communauté Python

---

**⭐ Si vous aimez ce projet, laissez une star sur GitHub !**

**Made with ❤️ for recruitment professionals**

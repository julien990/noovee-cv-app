# ============================================================================
# NOOVEE - COMMANDES GIT COMPLÈTES (Copier-coller direct)
# ============================================================================
#
# Cet article contient toutes les commandes pour créer et pousser
# votre projet Noovee sur GitHub en 10 minutes
#
# ============================================================================

# PRÉALABLE : Créer un repository sur GitHub
# ==========
# 1. Allez sur https://github.com/new
# 2. Nommez : "noovee"
# 3. Description : "CV Manager Pro - Plateforme intelligente avec IA"
# 4. Visibility : Public (recommandé)
# 5. ❌ NE COCHEZ PAS "Initialize this repository with a README"
# 6. Cliquez "Create repository"
# 7. Notez votre URL: https://github.com/VOTRE_USERNAME/noovee


# ============================================================================
# PREMIÈRE FOIS SEULEMENT - Configuration Git (30 secondes)
# ============================================================================

# Configurez votre identité Git (une fois pour toutes)
git config --global user.name "Votre Nom"
git config --global user.email "votre@email.com"

# Générer une clé SSH (optionnel mais recommandé)
# ssh-keygen -t ed25519 -C "votre@email.com"
# Puis ajouter la clé sur GitHub : https://github.com/settings/ssh


# ============================================================================
# INITIALISER LE REPO LOCAL (5 minutes)
# ============================================================================

# 1. Se positionner dans le dossier du projet
cd /home/claude

# 2. Initialiser Git
git init

# 3. Ajouter TOUS les fichiers
git add -A

# 4. Vérifier les fichiers
git status

# 5. Créer le commit initial
git commit -m "Initial commit: Noovee v2.0 - CV Manager Pro

- ✨ Extraction automatique de CVs (PPTX, DOCX, PDF)
- 🤖 Analyse IA multi-fournisseurs (Mistral + Claude)
- 📊 Scoring et matching intelligents
- 🔍 Recherche avancée
- 📈 Export CSV/JSON
- 💾 Backup automatique
- 🎨 Interface Streamlit moderne
- 🚀 Déploiement Docker inclus"

# 6. Renommer la branche par défaut en 'main'
git branch -M main

# 7. Ajouter le remote GitHub (REMPLACER votre_username)
git remote add origin https://github.com/votre_username/noovee.git

# 8. Vérifier que le remote est bien ajouté
git remote -v

# 9. POUSSER sur GitHub ⬆️
git push -u origin main


# ============================================================================
# RÉSULTAT
# ============================================================================
# ✅ Votre code est maintenant sur GitHub !
# Accédez-y avec : https://github.com/votre_username/noovee


# ============================================================================
# POUR LES PROCHAINS MODIFICATIONS
# ============================================================================

# Après chaque changement, utilisez ces 3 commandes :

# 1. Ajouter les fichiers modifiés
git add -A

# 2. Créer un commit avec un message clair
git commit -m "Description brève du changement"

# 3. Pousser sur GitHub
git push


# ============================================================================
# COMMANDES UTILES
# ============================================================================

# Voir le statut actuel
git status

# Voir l'historique des commits
git log --oneline

# Voir les 5 derniers commits avec plus de détails
git log -5 --pretty=format:"%h - %s (%an, %ar)"

# Annuler le dernier commit (avant push)
git reset HEAD~1

# Annuler le dernier commit (après push - crée un nouveau commit)
git revert HEAD

# Créer une branche de développement
git checkout -b feature/ma-feature
git push -u origin feature/ma-feature

# Revenir sur main
git checkout main
git pull origin main

# Fusionner une branche dans main
git merge feature/ma-feature
git push


# ============================================================================
# TROUBLESHOOTING
# ============================================================================

# Erreur : "fatal: not a git repository"
# Solution : git init

# Erreur : "fatal: pathspec 'app_final.py' did not match"
# Solution : Vérifier que vous êtes dans le bon dossier (cd /chemin)

# Erreur : "Permission denied (publickey)"
# Solution : Configurer SSH (voir plus haut) ou utiliser HTTPS

# Erreur : "The current branch master has no upstream branch"
# Solution : git push -u origin main (ou votre nom de branche)

# Erreur : "Would clobber existing tag"
# Solution : git tag -d nom_tag && git push origin :nom_tag


# ============================================================================
# DÉPLOYER AVEC DOCKER (Optionnel)
# ============================================================================

# Builder l'image Docker
docker build -t noovee:latest .

# Lancer le conteneur
docker run -p 8501:8501 --env-file .env noovee:latest

# Ou avec Docker Compose
docker-compose up -d

# Voir les logs
docker-compose logs -f


# ============================================================================
# VÉRIFICATION FINALE
# ============================================================================

# Votre repo doit avoir cette structure :
# noovee/
# ├── app_final.py              ✅
# ├── requirements.txt          ✅
# ├── .env.example             ✅
# ├── .gitignore              ✅
# ├── README.md               ✅
# ├── LICENSE                 ✅
# ├── setup.sh                ✅
# ├── Dockerfile              ✅
# ├── docker-compose.yml      ✅
# ├── .streamlit/config.toml  ✅
# └── GITHUB_SETUP.sh         ✅

# Lisez les fichiers pour confirmer
ls -la

# Vérifiez le contenu du git
git ls-files


# ============================================================================
# PROCHAINES ÉTAPES
# ============================================================================

# 1. Testez localement d'abord
#    streamlit run app_final.py

# 2. Puis pusher sur GitHub
#    git push

# 3. Ajouter des collaborateurs
#    GitHub Settings > Collaborators

# 4. Configurer les GitHub Actions (CI/CD - avancé)
#    Créer .github/workflows/test.yml

# 5. Configurer les branches protégées (recommandé)
#    GitHub Settings > Branches > Add rule

# ============================================================================
# LIENS UTILES
# ============================================================================
#
# GitHub Docs:      https://docs.github.com/
# Git Cheatsheet:   https://github.github.com/training-kit/
# SSH Setup:        https://docs.github.com/en/authentication/connecting-to-github-with-ssh
# Docker:           https://docs.docker.com/
#
# ============================================================================

Fin des commandes.
Besoin d'aide ? Consultez les liens utiles ci-dessus ! 🚀

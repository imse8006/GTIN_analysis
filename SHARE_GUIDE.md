# 📊 Guide de Partage - GTIN Quality Dashboard

## Option 1 : Streamlit Cloud (Recommandé - Le plus simple)

### Étapes :

1. **Créer un compte GitHub** (si vous n'en avez pas)
   - Allez sur https://github.com
   - Créez un compte gratuit

2. **Créer un nouveau repository**
   - Cliquez sur "New repository"
   - Nommez-le (ex: `gtin-dashboard`)
   - Cochez "Public" ou "Private" selon vos préférences
   - Ne cochez PAS "Initialize with README"

3. **Pousser votre code sur GitHub**
   ```bash
   git init
   git add gtin_dashboard.py requirements.txt all-products-prod-2026-01-13_15.30.30.xlsx
   git commit -m "Initial commit - GTIN Dashboard"
   git branch -M main
   git remote add origin https://github.com/VOTRE_USERNAME/gtin-dashboard.git
   git push -u origin main
   ```

4. **Déployer sur Streamlit Cloud**
   - Allez sur https://share.streamlit.io
   - Connectez-vous avec votre compte GitHub
   - Cliquez sur "New app"
   - Sélectionnez votre repository
   - Main file path: `gtin_dashboard.py`
   - Cliquez sur "Deploy"
   - Votre dashboard sera accessible via un lien comme : `https://votre-app.streamlit.app`

5. **Partager le lien avec Dianne**
   - Envoyez-lui simplement le lien Streamlit Cloud
   - Elle pourra accéder au dashboard depuis n'importe quel navigateur

---

## Option 2 : Partage Local (Code + Instructions)

### Fichiers à partager :

1. **gtin_dashboard.py** - Le script principal
2. **requirements.txt** - Les dépendances
3. **all-products-prod-2026-01-13_15.30.30.xlsx** - Le fichier de données
4. **SHARE_GUIDE.md** - Ce guide

### Instructions pour Dianne :

1. **Installer Python** (si pas déjà installé)
   - Télécharger depuis https://www.python.org/downloads/
   - Cocher "Add Python to PATH" lors de l'installation

2. **Ouvrir un terminal** dans le dossier du projet

3. **Créer un environnement virtuel** (optionnel mais recommandé)
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

4. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

5. **Lancer le dashboard**
   ```bash
   streamlit run gtin_dashboard.py
   ```

6. **Accéder au dashboard**
   - Le dashboard s'ouvrira automatiquement dans le navigateur
   - URL : http://localhost:8501

---

## Option 3 : Exécutable Standalone (Avancé)

Si vous voulez créer un fichier .exe que Dianne peut lancer sans installer Python :

1. Installer PyInstaller :
   ```bash
   pip install pyinstaller
   ```

2. Créer l'exécutable :
   ```bash
   pyinstaller --onefile --add-data "all-products-prod-2026-01-13_15.30.30.xlsx;." gtin_dashboard.py
   ```

3. Partager le fichier .exe généré dans le dossier `dist/`

**Note :** Cette option est plus complexe et le fichier sera volumineux.

---

## Recommandation

**Option 1 (Streamlit Cloud)** est la meilleure solution car :
- ✅ Aucune installation nécessaire pour Dianne
- ✅ Accessible depuis n'importe où
- ✅ Mise à jour facile (juste push sur GitHub)
- ✅ Professionnel et fiable
- ✅ Gratuit

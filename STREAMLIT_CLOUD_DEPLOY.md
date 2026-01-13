# 🚀 Déploiement sur Streamlit Cloud

Votre code est maintenant sur GitHub ! Suivez ces étapes pour déployer sur Streamlit Cloud :

## 📋 Étapes de déploiement

### 1. Accéder à Streamlit Cloud
- Allez sur https://share.streamlit.io
- Connectez-vous avec votre compte **GitHub** (le même que celui utilisé pour créer le repo)

### 2. Créer une nouvelle app
- Cliquez sur **"New app"** ou **"Deploy an app"**
- Vous serez redirigé vers la sélection du repository

### 3. Configurer l'application
- **Repository** : Sélectionnez `imse8006/GTIN_analysis`
- **Branch** : `main` (par défaut)
- **Main file path** : `gtin_dashboard.py`
- **App URL** : Vous pouvez personnaliser (ex: `gtin-dashboard`)

### 4. Déployer
- Cliquez sur **"Deploy"**
- Streamlit Cloud va :
  - Installer les dépendances depuis `requirements.txt`
  - Lancer le dashboard
  - Générer un lien public

### 5. Accéder au dashboard
- Une fois le déploiement terminé (2-3 minutes), vous obtiendrez un lien comme :
  - `https://gtin-dashboard.streamlit.app` (ou le nom que vous avez choisi)

## 🔗 Partager avec Dianne

Une fois déployé, vous pouvez simplement :
1. Copier le lien Streamlit Cloud
2. L'envoyer à Dianne par email/Teams/etc.
3. Elle pourra accéder au dashboard depuis n'importe quel navigateur, sans installation !

## ⚙️ Configuration optionnelle

Si vous voulez personnaliser davantage :
- Allez dans **Settings** de votre app sur Streamlit Cloud
- Vous pouvez configurer :
  - Le thème (déjà configuré en sombre dans le code)
  - Les secrets/environnement variables si nécessaire
  - Les ressources (CPU/RAM)

## 🔄 Mises à jour

Pour mettre à jour le dashboard :
1. Modifiez les fichiers localement
2. Faites `git add`, `git commit`, `git push`
3. Streamlit Cloud redéploiera automatiquement !

## ✅ Votre repository est prêt !

**Repository GitHub** : https://github.com/imse8006/GTIN_analysis.git

**Fichiers inclus** :
- ✅ `gtin_dashboard.py` - Le dashboard
- ✅ `requirements.txt` - Les dépendances
- ✅ `all-products-prod-2026-01-13_15.30.30.xlsx` - Les données
- ✅ `README.md` - Documentation

Tout est prêt pour le déploiement ! 🎉

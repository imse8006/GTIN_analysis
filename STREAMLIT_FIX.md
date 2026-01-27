# 🔧 Résolution des erreurs Streamlit Cloud

## Problème : "This repository does not exist"

### Solution 1 : Autoriser Streamlit Cloud sur GitHub

1. **Sur GitHub** :
   - Allez sur https://github.com/settings/applications
   - Dans "Authorized GitHub Apps", cherchez "Streamlit Cloud"
   - Si absent, autorisez-le

2. **Autoriser l'accès au repository** :
   - Allez sur votre repository : https://github.com/imse8006/GTIN_analysis
   - Cliquez sur **Settings** (en haut)
   - Dans le menu de gauche, cliquez sur **Integrations** > **Applications**
   - Cherchez "Streamlit Cloud" dans "Installed GitHub Apps"
   - Si présent, cliquez dessus et assurez-vous qu'il a accès au repository

### Solution 2 : Utiliser l'URL GitHub complète

Dans le champ "Repository" sur Streamlit Cloud, utilisez :
- **Repository** : `imse8006/GTIN_analysis`
- OU cliquez sur "Paste GitHub URL" et collez : `https://github.com/imse8006/GTIN_analysis`

### Solution 3 : Vérifier que le repository est bien public

1. Allez sur https://github.com/imse8006/GTIN_analysis
2. Cliquez sur **Settings**
3. Vérifiez sous "Danger Zone" > "Change repository visibility"
4. Si le repo est privé, vous pouvez :
   - Le rendre public (gratuit)
   - OU configurer Streamlit Cloud pour les repos privés (payant)

## Problème : "This branch does not exist"

Le repo a bien une branche `main`. Si l'erreur persiste :
1. Essayez de rafraîchir la page Streamlit Cloud
2. Vérifiez que vous avez bien sélectionné le bon repository

## Problème : "This file does not exist" - Main file path

**IMPORTANT** : Le fichier principal doit être :
- **Main file path** : `gtin_dashboard.py`

**PAS** `streamlit_app.py` !

Changez le champ "Main file path" pour mettre : `gtin_dashboard.py`

## Configuration correcte sur Streamlit Cloud

Voici la configuration exacte à utiliser :

```
Repository: imse8006/GTIN_analysis
Branch: main
Main file path: gtin_dashboard.py
App URL: (optionnel, laissez générer automatiquement)
```

## Vérification rapide

Vérifiez que tout est bien sur GitHub :
1. Allez sur https://github.com/imse8006/GTIN_analysis
2. Vérifiez que vous voyez :
   - ✅ `gtin_dashboard.py`
   - ✅ `requirements.txt`
   - ✅ `all-products-prod-2026-01-13_15.30.30.xlsx`
   - ✅ `README.md`

## Si rien ne fonctionne

1. **Rafraîchir l'autorisation GitHub** :
   - Sur Streamlit Cloud, déconnectez-vous et reconnectez-vous
   - Ré-autorisez l'accès GitHub

2. **Vérifier les permissions** :
   - Le compte GitHub utilisé sur Streamlit Cloud doit être le propriétaire du repo
   - Ou le repo doit être dans une organisation où vous avez les droits

3. **Contact support** :
   - Si tout échoue, contactez le support Streamlit Cloud

# 📊 GTIN Quality Dashboard - MDM Analysis

Dashboard interactif pour l'analyse de qualité GTIN par Legal Entity selon les règles MDM.

## 🚀 Installation Rapide

1. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

2. **Lancer le dashboard**
   ```bash
   streamlit run gtin_dashboard.py
   ```

3. **Accéder au dashboard**
   - Le dashboard s'ouvrira automatiquement dans votre navigateur
   - URL : http://localhost:8501

## 📋 Prérequis

- Python 3.8+
- Fichier Excel : `all-products-prod-2026-01-13_15.30.30.xlsx`

## 📦 Dépendances

- streamlit
- pandas
- plotly
- openpyxl
- matplotlib

## 🎯 Fonctionnalités

- Analyse de qualité GTIN par Legal Entity
- Classification selon les règles MDM :
  - **8_digits, 13_digits, 14_digits** : GTIN valides
  - **INVALID** : GTIN invalides (manquants, non numériques, longueur incorrecte, check digit invalide)
  - **GENERIC** : GTIN génériques
  - **BLOCKED** : GTIN explicitement bloqués
- Graphiques interactifs
- Filtres par Legal Entity
- Thème sombre professionnel

## 📁 Structure

```
.
├── gtin_dashboard.py          # Script principal du dashboard
├── requirements.txt           # Dépendances Python
├── all-products-prod-*.xlsx   # Fichier de données
└── README.md                  # Ce fichier
```

## 🔗 Partage

Voir `SHARE_GUIDE.md` pour les instructions de partage avec d'autres utilisateurs.

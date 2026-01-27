# 📊 GTIN Quality Dashboard

Dashboard interactif pour l'analyse de qualité GTIN par Legal Entity.

## 🚀 Installation

1. Installer les dépendances :
```bash
pip install -r requirements.txt
```

Ou dans l'environnement virtuel :
```bash
venv\Scripts\activate
pip install -r requirements.txt
```

## 🎯 Lancement

```bash
streamlit run gtin_dashboard.py
```

Ou avec l'environnement virtuel :
```bash
venv\Scripts\activate
streamlit run gtin_dashboard.py
```

Le dashboard s'ouvrira automatiquement dans votre navigateur à l'adresse : `http://localhost:8501`

## 📈 Fonctionnalités

- **Vue d'ensemble** : Métriques globales (Total, Valides, Invalides, Génériques)
- **Analyse par Legal Entity** : Tableau détaillé avec taux de conformité
- **Graphiques interactifs** :
  - Bar chart du taux de conformité par Legal Entity
  - Pie chart de la distribution des statuts
  - Stacked bar chart détaillé par Legal Entity
- **Détail par Legal Entity** : Analyse approfondie d'une Legal Entity sélectionnée

## 🎨 Caractéristiques

- Interface moderne et professionnelle
- Graphiques interactifs avec Plotly
- Filtres dynamiques par Legal Entity
- Métriques en temps réel
- Design responsive

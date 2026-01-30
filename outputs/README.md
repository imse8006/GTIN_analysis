# Résultats pré-calculés (backend batch)

Ce dossier contient **toutes** les sorties du batch : Duplicate Analysis, GTIN Quality, Generic GTIN, Generate Email (un Excel par Legal Entity). Un sous-dossier par date : `YYYY-MM-DD/`.

- **Structure** dans chaque `YYYY-MM-DD/` :
  - **Duplicate** : `overview.json`, `manifest.json`, `outer_duplicates.xlsx`, `inner_duplicates.xlsx`, `cross_duplicates.xlsx`, `generic_by_entity.xlsx`, `placeholder_by_entity.xlsx`, `suspect_by_entity.xlsx`, `valid_*.xlsx`, `outer_eq_inner_same_row.xlsx`, `inner_eq_outer_same_entity.xlsx`, `inner_eq_outer_other_entity.xlsx`, etc.
  - **Quality** : `quality_overview.json`, `quality_by_entity.xlsx`, `quality_full_classified.xlsx`, `generics_non_eupcker.xlsx`
  - **Generic GTIN** : `generic_overview.json`, `generic_conformity_by_entity.xlsx`, `generic_non_conforming.xlsx`, `generic_all_records_with_conformity.xlsx`
  - **Generate Email** : `email_reports/<Entity>.xlsx` (un rapport Excel par Legal Entity), `email_overview.json`
- **Une seule commande (batch + push)** :  
  `python run_batch_and_push.py [fichier.xlsx]`  
  Lance le batch (toutes les analyses) puis pousse `outputs/` sur GitHub.
- **Batch seul** : `python run_duplicate_analysis_batch.py <fichier.xlsx>`  
  Puis à la main : `git add outputs/` → `git commit -m "Update outputs YYYY-MM-DD"` → `git push`
- Les Excel dans `outputs/` sont pour **toutes les Legal Entities**. En filtrant par entité dans le dashboard, pas d'Excel pré-calculé pour ce filtre : les téléchargements sont générés à la volée (export du jeu filtré).

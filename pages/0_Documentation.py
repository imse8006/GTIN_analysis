"""
Documentation complète de toutes les analyses GTIN du dashboard.
Cette page explique chaque opération, comparaison et critère utilisé dans les analyses.
"""
import streamlit as st
from auth_utils import render_login_form

st.set_page_config(
    page_title="Documentation - GTIN Analysis",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main-header { font-size: 3rem; font-weight: 700; color: #94a3b8; text-align: center; margin-bottom: 2rem; padding: 1rem 0; }
    .section-header { font-size: 1.8rem; font-weight: 600; color: #94a3b8; margin-top: 2rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #475569; }
    .subsection-header { font-size: 1.3rem; font-weight: 600; color: #cbd5e1; margin-top: 1.5rem; margin-bottom: 0.8rem; }
    .code-block { background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; border: 1px solid #334155; margin: 1rem 0; }
    .info-box { background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #3b82f6; margin: 1rem 0; }
    .warning-box { background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #f59e0b; margin: 1rem 0; }
    .stApp { background-color: #0f172a; }
    </style>
""", unsafe_allow_html=True)


def check_password():
    return render_login_form("Documentation", password_key="password_doc")


def main():
    if not check_password():
        return

    st.markdown('<h1 class="main-header">📚 Documentation - GTIN Analysis Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<div style="text-align: center; color: #cbd5e1; margin-bottom: 2rem;">Guide complet de toutes les analyses et comparaisons effectuées dans le dashboard</div>', unsafe_allow_html=True)

    # Table des matières
    st.markdown('<div class="section-header">📑 Table des matières</div>', unsafe_allow_html=True)
    toc = """
    1. [Normalisation des GTINs](#normalisation)
    2. [Classification des GTINs](#classification)
    3. [Analyse de Qualité GTIN](#qualite)
    4. [Analyse des Doublons](#doublons)
    5. [GTINs Génériques](#generiques)
    6. [GTINs Placeholder](#placeholder)
    7. [GTINs Suspects](#suspects)
    8. [GTINs Valides](#valides)
    9. [Analyse Generic GTIN vs Taxonomy](#generic-taxonomy)
    """
    st.markdown(toc)

    # 1. Normalisation
    st.markdown('<div class="section-header" id="normalisation">1. Normalisation des GTINs</div>', unsafe_allow_html=True)
    st.markdown("""
    La fonction `normalize_gtin()` transforme les valeurs GTIN brutes en chaînes normalisées pour l'analyse.
    
    **Processus de normalisation :**
    
    1. **Valeurs nulles** : `None`, `NaN`, chaînes vides → `None`
    2. **Notation scientifique** : Conversion des valeurs comme `1.23E+14` en entier (`123000000000000`)
    3. **Floats avec .0** : Suppression du `.0` final (ex: `12345678901234.0` → `12345678901234`)
    4. **Trim** : Suppression des espaces avant/après
    
    **Exemples :**
    - `"12345678901234.0"` → `"12345678901234"`
    - `"1.23E+14"` → `"123000000000000"`
    - `"  12345678901234  "` → `"12345678901234"`
    - `None` ou `""` → `None`
    """)

    # 2. Classification
    st.markdown('<div class="section-header" id="classification">2. Classification des GTINs</div>', unsafe_allow_html=True)
    st.markdown("""
    La fonction `classify_gtin_status()` classe chaque GTIN selon les règles MDM.
    
    **Ordre de priorité (du plus spécifique au plus général) :**
    
    1. **EXPLICIT_BLOCKED / PLACEHOLDER** : GTINs composés uniquement de 9 (ex: `99999999999999`)
    2. **GENERIC_GTIN** : GTINs génériques de la liste explicite :
       - `10000000000009`, `20000000000009`, `30000000000009`, `40000000000009`
       - `50000000000009`, `60000000000009`, `70000000000009`, `80000000000009`
    3. **NON_NUMERIC** : Contient des caractères non numériques
    4. **INVALID_LENGTH** : Longueur différente de 8, 13 ou 14 chiffres
    5. **SUSPECT** : Format valide mais check digit GS1 invalide
    6. **GTIN_8, GTIN_13, GTIN_14** : GTINs valides selon leur longueur
    
    **Validation du check digit GS1 :**
    - Pour GTIN-13 et GTIN-14, vérification de l'algorithme GS1
    - Si le check digit est incorrect → marqué comme **SUSPECT**
    """)

    # 3. Analyse de Qualité
    st.markdown('<div class="section-header" id="qualite">3. Analyse de Qualité GTIN</div>', unsafe_allow_html=True)
    st.markdown("""
    **Page : GTIN Quality Dashboard**
    
    Cette analyse classe tous les produits selon la qualité de leur GTIN-Outer.
    
    **Métriques calculées :**
    - **Total Products** : Nombre total de produits analysés
    - **Valid GTINs** : GTINs valides (8_digits, 13_digits, 14_digits)
    - **Invalid GTINs** : GTINs invalides (MISSING, NON_NUMERIC, INVALID_LENGTH)
    - **Generic GTINs** : GTINs génériques
    - **Placeholder GTINs** : GTINs bloqués (999...99)
    - **Compliance Rate** : Pourcentage de GTINs valides
    
    **Breakdown par longueur :**
    - 8 digits : GTIN-8 valides
    - 13 digits : GTIN-13 valides
    - 14 digits : GTIN-14 valides
    """)

    # 4. Analyse des Doublons
    st.markdown('<div class="section-header" id="doublons">4. Analyse des Doublons</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="subsection-header">4.1 Cross Duplicates</div>', unsafe_allow_html=True)
    st.markdown("""
    **Définition** : GTINs qui apparaissent à la fois dans la colonne GTIN-Outer ET GTIN-Inner.
    
    **Détection** : Un GTIN normalisé apparaît dans les deux colonnes (pas forcément sur la même ligne).
    
    **Utilisation** : Identifier les GTINs partagés entre Outer et Inner, ce qui peut indiquer des erreurs de saisie.
    """)
    
    st.markdown('<div class="subsection-header">4.2 GTIN Outer Duplicates</div>', unsafe_allow_html=True)
    st.markdown("""
    **Définition** : GTIN-Outer qui apparaît plusieurs fois dans le dataset.
    
    **Détection** : Compte le nombre d'occurrences de chaque GTIN-Outer normalisé.
    
    **Analyse** :
    - **Même entité** : Le GTIN apparaît plusieurs fois dans la même Legal Entity
    - **Entités différentes** : Le GTIN est partagé entre plusieurs Legal Entities (partage valide)
    """)
    
    st.markdown('<div class="subsection-header">4.3 GTIN Inner Duplicates</div>', unsafe_allow_html=True)
    st.markdown("""
    **Définition** : GTIN-Inner qui apparaît plusieurs fois dans le dataset.
    
    **Détection** : Compte le nombre d'occurrences de chaque GTIN-Inner normalisé.
    
    **Analyse** : Identifie les GTINs intérieurs dupliqués, généralement moins problématiques que les Outer.
    """)
    
    st.markdown('<div class="subsection-header">4.4 Outer = Inner (même ligne)</div>', unsafe_allow_html=True)
    st.markdown("""
    **Définition** : Sur la même ligne, GTIN-Outer = GTIN-Inner.
    
    **Détection** : Comparaison directe des valeurs normalisées sur chaque ligne.
    
    **Cas d'usage** : Identifier les produits où Outer et Inner sont identiques (peut être normal ou suspect selon le contexte).
    """)
    
    st.markdown('<div class="subsection-header">4.5 Inner = Outer (non-Generic)</div>', unsafe_allow_html=True)
    st.markdown("""
    **Définition** : GTIN-Inner qui correspond à un GTIN-Outer d'une autre ligne (même entité ou autre entité).
    
    **Détection** : 
    - Compare chaque GTIN-Inner avec tous les GTIN-Outer
    - Exclut les Generic GTINs de l'analyse
    - Distingue même entité vs autres entités
    
    **Utilisation** : Identifier les cas où Inner correspond à Outer d'un autre produit.
    """)

    # 5. GTINs Génériques
    st.markdown('<div class="section-header" id="generiques">5. GTINs Génériques</div>', unsafe_allow_html=True)
    st.markdown("""
    **Définition** : GTINs génériques utilisés pour représenter des catégories de produits plutôt que des produits spécifiques.
    
    **Liste des Generic GTINs :**
    - `10000000000009` → Butchery (BEEF, PORK, POULTRY)
    - `20000000000009` → Not in MDD
    - `30000000000009` → Equipment (SUPPLIES & EQUIPMENT)
    - `40000000000009` → Fishmongery (SEAFOOD)
    - `50000000000009` → Not in MDD
    - `60000000000009` → Not in MDD
    - `70000000000009` → Produce (PRODUCE)
    - `80000000000009` → Not in MDD
    
    **Analyse** :
    - Compte les occurrences de chaque Generic GTIN
    - Analyse par Legal Entity
    - Identifie les doublons de Generic GTINs
    """)

    # 6. GTINs Placeholder
    st.markdown('<div class="section-header" id="placeholder">6. GTINs Placeholder</div>', unsafe_allow_html=True)
    st.markdown("""
    **Définition** : GTINs explicitement bloqués, composés uniquement de 9.
    
    **Critères** : Tous les chiffres sont des 9 (ex: `99999999999999`, `999`, `99`)
    
    **Exemples** :
    - `99999999999999` → Placeholder 14 digits
    - `9999999999999` → Placeholder 13 digits
    - `99999999` → Placeholder 8 digits
    
    **Utilisation** : Identifier les produits sans GTIN réel assigné.
    """)

    # 7. GTINs Suspects
    st.markdown('<div class="section-header" id="suspects">7. GTINs Suspects</div>', unsafe_allow_html=True)
    st.markdown("""
    **Définition** : GTINs avec un format valide mais présentant des motifs suspects.
    
    **Critères de détection :**
    
    1. **Répétition excessive** : Un même chiffre apparaît ≥ 60% de la longueur
       - Exemple : `11111111111111` (14 fois le chiffre 1)
       - Exemple : `18414900000000` (beaucoup de 0)
    
    2. **Trop de zéros à la fin** : 
       - Au moins 6 zéros consécutifs à la fin, OU
       - La moitié de la longueur en zéros à la fin
       - Exemple : `18414900000000` (8 zéros à la fin sur 14 digits)
    
    **Exclusion** : Les Generic GTINs sont exclus de l'analyse des suspects.
    
    **Utilisation** : Identifier les GTINs qui semblent être des placeholders ou des erreurs de saisie.
    """)

    # 8. GTINs Valides
    st.markdown('<div class="section-header" id="valides">8. GTINs Valides</div>', unsafe_allow_html=True)
    st.markdown("""
    **Définition** : GTINs qui passent toutes les validations.
    
    **Critères de validité :**
    1. Format numérique valide
    2. Longueur correcte (8, 13 ou 14 digits)
    3. Check digit GS1 valide (pour 13 et 14 digits)
    4. Pas un Generic GTIN
    5. Pas un Placeholder (999...99)
    
    **Analyse par entité** :
    - Identifie les GTINs valides partagés entre plusieurs Legal Entities
    - Distingue le partage valide (même GTIN, différentes entités) des doublons problématiques
    """)

    # 9. Generic GTIN vs Taxonomy
    st.markdown('<div class="section-header" id="generic-taxonomy">9. Analyse Generic GTIN vs Taxonomy</div>', unsafe_allow_html=True)
    st.markdown("""
    **Page : Generic GTIN Analysis**
    
    **Objectif** : Vérifier que les Generic GTINs correspondent à la taxonomie OSD correcte.
    
    **Processus :**
    
    1. **Filtrage initial** : Sélectionne uniquement les produits avec Generic GTINs :
       - `10000000000009` (Butchery)
       - `30000000000009` (Equipment)
       - `40000000000009` (Fishmongery)
       - `70000000000009` (Produce)
    
    2. **Extraction de la taxonomie** : Prend la première partie de "OSD Classification" (avant le premier tiret)
       - Exemple : `"BEEF-YYYY-ZZZZ"` → `"BEEF"`
    
    3. **Mapping attendu** :
       - `BEEF, PORK, POULTRY` → Expected GTIN: `10000000000009`
       - `SUPPLIES & EQUIPMENT` → Expected GTIN: `30000000000009`
       - `SEAFOOD` → Expected GTIN: `40000000000009`
       - `PRODUCE` → Expected GTIN: `70000000000009`
    
    4. **Comparaison** :
       - **Conforme** : Le Generic GTIN du produit = GTIN attendu pour sa taxonomie
       - **Non-conforme** : Le Generic GTIN ≠ GTIN attendu, OU taxonomie non dans le mapping
    
    **Résultats** :
    - Métriques globales (total, conformes, non-conformes)
    - Liste des records non-conformes avec détails (SUPC, Description, OSD Taxonomy, OSD Expected, GTIN Outer, Legal Entity)
    - Statistiques par Legal Entity
    """)

    # Normalisation GTIN-Outer
    st.markdown('<div class="section-header">🔧 Normalisation GTIN-Outer</div>', unsafe_allow_html=True)
    st.markdown("""
    **Logique de priorité pour GTIN-Outer normalisé :**
    
    1. Si **GTIN-Outer ET Generic GTIN** sont remplis → Utilise **GTIN-Outer** (priorité)
    2. Si seulement **GTIN-Outer** est rempli → Utilise **GTIN-Outer**
    3. Si seulement **Generic GTIN** est rempli → Utilise **Generic GTIN**
    4. Si aucun n'est rempli → `None`
    
    **Colonne `gtin_source`** : Indique quelle colonne a été utilisée pour `gtin_outer_normalized`
    - `"GTIN Outer"` : Seulement GTIN-Outer rempli
    - `"Generic GTIN"` : Seulement Generic GTIN rempli
    - `"GTIN Outer (both filled)"` : Les deux remplis, GTIN-Outer utilisé
    - `"None"` : Aucun rempli
    """)

    # Conversion GTIN-13 vers GTIN-14
    st.markdown('<div class="section-header">🔄 Conversion GTIN-13 → GTIN-14</div>', unsafe_allow_html=True)
    st.markdown("""
    **Fonction `gtin_to_14()`** : Convertit un GTIN-13 en GTIN-14 en ajoutant un zéro au début.
    
    **Règle** :
    - Si longueur = 13 → Ajoute `"0"` au début
    - Si longueur = 14 → Retourne tel quel
    - Sinon → Retourne tel quel (pas de conversion)
    
    **Exemple** :
    - `"1234567890123"` (13 digits) → `"01234567890123"` (14 digits)
    - `"12345678901234"` (14 digits) → `"12345678901234"` (inchangé)
    """)

    # Check Digit GS1
    st.markdown('<div class="section-header">✅ Validation Check Digit GS1</div>', unsafe_allow_html=True)
    st.markdown("""
    **Algorithme de validation** :
    
    1. Prend les digits du corps (tous sauf le dernier)
    2. Multiplie alternativement par 1 et 3 en partant de la droite
    3. Somme tous les résultats
    4. Calcule : `(10 - (somme % 10)) % 10`
    5. Compare avec le dernier digit (check digit)
    
    **Règles selon la longueur :**
    - **GTIN-13** : Multiplie par 1 les positions impaires (en partant de la droite)
    - **GTIN-14** : Multiplie par 1 les positions paires (en partant de la droite)
    
    **Résultat** :
    - Si check digit correct → GTIN valide
    - Si check digit incorrect → Marqué comme **SUSPECT**
    """)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #64748b; margin-top: 2rem;">
    📊 GTIN Analysis Dashboard - Documentation complète<br>
    Pour toute question, consulter le code source dans <code>duplicate_analysis_backend.py</code>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()

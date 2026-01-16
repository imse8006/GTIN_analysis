import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path
from datetime import date
import io
from collections import Counter

# Import shared functions and constants
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

# Import GTIN classification functions
try:
    from gtin_analysis import (
        GENERIC_GTINS, 
        EXPLICIT_BLOCKED, 
        VALID_LENGTHS,
        has_valid_gs1_check_digit,
        classify_gtin_status
    )
except ImportError:
    # Fallback definitions if import fails
    GENERIC_GTINS = {
        "10000000000009", "20000000000009", "30000000000009", "40000000000009",
        "50000000000009", "60000000000009", "70000000000009", "80000000000009",
    }
    EXPLICIT_BLOCKED = "99999999999999"
    VALID_LENGTHS = {8, 13, 14}
    
    def has_valid_gs1_check_digit(gtin, length):
        if length == 8:
            return True
        if length not in (13, 14) or not gtin.isdigit():
            return False
        digits = [int(d) for d in gtin]
        body, check_digit = digits[:-1], digits[-1]
        total = 0
        for i, d in enumerate(reversed(body), start=1):
            if length == 13:
                multiplier = 1 if i % 2 == 1 else 3
            else:
                multiplier = 3 if i % 2 == 1 else 1
            total += d * multiplier
        calc = (10 - (total % 10)) % 10
        return calc == check_digit
    
    def classify_gtin_status(gtin_raw):
        if pd.isna(gtin_raw) or gtin_raw is None:
            return "MISSING"
        gtin = normalize_gtin(gtin_raw)
        if gtin is None:
            return "MISSING"
        if gtin == EXPLICIT_BLOCKED:
            return "EXPLICIT_BLOCKED"
        if gtin in GENERIC_GTINS:
            return "GENERIC_GTIN"
        if not gtin.isdigit():
            return "NON_NUMERIC"
        length = len(gtin)
        if length not in VALID_LENGTHS:
            return "INVALID_LENGTH"
        if not has_valid_gs1_check_digit(gtin, length):
            return "SUSPECT"
        if length == 8:
            return "GTIN_8"
        elif length == 13:
            return "GTIN_13"
        else:
            return "GTIN_14"

# Page configuration
st.set_page_config(
    page_title="GTIN Duplicate Analysis - MDM",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"  # Expanded to show navigation
)

# Use same CSS as main dashboard
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: 700;
        color: #94a3b8;
        text-align: center;
        margin-bottom: 1rem;
        padding: 1rem 0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #94a3b8;
        margin-top: 2rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #475569;
    }
    .stMetric {
        background-color: #1e293b;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        border: 1px solid #334155;
    }
    .filter-section {
        background-color: #1e293b;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 2rem;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    /* Align Reset buttons with multiselect field */
    div[data-testid="column"]:has(button:contains("Reset")) {
        padding-top: 1.5rem !important;
    }
    /* Increase multiselect height to align with Reset buttons */
    div[data-testid="stMultiSelect"] {
        min-height: 5.5rem !important;
    }
    div[data-testid="stMultiSelect"] > div {
        min-height: 5.5rem !important;
    }
    div[data-testid="stMultiSelect"] > div > div {
        min-height: 5.5rem !important;
    }
    /* Hide empty filter-section divs and empty containers */
    div.filter-section:empty,
    div[class*="filter-section"]:empty,
    div[data-testid="stElementContainer"]:has(div.filter-section:empty),
    div[data-testid="stElementContainer"]:has(div[class*="filter-section"]:empty) {
        display: none !important;
        height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    /* Custom Save button styling - softer blue */
    button[kind="primary"][data-testid="baseButton-save_duplicate_analysis_top"] {
        background-color: #3b82f6 !important;
        border-color: #3b82f6 !important;
        color: white !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    button[kind="primary"][data-testid="baseButton-save_duplicate_analysis_top"]:hover {
        background-color: #2563eb !important;
        border-color: #2563eb !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
    }
    </style>
""", unsafe_allow_html=True)

INPUT_FILE = "all-products-prod-2026-01-13_15.30.30.xlsx"


def normalize_gtin(value):
    """Normalize GTIN value from Excel."""
    if pd.isna(value) or value is None:
        return None
    s = str(value).strip()
    if s == "" or s.lower() == "nan":
        return None
    if "E" in s.upper():
        try:
            s = str(int(float(s)))
        except (ValueError, OverflowError):
            return s
    if "." in s and s.endswith(".0") and s[:-2].replace(".", "").isdigit():
        s = s[:-2]
    return s


@st.cache_data
def load_duplicate_data():
    """Load data and find GTIN Outer, Inner, and Generic GTIN columns."""
    df = pd.read_excel(INPUT_FILE, dtype=str)
    
    # Find GTIN-Outer column
    gtin_outer_col = None
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if "gtin" in col_lower and "outer" in col_lower:
            gtin_outer_col = col
            break
    
    if gtin_outer_col is None:
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if col_lower in ["gtin-outer", "gtin_outer", "gtinouter"]:
                gtin_outer_col = col
                break
    
    # Find Generic GTIN column
    generic_gtin_col = None
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if "generic" in col_lower and "gtin" in col_lower:
            generic_gtin_col = col
            break
    
    # Find GTIN-Inner column
    gtin_inner_col = None
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if "gtin" in col_lower and "inner" in col_lower:
            gtin_inner_col = col
            break
    
    if gtin_inner_col is None:
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if col_lower in ["gtin-inner", "gtin_inner", "gtininner"]:
                gtin_inner_col = col
                break
    
    if gtin_outer_col is None:
        st.error("GTIN-Outer column not found!")
        return None, None, None, None
    
    if gtin_inner_col is None:
        st.warning("GTIN-Inner column not found! Only Outer duplicates will be analyzed.")
    
    # Normalize GTINs with priority logic:
    # 1. If only GTIN-Outer is filled → use GTIN-Outer
    # 2. If only Generic GTIN is filled → use Generic GTIN
    # 3. If both are filled → use GTIN-Outer (priority to GTIN-Outer when both exist)
    def get_gtin_outer_normalized(row):
        has_outer = gtin_outer_col and pd.notna(row.get(gtin_outer_col)) and str(row.get(gtin_outer_col)).strip() not in ["", "nan"]
        has_generic = generic_gtin_col and pd.notna(row.get(generic_gtin_col)) and str(row.get(generic_gtin_col)).strip() not in ["", "nan"]
        
        if has_outer and has_generic:
            # Both filled → use GTIN-Outer (priority)
            return normalize_gtin(row[gtin_outer_col])
        elif has_outer:
            # Only GTIN-Outer filled → use GTIN-Outer
            return normalize_gtin(row[gtin_outer_col])
        elif has_generic:
            # Only Generic GTIN filled → use Generic GTIN
            return normalize_gtin(row[generic_gtin_col])
        else:
            # Neither filled
            return None
    
    df["gtin_outer_normalized"] = df.apply(get_gtin_outer_normalized, axis=1)
    
    # Store which column was used for reference
    def get_gtin_source(row):
        has_outer = gtin_outer_col and pd.notna(row.get(gtin_outer_col)) and str(row.get(gtin_outer_col)).strip() not in ["", "nan"]
        has_generic = generic_gtin_col and pd.notna(row.get(generic_gtin_col)) and str(row.get(generic_gtin_col)).strip() not in ["", "nan"]
        
        if has_outer and has_generic:
            return "GTIN Outer (both filled)"
        elif has_outer:
            return "GTIN Outer"
        elif has_generic:
            return "Generic GTIN"
        else:
            return "None"
    
    df["gtin_source"] = df.apply(get_gtin_source, axis=1)
    
    if gtin_inner_col:
        df["gtin_inner_normalized"] = df[gtin_inner_col].apply(normalize_gtin)
    else:
        df["gtin_inner_normalized"] = None
    
    return df, gtin_outer_col, gtin_inner_col, generic_gtin_col


def is_suspect_gtin(gtin):
    """Detect suspect GTINs where a digit repeats many times (e.g., 18414900000000)."""
    if pd.isna(gtin) or gtin is None:
        return False
    gtin_str = normalize_gtin(gtin)
    if not gtin_str or not gtin_str.isdigit():
        return False
    
    # Check if any digit appears more than 60% of the length
    digit_counts = Counter(gtin_str)
    max_count = max(digit_counts.values())
    threshold = len(gtin_str) * 0.6
    
    # Also check for patterns like many zeros at the end
    if gtin_str.endswith("0" * max(6, len(gtin_str) // 2)):
        return True
    
    return max_count >= threshold


def analyze_duplicates(df, gtin_outer_col, gtin_inner_col):
    """Analyze duplicates in GTIN Outer and Inner."""
    results = {}
    
    # 1. Duplicates in GTIN Outer
    outer_duplicates = df[df.duplicated(subset=["gtin_outer_normalized"], keep=False)].copy()
    outer_duplicate_count = len(outer_duplicates)
    outer_unique_duplicated = outer_duplicates["gtin_outer_normalized"].nunique() if outer_duplicate_count > 0 else 0
    
    results["outer"] = {
        "total_duplicates": outer_duplicate_count,
        "unique_duplicated_gtins": outer_unique_duplicated,
        "duplicate_df": outer_duplicates
    }
    
    # 2. Duplicates in GTIN Inner (if column exists)
    if gtin_inner_col:
        inner_duplicates = df[df.duplicated(subset=["gtin_inner_normalized"], keep=False)].copy()
        inner_duplicate_count = len(inner_duplicates)
        inner_unique_duplicated = inner_duplicates["gtin_inner_normalized"].nunique() if inner_duplicate_count > 0 else 0
        
        results["inner"] = {
            "total_duplicates": inner_duplicate_count,
            "unique_duplicated_gtins": inner_unique_duplicated,
            "duplicate_df": inner_duplicates
        }
    else:
        results["inner"] = None
    
    # 3. Cross duplicates: GTIN Outer appears in GTIN Inner
    if gtin_inner_col:
        outer_values = set(df["gtin_outer_normalized"].dropna().unique())
        inner_values = set(df["gtin_inner_normalized"].dropna().unique())
        cross_duplicates = outer_values.intersection(inner_values)
        
        if len(cross_duplicates) > 0:
            cross_df = df[df["gtin_outer_normalized"].isin(cross_duplicates) | 
                         df["gtin_inner_normalized"].isin(cross_duplicates)].copy()
        else:
            cross_df = pd.DataFrame()
        
        results["cross"] = {
            "unique_cross_gtins": len(cross_duplicates),
            "total_records": len(cross_df),
            "cross_df": cross_df,
            "gtin_list": list(cross_duplicates)
        }
    else:
        results["cross"] = None
    
    return results


def analyze_generic_gtins(df, gtin_outer_col, generic_gtin_col=None):
    """Analyze Generic GTINs duplicates and their distribution by Legal Entity."""
    # Classify GTINs based on normalized GTIN
    df["gtin_status"] = df["gtin_outer_normalized"].apply(
        lambda x: classify_gtin_status(x) if x is not None else "MISSING"
    )
    
    # Filter Generic GTINs (either from classification or from Generic GTIN column)
    if generic_gtin_col and generic_gtin_col in df.columns:
        # If Generic GTIN column exists, use it directly
        generic_df = df[df[generic_gtin_col].notna() & (df[generic_gtin_col].astype(str).str.strip() != "")].copy()
        if len(generic_df) == 0:
            # Fallback to classification
            generic_df = df[df["gtin_status"] == "GENERIC_GTIN"].copy()
    else:
        # Use classification
        generic_df = df[df["gtin_status"] == "GENERIC_GTIN"].copy()
    
    if len(generic_df) == 0:
        return {
            "total": 0,
            "unique_gtins": 0,
            "duplicate_count": 0,
            "unique_duplicated_gtins": 0,
            "by_entity": pd.DataFrame(),
            "duplicate_summary": pd.DataFrame(),
            "gtin_list": [],
            "full_df": pd.DataFrame()
        }
    
    # Find duplicates: Generic GTINs that appear more than once
    generic_duplicates = generic_df[generic_df.duplicated(subset=["gtin_outer_normalized"], keep=False)].copy()
    duplicate_count = len(generic_duplicates)
    unique_duplicated_gtins = generic_duplicates["gtin_outer_normalized"].nunique() if duplicate_count > 0 else 0
    
    # Analysis by Legal Entity (for all Generic GTINs, not just duplicates)
    by_entity = generic_df.groupby("Legal Entity").agg({
        "gtin_outer_normalized": ["count", "nunique"]
    }).reset_index()
    by_entity.columns = ["Legal Entity", "Total Records", "Unique Generic GTINs"]
    by_entity = by_entity.sort_values("Total Records", ascending=False)
    
    # Duplicate summary: which Generic GTINs are duplicated and by which entities
    duplicate_summary = []
    if duplicate_count > 0:
        for gtin in generic_duplicates["gtin_outer_normalized"].unique():
            gtin_records = generic_duplicates[generic_duplicates["gtin_outer_normalized"] == gtin]
            entities = sorted(gtin_records["Legal Entity"].unique().tolist())
            duplicate_summary.append({
                "Generic GTIN": gtin,
                "Occurrences": len(gtin_records),
                "Legal Entities": ", ".join(entities),
                "Entity Count": len(entities)
            })
        duplicate_summary_df = pd.DataFrame(duplicate_summary).sort_values("Occurrences", ascending=False)
    else:
        duplicate_summary_df = pd.DataFrame()
    
    unique_generics = generic_df["gtin_outer_normalized"].dropna().unique().tolist()
    
    return {
        "total": len(generic_df),
        "unique_gtins": len(unique_generics),
        "duplicate_count": duplicate_count,
        "unique_duplicated_gtins": unique_duplicated_gtins,
        "by_entity": by_entity,
        "duplicate_summary": duplicate_summary_df,
        "gtin_list": unique_generics,
        "full_df": generic_df
    }


def analyze_placeholder_gtins(df, gtin_outer_col):
    """Analyze Placeholder GTINs (9999...999) and their distribution by Legal Entity."""
    # Classify GTINs
    df["gtin_status"] = df["gtin_outer_normalized"].apply(
        lambda x: classify_gtin_status(x) if x is not None else "MISSING"
    )
    
    # Filter Placeholder GTINs (EXPLICIT_BLOCKED = 99999999999999)
    placeholder_df = df[df["gtin_status"] == "EXPLICIT_BLOCKED"].copy()
    
    if len(placeholder_df) == 0:
        return {
            "total": 0,
            "unique_gtins": 0,
            "by_entity": pd.DataFrame(),
            "gtin_list": [],
            "full_df": pd.DataFrame()
        }
    
    # Analysis by Legal Entity
    by_entity = placeholder_df.groupby("Legal Entity").agg({
        "gtin_outer_normalized": ["count", "nunique"]
    }).reset_index()
    by_entity.columns = ["Legal Entity", "Total Records", "Unique Placeholder GTINs"]
    by_entity = by_entity.sort_values("Total Records", ascending=False)
    
    unique_placeholders = placeholder_df["gtin_outer_normalized"].dropna().unique().tolist()
    
    return {
        "total": len(placeholder_df),
        "unique_gtins": len(unique_placeholders),
        "by_entity": by_entity,
        "gtin_list": unique_placeholders,
        "full_df": placeholder_df
    }


def analyze_suspect_gtins(df, gtin_outer_col):
    """Analyze Suspect GTINs (e.g., 18414900000000) and their distribution, excluding Generic GTINs."""
    # Detect suspect GTINs
    df["is_suspect"] = df[gtin_outer_col].apply(is_suspect_gtin)
    
    # Exclude Generic GTINs
    df["gtin_status"] = df["gtin_outer_normalized"].apply(
        lambda x: classify_gtin_status(x) if x is not None else "MISSING"
    )
    
    # Filter: suspect AND not generic
    suspect_df = df[(df["is_suspect"] == True) & (df["gtin_status"] != "GENERIC_GTIN")].copy()
    
    if len(suspect_df) == 0:
        return {
            "total": 0,
            "unique_gtins": 0,
            "by_entity": pd.DataFrame(),
            "gtin_list": [],
            "full_df": pd.DataFrame()
        }
    
    # Analysis by Legal Entity
    by_entity = suspect_df.groupby("Legal Entity").agg({
        gtin_outer_col: "count",
        "gtin_outer_normalized": "nunique"
    }).reset_index()
    by_entity.columns = ["Legal Entity", "Total Records", "Unique Suspect GTINs"]
    by_entity = by_entity.sort_values("Total Records", ascending=False)
    
    unique_suspects = suspect_df["gtin_outer_normalized"].unique().tolist()
    
    return {
        "total": len(suspect_df),
        "unique_gtins": len(unique_suspects),
        "by_entity": by_entity,
        "gtin_list": unique_suspects,
        "full_df": suspect_df
    }


def analyze_valid_gtins_by_entity(df, gtin_outer_col):
    """Analyze valid GTINs and understand which Legal Entities share them."""
    # Classify GTINs
    df["gtin_status"] = df[gtin_outer_col].apply(classify_gtin_status)
    
    # Filter valid GTINs (8, 13, 14 digits with valid check digit)
    valid_statuses = ["GTIN_8", "GTIN_13", "GTIN_14"]
    valid_df = df[df["gtin_status"].isin(valid_statuses)].copy()
    
    if len(valid_df) == 0:
        return {
            "total": 0,
            "unique_gtins": 0,
            "shared_gtins": pd.DataFrame(),
            "entity_sharing": pd.DataFrame()
        }
    
    # Find GTINs shared across multiple Legal Entities
    gtin_entity_counts = valid_df.groupby("gtin_outer_normalized")["Legal Entity"].nunique().reset_index()
    gtin_entity_counts.columns = ["GTIN", "Entity Count"]
    shared_gtins = gtin_entity_counts[gtin_entity_counts["Entity Count"] > 1].sort_values("Entity Count", ascending=False)
    
    # For each shared GTIN, list which entities share it
    sharing_details = []
    for gtin in shared_gtins["GTIN"].head(100):  # Limit to top 100 for performance
        entities = valid_df[valid_df["gtin_outer_normalized"] == gtin]["Legal Entity"].unique().tolist()
        sharing_details.append({
            "GTIN": gtin,
            "Entity Count": len(entities),
            "Legal Entities": ", ".join(sorted(entities))
        })
    
    sharing_df = pd.DataFrame(sharing_details) if sharing_details else pd.DataFrame()
    
    # Entity-to-Entity sharing matrix (simplified - count of shared GTINs)
    entity_list = sorted(valid_df["Legal Entity"].unique())
    entity_sharing = []
    for i, entity1 in enumerate(entity_list):
        for entity2 in entity_list[i+1:]:
            gtins1 = set(valid_df[valid_df["Legal Entity"] == entity1]["gtin_outer_normalized"].unique())
            gtins2 = set(valid_df[valid_df["Legal Entity"] == entity2]["gtin_outer_normalized"].unique())
            shared_count = len(gtins1.intersection(gtins2))
            if shared_count > 0:
                entity_sharing.append({
                    "Entity 1": entity1,
                    "Entity 2": entity2,
                    "Shared GTINs": shared_count
                })
    
    entity_sharing_df = pd.DataFrame(entity_sharing).sort_values("Shared GTINs", ascending=False) if entity_sharing else pd.DataFrame()
    
    return {
        "total": len(valid_df),
        "unique_gtins": valid_df["gtin_outer_normalized"].nunique(),
        "shared_gtins": shared_gtins,
        "sharing_details": sharing_df,
        "entity_sharing": entity_sharing_df,
        "full_df": valid_df
    }


def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        # Get password from secrets (Streamlit Cloud) or use default for local
        try:
            correct_password = st.secrets["PASSWORD"]
        except (KeyError, FileNotFoundError):
            correct_password = "OSDTeam123"
        
        if st.session_state["password"] == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    
    if "password_correct" not in st.session_state:
        st.markdown('<div style="text-align: center; padding: 2rem;">', unsafe_allow_html=True)
        st.markdown('<div style="color: #94a3b8; font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem;">GTIN Duplicate Analysis</div>', unsafe_allow_html=True)
        password = st.text_input("Password", type="password", on_change=password_entered, key="password", label_visibility="visible")
        if "password" in st.session_state and st.session_state.get("password_correct", None) == False:
            st.error("Incorrect password")
        st.markdown('</div>', unsafe_allow_html=True)
        if st.session_state.get("password_correct", False):
            st.rerun()
        return False
    
    if st.session_state.get("password_correct", False):
        return True
    return False


def main():
    # Password protection
    if not check_password():
        st.stop()
    
    # Header
    st.markdown('<h1 class="main-header">🔍 GTIN Duplicate Analysis</h1>', unsafe_allow_html=True)
    st.markdown(f'<div style="text-align: center; color: #cbd5e1; margin-bottom: 0.5rem;">📁 Source file: <strong style="color: #94a3b8;">{INPUT_FILE}</strong></div>', unsafe_allow_html=True)
    
    # Save Analysis button - positioned right after source file with improved design
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])
    with col_btn2:
        save_button_clicked = st.button(
            "💾 Save Analysis and Report to Tracker",
            use_container_width=True,
            type="primary",
            key="save_duplicate_analysis_top"
        )
        if save_button_clicked:
            st.session_state["save_duplicate_requested"] = True
    
    # Load data
    with st.spinner("Loading data and analyzing duplicates..."):
        result = load_duplicate_data()
        if result[0] is None:
            return
        df, gtin_outer_col, gtin_inner_col, generic_gtin_col = result
    
    total_rows = len(df)
    
    # Filter section by Legal Entity
    st.markdown('<div class="filter-section">', unsafe_allow_html=True)
    st.markdown("### 🔍 Filters")
    
    legal_entities = sorted(df["Legal Entity"].unique())
    
    # Initialize session state for selected entities
    if "selected_entities_duplicate" not in st.session_state:
        st.session_state.selected_entities_duplicate = legal_entities
    
    col1, col2 = st.columns([4, 1])
    with col1:
        selected_entities = st.multiselect(
            "**Select Legal Entities**",
            legal_entities,
            default=st.session_state.selected_entities_duplicate,
            help="Select one or more Legal Entities to analyze"
        )
        st.session_state.selected_entities_duplicate = selected_entities
    
    with col2:
        # Stack buttons vertically, aligned with multiselect
        st.markdown('<div style="padding-top: 1.5rem;">', unsafe_allow_html=True)
        if st.button("🔄 Reset to All", use_container_width=True, key="reset_all_duplicate"):
            st.session_state.selected_entities_duplicate = legal_entities
            st.rerun()
        if st.button("Reset", use_container_width=True, key="reset_duplicate"):
            st.session_state.selected_entities_duplicate = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Filter data by selected entities
    if not selected_entities:
        st.warning("⚠️ Please select at least one Legal Entity")
        return
    
    df_filtered = df[df["Legal Entity"].isin(selected_entities)].copy()
    
    if len(df_filtered) == 0:
        st.warning("⚠️ No data found for selected Legal Entities")
        return
    
    # Analyze duplicates on filtered data
    with st.spinner("Analyzing duplicates..."):
        duplicate_results = analyze_duplicates(df_filtered, gtin_outer_col, gtin_inner_col)
    
    # Analyze Generic, Suspect, Placeholder, and Valid GTINs on filtered data
    with st.spinner("Analyzing Generic GTINs..."):
        generic_results = analyze_generic_gtins(df_filtered, gtin_outer_col, generic_gtin_col)
    
    with st.spinner("Analyzing Placeholder GTINs..."):
        placeholder_results = analyze_placeholder_gtins(df_filtered, gtin_outer_col)
    
    with st.spinner("Analyzing Suspect GTINs..."):
        suspect_results = analyze_suspect_gtins(df_filtered, gtin_outer_col)
    
    with st.spinner("Analyzing Valid GTINs by Legal Entity..."):
        valid_results = analyze_valid_gtins_by_entity(df_filtered, gtin_outer_col)
    
    # Overview Metrics
    st.markdown('<div class="section-header">📊 Overview</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
    with col1:
        st.metric("📦 Total Products", f"{len(df_filtered):,}", 
                 f"Filtered from {total_rows:,} total")
    
    with col2:
        outer_dup = duplicate_results["outer"]["total_duplicates"]
        st.metric("🔄 Outer Duplicates", f"{outer_dup:,}", 
                 f"{outer_dup/len(df_filtered)*100:.1f}%" if len(df_filtered) > 0 else "0%")
    
    with col3:
        if duplicate_results["cross"]:
            cross_dup = duplicate_results["cross"]["unique_cross_gtins"]
            st.metric("🔀 Cross Duplicates", f"{cross_dup:,}",
                     f"{duplicate_results['cross']['total_records']:,} records")
        else:
            st.metric("🔀 Cross Duplicates", "N/A", "Inner column not found")
    
    with col4:
        duplicate_count = generic_results.get('duplicate_count', 0)
        unique_duplicated = generic_results.get('unique_duplicated_gtins', 0)
        st.metric("⚠️ Generic GTINs", f"{duplicate_count:,}", 
                 f"{unique_duplicated:,} duplicated" if duplicate_count > 0 else f"{generic_results.get('unique_gtins', 0):,} unique")
    
    with col5:
        st.metric("🚫 Placeholder GTINs", f"{placeholder_results['total']:,}",
                 f"{placeholder_results['unique_gtins']:,} unique")
    
    with col6:
        st.metric("🔍 Suspect GTINs", f"{suspect_results['total']:,}",
                 f"{suspect_results['unique_gtins']:,} unique")
    
    with col7:
        st.metric("✅ Valid GTINs", f"{valid_results['total']:,}",
                 f"{valid_results['unique_gtins']:,} unique")
    
    # Handle save button click (button is at the top, but logic is here after data is loaded)
    if st.session_state.get("save_duplicate_requested", False):
        st.session_state["save_duplicate_requested"] = False  # Reset flag
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).parent.parent))
        from tracker_utils import save_tracker_data
        
        # Prepare duplicate metrics
        tracker_entry = {
            "analysis_type": "duplicate",
            "legal_entities": selected_entities,
            "total_products": len(df_filtered),
            "outer_duplicates": duplicate_results["outer"]["total_duplicates"],
            "outer_unique_duplicated": duplicate_results["outer"]["unique_duplicated_gtins"],
            "inner_duplicates": duplicate_results["inner"]["total_duplicates"] if duplicate_results["inner"] else 0,
            "inner_unique_duplicated": duplicate_results["inner"]["unique_duplicated_gtins"] if duplicate_results["inner"] else 0,
            "cross_duplicates": duplicate_results["cross"]["unique_cross_gtins"] if duplicate_results["cross"] else 0,
            "cross_total_records": duplicate_results["cross"]["total_records"] if duplicate_results["cross"] else 0,
            "has_inner_column": gtin_inner_col is not None,
            "generic_gtins": generic_results["total"],
            "placeholder_gtins": placeholder_results["total"],
            "suspect_gtins": suspect_results["total"],
            "valid_gtins": valid_results["total"]
        }
        
        if save_tracker_data(tracker_entry):
            st.success("✅ Analysis saved to tracker successfully!")
        else:
            st.error("❌ Error saving analysis to tracker")
    
    # Detailed Analysis
    st.markdown('<div class="section-header">📋 Detailed Analysis</div>', unsafe_allow_html=True)
    
    # Tabs for different analysis types
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🔄 Cross Duplicates", 
        "📦 GTIN Outer Duplicates", 
        "📦 GTIN Inner Duplicates",
        "⚠️ Generic GTINs",
        "🚫 Placeholder GTINs",
        "🔍 Suspect GTINs",
        "✅ Valid GTINs by Entity"
    ])
    
    # Tab 1: Cross Duplicates (moved to first position as it's most interesting)
    with tab1:
        st.markdown("#### 🔀 Cross Duplicates (GTIN appears in both Outer and Inner)")
        
        if duplicate_results["cross"]:
            cross_df = duplicate_results["cross"]["cross_df"]
            
            if len(cross_df) > 0:
                st.markdown(f"**Found {duplicate_results['cross']['unique_cross_gtins']} GTINs that appear in both Outer and Inner columns**")
                
                # Analysis by Legal Entity
                st.markdown("##### 📊 By Legal Entity")
                cross_by_entity = cross_df.groupby("Legal Entity").agg({
                    gtin_outer_col: "count" if gtin_outer_col else "size",
                    "gtin_outer_normalized": "nunique"
                }).reset_index()
                cross_by_entity.columns = ["Legal Entity", "Total Records", "Unique Cross GTINs"]
                cross_by_entity = cross_by_entity.sort_values("Total Records", ascending=False)
                st.dataframe(cross_by_entity, use_container_width=True, hide_index=True)
                
                # Summary by GTIN
                st.markdown("##### 📋 GTIN Summary")
                cross_summary = []
                for gtin in duplicate_results["cross"]["gtin_list"][:100]:  # Limit to first 100
                    gtin_df = cross_df[(cross_df["gtin_outer_normalized"] == gtin) | 
                                      (cross_df["gtin_inner_normalized"] == gtin)]
                    outer_count = len(gtin_df[gtin_df["gtin_outer_normalized"] == gtin])
                    inner_count = len(gtin_df[gtin_df["gtin_inner_normalized"] == gtin])
                    entities = gtin_df["Legal Entity"].unique().tolist()
                    cross_summary.append({
                        "GTIN": gtin,
                        "As Outer": outer_count,
                        "As Inner": inner_count,
                        "Total Records": outer_count + inner_count,
                        "Legal Entities": ", ".join(sorted(entities))
                    })
                
                if cross_summary:
                    cross_summary_df = pd.DataFrame(cross_summary)
                    st.dataframe(cross_summary_df, use_container_width=True, hide_index=True)
                
                # Detailed view
                with st.expander("View All Cross Duplicate Records"):
                    display_cols = ["Legal Entity"]
                    if gtin_outer_col:
                        display_cols.append(gtin_outer_col)
                    if gtin_inner_col:
                        display_cols.append(gtin_inner_col)
                    if "SUPC" in cross_df.columns:
                        display_cols.append("SUPC")
                    
                    available_cols = [col for col in display_cols if col in cross_df.columns]
                    st.dataframe(cross_df[available_cols], use_container_width=True, hide_index=True)
            else:
                st.success("✅ No cross duplicates found!")
        else:
            st.info("ℹ️ GTIN Inner column not found. Cross duplicate analysis requires both Outer and Inner columns.")
    
    # Tab 2: GTIN Outer Duplicates
    with tab2:
        st.markdown("#### 📦 GTIN Outer Duplicates")
        outer_df = duplicate_results["outer"]["duplicate_df"]
        
        if len(outer_df) > 0:
            # Analysis by Legal Entity
            st.markdown("##### 📊 By Legal Entity")
            outer_by_entity = outer_df.groupby("Legal Entity").agg({
                gtin_outer_col: "count",
                "gtin_outer_normalized": "nunique"
            }).reset_index()
            outer_by_entity.columns = ["Legal Entity", "Total Duplicates", "Unique Duplicated GTINs"]
            outer_by_entity = outer_by_entity.sort_values("Total Duplicates", ascending=False)
            st.dataframe(outer_by_entity, use_container_width=True, hide_index=True)
            
            # Summary by GTIN
            st.markdown("##### 📋 GTIN Summary")
            outer_summary = outer_df.groupby("gtin_outer_normalized").agg({
                "Legal Entity": lambda x: ", ".join(sorted(x.unique()))
            }).reset_index()
            outer_summary["Duplicate Count"] = outer_df.groupby("gtin_outer_normalized").size().values
            outer_summary.columns = ["GTIN Outer", "Legal Entities", "Duplicate Count"]
            outer_summary = outer_summary.sort_values("Duplicate Count", ascending=False)
            
            st.markdown(f"**Found {duplicate_results['outer']['unique_duplicated_gtins']} unique GTINs with duplicates**")
            st.dataframe(outer_summary, use_container_width=True, hide_index=True)
            
            # Detailed view
            with st.expander("View All Duplicate Records"):
                display_cols = ["Legal Entity", gtin_outer_col, "gtin_outer_normalized"]
                if "SUPC" in outer_df.columns:
                    display_cols.append("SUPC")
                if "Local Product Description" in outer_df.columns:
                    display_cols.append("Local Product Description")
                
                available_cols = [col for col in display_cols if col in outer_df.columns]
                st.dataframe(outer_df[available_cols], use_container_width=True, hide_index=True)
        else:
            st.success("✅ No duplicates found in GTIN Outer!")
    
    # Tab 3: GTIN Inner Duplicates
    with tab3:
        st.markdown("#### 📦 GTIN Inner Duplicates")
        
        if duplicate_results["inner"]:
            inner_df = duplicate_results["inner"]["duplicate_df"]
            
            if len(inner_df) > 0:
                # Analysis by Legal Entity
                st.markdown("##### 📊 By Legal Entity")
                inner_by_entity = inner_df.groupby("Legal Entity").agg({
                    gtin_inner_col: "count",
                    "gtin_inner_normalized": "nunique"
                }).reset_index()
                inner_by_entity.columns = ["Legal Entity", "Total Duplicates", "Unique Duplicated GTINs"]
                inner_by_entity = inner_by_entity.sort_values("Total Duplicates", ascending=False)
                st.dataframe(inner_by_entity, use_container_width=True, hide_index=True)
                
                # Summary by GTIN
                st.markdown("##### 📋 GTIN Summary")
                inner_summary = inner_df.groupby("gtin_inner_normalized").agg({
                    "Legal Entity": lambda x: ", ".join(sorted(x.unique()))
                }).reset_index()
                inner_summary["Duplicate Count"] = inner_df.groupby("gtin_inner_normalized").size().values
                inner_summary.columns = ["GTIN Inner", "Legal Entities", "Duplicate Count"]
                inner_summary = inner_summary.sort_values("Duplicate Count", ascending=False)
                
                st.markdown(f"**Found {duplicate_results['inner']['unique_duplicated_gtins']} unique GTINs with duplicates**")
                st.dataframe(inner_summary, use_container_width=True, hide_index=True)
                
                # Detailed view
                with st.expander("View All Duplicate Records"):
                    display_cols = ["Legal Entity", gtin_inner_col, "gtin_inner_normalized"]
                    if "SUPC" in inner_df.columns:
                        display_cols.append("SUPC")
                    if "Local Product Description" in inner_df.columns:
                        display_cols.append("Local Product Description")
                    
                    available_cols = [col for col in display_cols if col in inner_df.columns]
                    st.dataframe(inner_df[available_cols], use_container_width=True, hide_index=True)
            else:
                st.success("✅ No duplicates found in GTIN Inner!")
        else:
            st.info("ℹ️ GTIN Inner column not found in the data file.")
    
    # Tab 4: Generic GTINs Duplicates
    with tab4:
        st.markdown("#### ⚠️ Generic GTINs Duplicates Analysis")
        st.markdown("*Analysis of Generic GTINs that appear as duplicates*")
        
        if generic_results["total"] > 0:
            st.markdown(f"**Found {generic_results['total']:,} records with {generic_results['unique_gtins']:,} unique Generic GTINs**")
            
            if generic_results["duplicate_count"] > 0:
                st.markdown(f"**🔄 {generic_results['duplicate_count']:,} duplicate records ({generic_results['unique_duplicated_gtins']:,} unique duplicated Generic GTINs)**")
                
                # Duplicate Summary
                st.markdown("##### 📋 Generic GTINs Duplicate Summary")
                if len(generic_results["duplicate_summary"]) > 0:
                    st.dataframe(generic_results["duplicate_summary"], use_container_width=True, hide_index=True)
                    
                    # Chart: Duplicates by Entity Count
                    st.markdown("##### 📊 Distribution: How Many Entities Share Each Generic GTIN")
                    entity_count_dist = generic_results["duplicate_summary"]["Entity Count"].value_counts().sort_index()
                    fig_entity_dist = px.bar(
                        x=entity_count_dist.index,
                        y=entity_count_dist.values,
                        title="Number of Generic GTINs by Entity Count",
                        labels={"x": "Number of Legal Entities", "y": "Number of Generic GTINs"}
                    )
                    fig_entity_dist.update_layout(template='plotly_dark', height=400)
                    st.plotly_chart(fig_entity_dist, use_container_width=True)
                else:
                    st.info("No duplicate summary available")
            else:
                st.info("ℹ️ No duplicates found among Generic GTINs")
            
            # Distribution by Legal Entity (all Generic GTINs)
            st.markdown("##### 📊 Distribution by Legal Entity (All Generic GTINs)")
            if len(generic_results["by_entity"]) > 0:
                st.dataframe(generic_results["by_entity"], use_container_width=True, hide_index=True)
                
                # Chart
                fig_generic = px.bar(
                    generic_results["by_entity"],
                    x="Legal Entity",
                    y="Total Records",
                    title="Generic GTINs Distribution by Legal Entity",
                    labels={"Total Records": "Number of Records", "Legal Entity": "Legal Entity"}
                )
                fig_generic.update_layout(template='plotly_dark', height=400)
                st.plotly_chart(fig_generic, use_container_width=True)
            
            # Detailed view of duplicates
            if generic_results["duplicate_count"] > 0:
                with st.expander("View All Generic GTIN Duplicate Records"):
                    # Get only duplicate records
                    generic_duplicates_df = generic_results["full_df"][
                        generic_results["full_df"].duplicated(subset=["gtin_outer_normalized"], keep=False)
                    ].copy()
                    
                    display_cols = ["Legal Entity", gtin_outer_col, "gtin_outer_normalized"]
                    if "SUPC" in generic_duplicates_df.columns:
                        display_cols.append("SUPC")
                    if "Local Product Description" in generic_duplicates_df.columns:
                        display_cols.append("Local Product Description")
                    
                    available_cols = [col for col in display_cols if col in generic_duplicates_df.columns]
                    st.dataframe(generic_duplicates_df[available_cols], use_container_width=True, hide_index=True)
        else:
            st.success("✅ No Generic GTINs found!")
    
    # Tab 5: Placeholder GTINs
    with tab5:
        st.markdown("#### 🚫 Placeholder GTINs Analysis")
        st.markdown("*GTINs with placeholder values (9999...999)*")
        
        if placeholder_results["total"] > 0:
            st.markdown(f"**Found {placeholder_results['total']:,} records with {placeholder_results['unique_gtins']:,} unique Placeholder GTINs**")
            
            # By Legal Entity
            st.markdown("##### 📊 Distribution by Legal Entity")
            if len(placeholder_results["by_entity"]) > 0:
                st.dataframe(placeholder_results["by_entity"], use_container_width=True, hide_index=True)
                
                # Chart
                fig_placeholder = px.bar(
                    placeholder_results["by_entity"],
                    x="Legal Entity",
                    y="Total Records",
                    title="Placeholder GTINs by Legal Entity",
                    labels={"Total Records": "Number of Records", "Legal Entity": "Legal Entity"}
                )
                fig_placeholder.update_layout(template='plotly_dark', height=400)
                st.plotly_chart(fig_placeholder, use_container_width=True)
            
            # List of Placeholder GTINs
            st.markdown("##### 📋 Placeholder GTINs List")
            placeholder_list_df = pd.DataFrame({"Placeholder GTIN": placeholder_results["gtin_list"]})
            st.dataframe(placeholder_list_df, use_container_width=True, hide_index=True)
            
            # Detailed view
            with st.expander("View All Placeholder GTIN Records"):
                display_cols = ["Legal Entity", gtin_outer_col, "gtin_outer_normalized"]
                if generic_gtin_col and generic_gtin_col in placeholder_results["full_df"].columns:
                    display_cols.append(generic_gtin_col)
                if "SUPC" in placeholder_results["full_df"].columns:
                    display_cols.append("SUPC")
                if "Local Product Description" in placeholder_results["full_df"].columns:
                    display_cols.append("Local Product Description")
                
                available_cols = [col for col in display_cols if col in placeholder_results["full_df"].columns]
                st.dataframe(placeholder_results["full_df"][available_cols], use_container_width=True, hide_index=True)
        else:
            st.success("✅ No Placeholder GTINs found!")
    
    # Tab 6: Suspect GTINs
    with tab6:
        st.markdown("#### 🔍 Suspect GTINs Analysis")
        st.markdown("*GTINs with suspicious patterns (e.g., repeated digits like 18414900000000)*")
        
        if suspect_results["total"] > 0:
            st.markdown(f"**Found {suspect_results['total']:,} records with {suspect_results['unique_gtins']:,} unique Suspect GTINs**")
            
            # By Legal Entity
            st.markdown("##### 📊 Distribution by Legal Entity")
            if len(suspect_results["by_entity"]) > 0:
                st.dataframe(suspect_results["by_entity"], use_container_width=True, hide_index=True)
                
                # Chart
                fig_suspect = px.bar(
                    suspect_results["by_entity"],
                    x="Legal Entity",
                    y="Total Records",
                    title="Suspect GTINs by Legal Entity",
                    labels={"Total Records": "Number of Records", "Legal Entity": "Legal Entity"}
                )
                fig_suspect.update_layout(template='plotly_dark', height=400)
                st.plotly_chart(fig_suspect, use_container_width=True)
            
            # Sample Suspect GTINs
            st.markdown("##### 📋 Sample Suspect GTINs")
            suspect_list_df = pd.DataFrame({"Suspect GTIN": suspect_results["gtin_list"][:50]})
            st.dataframe(suspect_list_df, use_container_width=True, hide_index=True)
            
            # Detailed view
            with st.expander("View All Suspect GTIN Records"):
                display_cols = ["Legal Entity", gtin_outer_col, "gtin_outer_normalized"]
                if "SUPC" in suspect_results["full_df"].columns:
                    display_cols.append("SUPC")
                if "Local Product Description" in suspect_results["full_df"].columns:
                    display_cols.append("Local Product Description")
                
                available_cols = [col for col in display_cols if col in suspect_results["full_df"].columns]
                st.dataframe(suspect_results["full_df"][available_cols], use_container_width=True, hide_index=True)
        else:
            st.success("✅ No Suspect GTINs found!")
    
    # Tab 7: Valid GTINs by Entity
    with tab7:
        st.markdown("#### ✅ Valid GTINs - Sharing Analysis by Legal Entity")
        
        if valid_results["total"] > 0:
            st.markdown(f"**Found {valid_results['total']:,} records with {valid_results['unique_gtins']:,} unique Valid GTINs**")
            
            # Shared GTINs
            st.markdown("##### 🔗 GTINs Shared Across Multiple Legal Entities")
            if len(valid_results["shared_gtins"]) > 0:
                st.markdown(f"**{len(valid_results['shared_gtins'])} GTINs are shared across multiple entities**")
                st.dataframe(valid_results["shared_gtins"].head(50), use_container_width=True, hide_index=True)
                
                # Chart: Distribution of sharing
                sharing_dist = valid_results["shared_gtins"]["Entity Count"].value_counts().sort_index()
                fig_sharing = px.bar(
                    x=sharing_dist.index,
                    y=sharing_dist.values,
                    title="Distribution: How Many Entities Share GTINs",
                    labels={"x": "Number of Entities", "y": "Number of GTINs"}
                )
                fig_sharing.update_layout(template='plotly_dark', height=400)
                st.plotly_chart(fig_sharing, use_container_width=True)
            
            # Entity-to-Entity Sharing
            st.markdown("##### 🤝 Entity-to-Entity GTIN Sharing")
            if len(valid_results["entity_sharing"]) > 0:
                st.markdown("**Top Entity Pairs Sharing GTINs:**")
                st.dataframe(valid_results["entity_sharing"].head(30), use_container_width=True, hide_index=True)
                
                # Heatmap visualization (if not too many entities)
                if len(valid_results["entity_sharing"]) > 0 and len(valid_results["entity_sharing"]) < 200:
                    # Create a matrix for heatmap
                    entities = sorted(set(valid_results["entity_sharing"]["Entity 1"].tolist() + 
                                         valid_results["entity_sharing"]["Entity 2"].tolist()))
                    if len(entities) <= 20:  # Only show heatmap if reasonable number of entities
                        sharing_matrix = pd.DataFrame(0, index=entities, columns=entities)
                        for _, row in valid_results["entity_sharing"].iterrows():
                            sharing_matrix.loc[row["Entity 1"], row["Entity 2"]] = row["Shared GTINs"]
                            sharing_matrix.loc[row["Entity 2"], row["Entity 1"]] = row["Shared GTINs"]
                        
                        fig_heatmap = px.imshow(
                            sharing_matrix.values,
                            labels=dict(x="Legal Entity", y="Legal Entity", color="Shared GTINs"),
                            x=entities,
                            y=entities,
                            title="GTIN Sharing Heatmap Between Legal Entities",
                            color_continuous_scale="Blues"
                        )
                        fig_heatmap.update_layout(template='plotly_dark', height=600)
                        st.plotly_chart(fig_heatmap, use_container_width=True)
            
            # Detailed sharing information
            st.markdown("##### 📋 Detailed GTIN Sharing Information")
            if len(valid_results["sharing_details"]) > 0:
                st.dataframe(valid_results["sharing_details"].head(100), use_container_width=True, hide_index=True)
            
            # Summary statistics
            st.markdown("##### 📊 Summary Statistics")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Valid GTINs", f"{valid_results['unique_gtins']:,}")
            with col2:
                shared_count = len(valid_results["shared_gtins"])
                st.metric("Shared GTINs", f"{shared_count:,}", 
                         f"{shared_count/valid_results['unique_gtins']*100:.1f}%" if valid_results['unique_gtins'] > 0 else "0%")
            with col3:
                st.metric("Entity Pairs Sharing", f"{len(valid_results['entity_sharing']):,}")
        else:
            st.info("ℹ️ No valid GTINs found in the data.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"<div style='text-align: center; color: #cbd5e1; padding: 1rem;'>"
        f"📅 Analysis generated on {date.today().strftime('%B %d, %Y')} | "
        f"Filtered: <strong style='color: #94a3b8;'>{len(df_filtered):,}</strong> products from <strong style='color: #94a3b8;'>{total_rows:,}</strong> total | "
        f"Legal Entities: <strong style='color: #94a3b8;'>{', '.join(selected_entities)}</strong>"
        f"</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

import os
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
from export_utils import to_excel_bytes, to_excel_bytes_cross_duplicates
from auth_utils import render_login_form
from duplicate_analysis_backend import (
    list_output_dates,
    load_output_results,
    OUTPUTS_BASE,
)
from tracker_utils import save_tracker_data, has_tracker_entry_for


@st.cache_data(ttl=3600)
def _cached_load_output_results(output_dir: str, selected_entities_key=None):
    """Cache Duplicate Analysis results (avoids re-reading many large Excel on every rerun). selected_entities_key: tuple of entities or None for all."""
    entities = list(selected_entities_key) if selected_entities_key else None
    return load_output_results(output_dir, selected_entities=entities)

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
    page_title="GTIN Duplicate Analysis",
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
        min-height: 8rem;
    }
    /* Overview 7 metrics: equal column width */
    div[data-testid="stHorizontalBlock"]:has(> div:nth-of-type(7)) > div {
        flex: 1 1 0 !important;
        min-width: 0 !important;
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

INPUT_FILE = "all-products-prod-2026-01-22_15.44.25.xlsx"


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
def load_duplicate_data(file_path: str, file_mtime: float):
    """Load data and find GTIN Outer, Inner, and Generic GTIN columns. Cached by (path, mtime) so cache invalidates when file is updated."""
    df = pd.read_excel(file_path, dtype=str)
    
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
    
    # Filter: suspect AND not generic AND not placeholder (EXPLICIT_BLOCKED / PLACEHOLDER)
    suspect_df = df[
        (df["is_suspect"] == True)
        & (df["gtin_status"] != "GENERIC_GTIN")
        & (df["gtin_status"] != "EXPLICIT_BLOCKED")
        & (df["gtin_status"] != "PLACEHOLDER")
    ].copy()
    
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


def analyze_inner_equals_outer(df, gtin_outer_col, gtin_inner_col):
    """
    1) same_row: rows where GTIN Outer == GTIN Inner on the same row (excl. Generics/Placeholders).
    2) Inner = Outer (non-Generic): for each Inner GTIN (non-Generic/Placeholder) that matches at least one
       Outer GTIN (non-Generic/Placeholder) somewhere, split by:
       - Same Legal Entity: all Outer matches are in the same Legal Entity as the row.
       - Different Legal Entities: at least 2 Legal Entities involved (or at least one match in another entity).
    """
    if not gtin_inner_col or gtin_inner_col not in df.columns or "gtin_inner_normalized" not in df.columns:
        return {
            "same_row": {"total": 0, "unique_gtins": 0, "df": pd.DataFrame(), "gtin_list": []},
            "same_entity": {"total": 0, "unique_gtins": 0, "df": pd.DataFrame(), "gtin_list": []},
            "other_entity": {"total": 0, "unique_gtins": 0, "df": pd.DataFrame(), "gtin_list": []},
            "has_inner": False,
        }
    df = df.copy()
    df["_outer_status"] = df["gtin_outer_normalized"].apply(
        lambda x: classify_gtin_status(x) if x is not None else "MISSING"
    )
    df["_inner_status"] = df["gtin_inner_normalized"].apply(
        lambda x: classify_gtin_status(x) if x is not None else "MISSING"
    )
    excluded = {"GENERIC_GTIN", "EXPLICIT_BLOCKED"}
    ok_outer = ~df["_outer_status"].isin(excluded) & df["gtin_outer_normalized"].notna()
    ok_inner = ~df["_inner_status"].isin(excluded) & df["gtin_inner_normalized"].notna()
    outer_str = df["gtin_outer_normalized"].astype(str).str.strip()
    inner_str = df["gtin_inner_normalized"].astype(str).str.strip()
    inner_eq_outer_row = (inner_str == outer_str) & outer_str.ne("") & inner_str.ne("")

    # 1) Same row: Outer == Inner on the same row (excl. Generics/Placeholders)
    same_row_df = df[ok_outer & ok_inner & inner_eq_outer_row].copy()
    same_row_df = same_row_df.drop(columns=["_outer_status", "_inner_status"], errors="ignore")

    # 2) Build: for each Outer GTIN value (normalized str), set of Legal Entities where it appears as Outer
    ok_rows = df[ok_outer].copy()
    ok_rows["_outer_key"] = ok_rows["gtin_outer_normalized"].astype(str).str.strip()
    entities_by_outer_gtin = (
        ok_rows.groupby("_outer_key")["Legal Entity"]
        .apply(lambda s: set(s.dropna().unique()))
        .to_dict()
    )

    # Rows where Inner is non-Generic and Inner != Outer on the row
    with_inner = df[
        ok_inner
        & df["gtin_inner_normalized"].notna()
        & (inner_str != "")
        & (~inner_eq_outer_row)
    ].copy()
    with_inner = with_inner.drop(columns=["_outer_status", "_inner_status"], errors="ignore")
    with_inner["_inner_key"] = with_inner["gtin_inner_normalized"].astype(str).str.strip()

    if len(with_inner) == 0:
        return {
            "same_row": _same_row_result(same_row_df),
            "same_entity": {"total": 0, "unique_gtins": 0, "df": pd.DataFrame(), "gtin_list": []},
            "other_entity": {"total": 0, "unique_gtins": 0, "df": pd.DataFrame(), "gtin_list": []},
            "has_inner": True,
        }

    # For each row: entities where this Inner value appears as Outer (loop faster than apply(axis=1))
    buckets = []
    for inner_k, row_entity in zip(with_inner["_inner_key"], with_inner["Legal Entity"]):
        entities = entities_by_outer_gtin.get(inner_k, set())
        if not entities:
            buckets.append("none")
        elif entities == {row_entity}:
            buckets.append("same_entity")
        else:
            buckets.append("other_entity")
    with_inner["_bucket"] = buckets
    same_entity_df = with_inner[with_inner["_bucket"] == "same_entity"].drop(
        columns=["_inner_key", "_bucket"], errors="ignore"
    )
    other_entity_df = with_inner[with_inner["_bucket"] == "other_entity"].drop(
        columns=["_inner_key", "_bucket"], errors="ignore"
    )

    return {
        "same_row": _same_row_result(same_row_df),
        "same_entity": {
            "total": len(same_entity_df),
            "unique_gtins": same_entity_df["gtin_inner_normalized"].nunique() if len(same_entity_df) > 0 else 0,
            "df": same_entity_df,
            "gtin_list": same_entity_df["gtin_inner_normalized"].unique().tolist() if len(same_entity_df) > 0 else [],
        },
        "other_entity": {
            "total": len(other_entity_df),
            "unique_gtins": other_entity_df["gtin_inner_normalized"].nunique() if len(other_entity_df) > 0 else 0,
            "df": other_entity_df,
            "gtin_list": other_entity_df["gtin_inner_normalized"].unique().tolist() if len(other_entity_df) > 0 else [],
        },
        "has_inner": True,
    }


def _same_row_result(same_row_df):
    return {
        "total": len(same_row_df),
        "unique_gtins": same_row_df["gtin_inner_normalized"].nunique() if len(same_row_df) > 0 else 0,
        "df": same_row_df,
        "gtin_list": same_row_df["gtin_inner_normalized"].unique().tolist() if len(same_row_df) > 0 else [],
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
    return render_login_form("GTIN Duplicate Analysis")


def main():
    # Password protection
    if not check_password():
        st.stop()
    
    # Header
    st.markdown('<h1 class="main-header">🔍 GTIN Duplicate Analysis</h1>', unsafe_allow_html=True)

    # Load from pre-computed outputs (batch writes to outputs/YYYY-MM-DD/)
    output_dates = list_output_dates()
    if not output_dates:
        st.info(
            f"No pre-computed results. Run the batch then reload this page:\n\n"
            f"`python run_duplicate_analysis_batch.py [file.xlsx]`\n\n"
            f"Results will be written to `{OUTPUTS_BASE}/YYYY-MM-DD/`."
        )
        st.code("python run_duplicate_analysis_batch.py all-products-prod-2026-01-22_15.44.25.xlsx", language="bash")
        return

    # Select extract date
    date_options = [f"{d[0]} ({d[1]})" for d in output_dates]
    date_paths = {date_options[i]: output_dates[i][1] for i in range(len(output_dates))}
    selected_date_label = st.selectbox(
        "**Extract date**",
        date_options,
        index=0,
        help="Latest run first. Run the batch to add a date.",
        key="dup_select_date",
    )
    output_dir = date_paths[selected_date_label]

    with st.spinner("Loading results…"):
        loaded = _cached_load_output_results(output_dir, None)
    if loaded is None:
        st.error("Unable to load results for this date.")
        return
    overview, manifest, duplicate_results, generic_results, placeholder_results, suspect_results, valid_results, inner_eq_outer_results, total_rows, gtin_outer_col, gtin_inner_col = loaded
    source_file = overview.get("source_file", "")
    extract_date = overview.get("extract_date", "")
    generic_gtin_col = manifest.get("generic_gtin_col")

    # Auto-save to tracker when this output is not yet recorded
    if not has_tracker_entry_for(extract_date, source_file, "duplicate"):
        tracker_entry = {
            "analysis_type": "duplicate",
            "extract_date": extract_date,
            "source_file": source_file,
            "legal_entities": overview.get("legal_entities", []),
            "total_products": total_rows,
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
            "valid_gtins": valid_results["total"],
        }
        save_tracker_data(tracker_entry)

    st.markdown(f'<div style="text-align: center; color: #cbd5e1; margin-bottom: 0.5rem;">📁 Source: <strong style="color: #94a3b8;">{source_file}</strong></div>', unsafe_allow_html=True)

    # Filter section by Legal Entity (client-side filter on pre-computed data)
    legal_entities = overview.get("legal_entities", [])
    st.markdown('<div class="filter-section">', unsafe_allow_html=True)
    st.markdown("### 🔍 Filters")

    if "selected_entities_duplicate" not in st.session_state:
        st.session_state.selected_entities_duplicate = legal_entities

    col1, col2 = st.columns([4, 1])
    with col1:
        selected_entities = st.multiselect(
            "**Select Legal Entities**",
            legal_entities,
            default=st.session_state.selected_entities_duplicate,
            help="Filter displayed results by Legal Entity.",
        )
        st.session_state.selected_entities_duplicate = selected_entities

    with col2:
        st.markdown('<div style="padding-top: 1.5rem;">', unsafe_allow_html=True)
        if st.button("🔄 Reset to All", use_container_width=True, key="reset_all_duplicate"):
            st.session_state.selected_entities_duplicate = legal_entities
            st.rerun()
        if st.button("Reset", use_container_width=True, key="reset_duplicate"):
            st.session_state.selected_entities_duplicate = []
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    if not selected_entities:
        st.warning("⚠️ Please select at least one Legal Entity")
        return

    # Re-load with entity filter so metrics/tables reflect selection
    with st.spinner("Applying Legal Entity filter…"):
        loaded = _cached_load_output_results(output_dir, tuple(selected_entities) if selected_entities else None)
    if loaded is None:
        return
    overview, _, duplicate_results, generic_results, placeholder_results, suspect_results, valid_results, inner_eq_outer_results, total_rows, gtin_outer_col, gtin_inner_col = loaded

    entity_counts = overview.get("entity_total_products", {})
    df_filtered_len = sum(entity_counts.get(e, 0) for e in selected_entities) if selected_entities else total_rows
    
    # Overview Metrics
    st.markdown('<div class="section-header">📊 Overview</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
    with col1:
        st.metric("📦 Total Products", f"{df_filtered_len:,}", 
                 f"Filtered from {total_rows:,} total")
    
    with col2:
        outer_dup = duplicate_results["outer"]["total_duplicates"]
        st.metric("🔄 Outer Duplicates", f"{outer_dup:,}", 
                 f"{outer_dup/df_filtered_len*100:.1f}%" if df_filtered_len > 0 else "0%")
    
    with col3:
        if duplicate_results["cross"]:
            cross_dup = duplicate_results["cross"]["unique_cross_gtins"]
            st.metric("🔀 Cross Duplicates", f"{cross_dup:,}",
                     f"{duplicate_results['cross']['total_records']:,} records")
        else:
            st.metric("🔀 Cross Duplicates", "N/A", "Inner column not found")
    
    with col4:
        generic_total = generic_results.get('total', 0)
        unique_gtins = generic_results.get('unique_gtins', 0)
        st.metric("⚠️ Generic GTINs", f"{generic_total:,}", 
                 f"{unique_gtins:,} unique")
    
    with col5:
        st.metric("🚫 Placeholder GTINs", f"{placeholder_results['total']:,}",
                 f"{placeholder_results['unique_gtins']:,} unique")
    
    with col6:
        st.metric("🔍 Suspect GTINs", f"{suspect_results['total']:,}",
                 f"{suspect_results['unique_gtins']:,} unique",
                 help="Suspect = same digit ≥60% of length, or ≥6 trailing zeros (or half length). Excludes Generic.")
    
    with col7:
        st.metric("✅ Valid GTINs", f"{valid_results['total']:,}",
                 f"{valid_results['unique_gtins']:,} unique")
    
    # Detailed Analysis
    st.markdown('<div class="section-header">📋 Detailed Analysis</div>', unsafe_allow_html=True)
    
    # Tabs for different analysis types
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "GTIN Outer Duplicates", 
        "GTIN Inner Duplicates",
        "Cross Duplicates",
        "Generic GTINs",
        "Placeholder GTINs",
        "Suspect GTINs",
        "Valid GTINs by Entity",
        "Outer = Inner (same row)",
        "Inner = Outer (non-Generic)"
    ])
    
    # Tab 1: GTIN Outer Duplicates
    with tab1:
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
            st.download_button("Download as Excel", data=to_excel_bytes(outer_summary), file_name="outer_duplicates_summary.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_outer_summary")
            
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
    
    # Tab 2: GTIN Inner Duplicates
    with tab2:
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
                st.download_button("Download as Excel", data=to_excel_bytes(inner_summary), file_name="inner_duplicates_summary.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_inner_summary")
                
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
    
    # Tab 3: Cross Duplicates (moved after Inner Duplicates)
    with tab3:
        st.markdown("#### 🔀 Cross Duplicates (GTIN appears in both Outer and Inner)")
        st.markdown("""
        <div style="background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #60a5fa; margin-bottom: 1rem;">
            <strong style="color: #60a5fa;">ℹ️ Différence avec "Inner = Outer (non-Generic)" :</strong><br>
            <span style="color: #cbd5e1;">
            <strong>Cross Duplicates</strong> identifie les GTINs qui apparaissent <strong>à la fois</strong> dans la colonne Outer <strong>ET</strong> dans la colonne Inner, 
            mais pas nécessairement sur la même ligne. Un GTIN peut être Outer sur une ligne et Inner sur une autre ligne (même entité ou entité différente).<br><br>
            <strong>Inner = Outer (non-Generic)</strong> identifie uniquement les cas où <strong>sur la même ligne</strong>, le GTIN Inner est <strong>égal</strong> au GTIN Outer 
            (et où les deux ne sont pas des Generic GTINs).
            </span>
        </div>
        """, unsafe_allow_html=True)
        
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
                
                # Download all records with green formatting
                st.download_button("Download as Excel", data=to_excel_bytes_cross_duplicates(cross_df, gtin_outer_col, gtin_inner_col), file_name="cross_duplicates_all.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_cross_all")
                
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
                    st.download_button("Download as Excel", data=to_excel_bytes(generic_results["duplicate_summary"]), file_name="generic_duplicates_summary.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_generic_dup")
                    
                    # Chart: Duplicates by Entity Count
                    st.markdown("##### 📊 Distribution: How Many Entities Share Each Generic GTIN")
                    dup_sum = generic_results["duplicate_summary"]
                    entity_count_col = next((c for c in dup_sum.columns if "entity" in c.lower() and "count" in c.lower()), None)
                    if entity_count_col is not None:
                        entity_count_dist = dup_sum[entity_count_col].value_counts().sort_index()
                        fig_entity_dist = px.bar(
                            x=entity_count_dist.index,
                            y=entity_count_dist.values,
                            title="Number of Generic GTINs by Entity Count",
                            labels={"x": "Number of Legal Entities", "y": "Number of Generic GTINs"}
                        )
                        fig_entity_dist.update_layout(template='plotly_dark', height=400)
                        st.plotly_chart(fig_entity_dist, use_container_width=True)
                    else:
                        st.caption("(Entity count column not found in duplicate summary)")
                else:
                    st.info("No duplicate summary available")
            else:
                st.info("ℹ️ No duplicates found among Generic GTINs")
            
            # Distribution by Legal Entity (all Generic GTINs)
            st.markdown("##### 📊 Distribution by Legal Entity (All Generic GTINs)")
            if len(generic_results["by_entity"]) > 0:
                st.dataframe(generic_results["by_entity"], use_container_width=True, hide_index=True)
                st.download_button("Download as Excel", data=to_excel_bytes(generic_results["by_entity"]), file_name="generic_by_entity.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_generic_by_ent")
                
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
                st.download_button("Download as Excel", data=to_excel_bytes(placeholder_results["by_entity"]), file_name="placeholder_by_entity.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_placeholder_by_ent")
                
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
            # Extract GTINs from gtin_list or from full_df if list is empty
            if placeholder_results.get("gtin_list") and len(placeholder_results["gtin_list"]) > 0:
                placeholder_gtins = placeholder_results["gtin_list"]
            elif len(placeholder_results["full_df"]) > 0 and "gtin_outer_normalized" in placeholder_results["full_df"].columns:
                placeholder_gtins = placeholder_results["full_df"]["gtin_outer_normalized"].dropna().unique().tolist()
            else:
                placeholder_gtins = []
            
            if len(placeholder_gtins) > 0:
                placeholder_list_df = pd.DataFrame({"Placeholder GTIN": placeholder_gtins})
                st.dataframe(placeholder_list_df, use_container_width=True, hide_index=True)
            else:
                st.info("ℹ️ Placeholder GTIN list not available. Please regenerate the analysis batch to include placeholder details.")
            
            # Detailed view
            with st.expander("View All Placeholder GTIN Records"):
                if len(placeholder_results["full_df"]) > 0:
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
                    st.info("ℹ️ Detailed placeholder records not available. Please regenerate the analysis batch to include placeholder details.")
        else:
            st.success("✅ No Placeholder GTINs found!")
    
    # Tab 6: Suspect GTINs
    with tab6:
        st.markdown("#### 🔍 Suspect GTINs Analysis")
        
        st.markdown("""
        **Detection Criteria:**
        
        A GTIN is marked as **Suspect** if it meets any of the following conditions:
        
        1. **Excessive digit repetition** : A single digit appears ≥ 60% of the GTIN length
           - Example: `11111111111111` (digit 1 appears 14 times out of 14)
           - Example: `18414900000000` (digit 0 appears 8 times out of 14)
        
        2. **Too many trailing zeros** : 
           - At least 6 consecutive zeros at the end, OR
           - Half the GTIN length (or more) in trailing zeros
           - Example: `18414900000000` (8 zeros at the end out of 14 digits)
        
        **Note:** Generic GTINs are excluded from this analysis.
        """)
        
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
            # Get unique GTINs from gtin_list or extract from full_df if list is empty
            if suspect_results.get("gtin_list") and len(suspect_results["gtin_list"]) > 0:
                suspect_gtins = suspect_results["gtin_list"][:50]
            elif len(suspect_results["full_df"]) > 0 and "gtin_outer_normalized" in suspect_results["full_df"].columns:
                suspect_gtins = suspect_results["full_df"]["gtin_outer_normalized"].dropna().unique().tolist()[:50]
            else:
                suspect_gtins = []
            
            if len(suspect_gtins) > 0:
                suspect_list_df = pd.DataFrame({"Suspect GTIN": suspect_gtins})
                st.dataframe(suspect_list_df, use_container_width=True, hide_index=True)
                
                # Get all suspect GTINs for download
                if suspect_results.get("gtin_list") and len(suspect_results["gtin_list"]) > 0:
                    all_suspect_gtins = suspect_results["gtin_list"]
                elif len(suspect_results["full_df"]) > 0 and "gtin_outer_normalized" in suspect_results["full_df"].columns:
                    all_suspect_gtins = suspect_results["full_df"]["gtin_outer_normalized"].dropna().unique().tolist()
                else:
                    all_suspect_gtins = []
                
                if len(all_suspect_gtins) > 0:
                    st.download_button("Download as Excel (all Suspect GTINs)", data=to_excel_bytes(pd.DataFrame({"Suspect GTIN": all_suspect_gtins})), file_name="suspect_gtins_all.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_suspect_gtins_all")
            else:
                st.info("No suspect GTINs to display.")
            
            # Detailed view
            with st.expander("View All Suspect GTIN Records"):
                if len(suspect_results["full_df"]) > 0:
                    display_cols = ["Legal Entity", gtin_outer_col, "gtin_outer_normalized"]
                    if "SUPC" in suspect_results["full_df"].columns:
                        display_cols.append("SUPC")
                    if "Local Product Description" in suspect_results["full_df"].columns:
                        display_cols.append("Local Product Description")
                    
                    available_cols = [col for col in display_cols if col in suspect_results["full_df"].columns]
                    st.dataframe(suspect_results["full_df"][available_cols], use_container_width=True, hide_index=True)
                    st.download_button("Download as Excel (all records)", data=to_excel_bytes(suspect_results["full_df"][available_cols]), file_name="suspect_records_all.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_suspect_records_all")
                else:
                    st.info("No detailed records available. Please regenerate the analysis batch to include suspect GTIN details.")
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
                st.download_button("Download as Excel (all)", data=to_excel_bytes(valid_results["shared_gtins"]), file_name="valid_shared_gtins_all.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_shared_gtins_all")
                
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
                st.download_button("Download as Excel (all)", data=to_excel_bytes(valid_results["entity_sharing"]), file_name="valid_entity_sharing_all.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_entity_sharing_all")
                
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
                st.download_button("Download as Excel (all)", data=to_excel_bytes(valid_results["sharing_details"]), file_name="valid_gtins_sharing_all.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_valid_sharing")
            
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
    
    # Tab 8: Outer = Inner (same row)
    with tab8:
        st.markdown("#### Outer = Inner (same row)")
        st.markdown("*Rows where GTIN Outer = GTIN Inner on the same row (excluding Generics and Placeholders).*")
        if not inner_eq_outer_results["has_inner"]:
            st.info("GTIN Inner column not found. This analysis requires both Outer and Inner columns.")
        else:
            same_row = inner_eq_outer_results["same_row"]
            st.metric("Records", f"{same_row['total']:,}", f"{same_row['unique_gtins']:,} unique GTINs")
            if same_row["total"] > 0:
                same_row_df = same_row["df"]
                by_ent = same_row_df.groupby("Legal Entity").agg(
                    records=("gtin_inner_normalized", "count"),
                    unique_gtins=("gtin_inner_normalized", "nunique")
                ).reset_index()
                by_ent = by_ent.sort_values("records", ascending=False)
                st.dataframe(by_ent, use_container_width=True, hide_index=True)
                st.download_button("Download as Excel", data=to_excel_bytes(same_row_df), file_name="outer_eq_inner_same_row.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_outer_eq_inner_same_row")
                with st.expander("View records"):
                    disp = [c for c in ["Legal Entity", gtin_outer_col, gtin_inner_col, "gtin_outer_normalized", "gtin_inner_normalized", "SUPC", "Local Product Description"] if c in same_row_df.columns]
                    st.dataframe(same_row_df[disp], use_container_width=True, hide_index=True)
            else:
                st.success("No records where Outer = Inner on the same row (excluding Generics/Placeholders).")

    # Tab 9: Inner = Outer (non-Generic)
    with tab9:
        st.markdown("#### Inner = Outer (non-Generic)")
        st.markdown("*GTIN Inner that equal a GTIN Outer somewhere, excluding Generic Outers. Two sub-analyses: same Legal Entity vs different Legal Entities.*")
        
        with st.spinner("Loading Inner = Outer (non-Generic) data…"):
            if not inner_eq_outer_results["has_inner"]:
                st.info("GTIN Inner column not found. This analysis requires both Outer and Inner columns.")
            else:
                same = inner_eq_outer_results["same_entity"]
                other = inner_eq_outer_results["other_entity"]
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Same Legal Entity", f"{same['total']:,}", f"{same['unique_gtins']:,} unique GTINs")
                with col2:
                    st.metric("Different Legal Entities", f"{other['total']:,}", f"{other['unique_gtins']:,} unique GTINs")
                
                st.markdown("##### Same Legal Entity")
                st.markdown("*Records where this row's GTIN Inner equals a GTIN Outer (non-Generic) in the **same** Legal Entity.*")
                if same["total"] > 0:
                    same_df = same["df"]
                    by_ent = same_df.groupby("Legal Entity").agg(
                        records=("gtin_inner_normalized", "count"),
                        unique_gtins=("gtin_inner_normalized", "nunique")
                    ).reset_index()
                    by_ent = by_ent.sort_values("records", ascending=False)
                    st.dataframe(by_ent, use_container_width=True, hide_index=True)
                    _same_entity_path = os.path.join(output_dir, "inner_eq_outer_same_entity.xlsx")
                    if set(selected_entities or []) == set(legal_entities) and os.path.isfile(_same_entity_path):
                        with open(_same_entity_path, "rb") as _f:
                            _same_entity_bytes = _f.read()
                    else:
                        _same_entity_bytes = to_excel_bytes(same_df)
                    st.download_button("Download as Excel", data=_same_entity_bytes, file_name="inner_eq_outer_same_entity.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_inner_eq_same")
                    with st.expander("View records (Same Legal Entity)"):
                        disp = [c for c in ["Legal Entity", gtin_outer_col, gtin_inner_col, "gtin_outer_normalized", "gtin_inner_normalized", "SUPC", "Local Product Description"] if c in same_df.columns]
                        st.dataframe(same_df[disp], use_container_width=True, hide_index=True)
                else:
                    st.success("No records where Inner = Outer (non-Generic) within the same Legal Entity.")
                
                st.markdown("##### Different Legal Entities")
                st.markdown("*Records where this row's GTIN Inner equals a GTIN Outer (non-Generic) in a **different** Legal Entity.*")
                if other["total"] > 0:
                    other_df = other["df"]
                    by_ent = other_df.groupby("Legal Entity").agg(
                        records=("gtin_inner_normalized", "count"),
                        unique_gtins=("gtin_inner_normalized", "nunique")
                    ).reset_index()
                    by_ent = by_ent.sort_values("records", ascending=False)
                    st.dataframe(by_ent, use_container_width=True, hide_index=True)
                    _other_entity_path = os.path.join(output_dir, "inner_eq_outer_other_entity.xlsx")
                    if set(selected_entities or []) == set(legal_entities) and os.path.isfile(_other_entity_path):
                        with open(_other_entity_path, "rb") as _f:
                            _other_entity_bytes = _f.read()
                    else:
                        _other_entity_bytes = to_excel_bytes(other_df)
                    st.download_button("Download as Excel", data=_other_entity_bytes, file_name="inner_eq_outer_other_entity.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_inner_eq_other")
                    with st.expander("View records (Different Legal Entities)"):
                        disp = [c for c in ["Legal Entity", gtin_outer_col, gtin_inner_col, "gtin_outer_normalized", "gtin_inner_normalized", "SUPC", "Local Product Description"] if c in other_df.columns]
                        st.dataframe(other_df[disp], use_container_width=True, hide_index=True)
                else:
                    st.success("No records where Inner = Outer (non-Generic) across different Legal Entities.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"<div style='text-align: center; color: #cbd5e1; padding: 1rem;'>"
        f"📅 Analysis generated on {date.today().strftime('%B %d, %Y')} | "
        f"Filtered: <strong style='color: #94a3b8;'>{df_filtered_len:,}</strong> products from <strong style='color: #94a3b8;'>{total_rows:,}</strong> total | "
        f"Legal Entities: <strong style='color: #94a3b8;'>{', '.join(selected_entities) if selected_entities else '—'}</strong>"
        f"</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

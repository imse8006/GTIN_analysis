"""
Backend for Duplicate Analysis: load data, run all analyses, write results to a dated folder.
No Streamlit dependency. Used by run_duplicate_analysis_batch.py and by Streamlit to read pre-computed outputs.
"""
import json
import os
from pathlib import Path
from datetime import datetime
from collections import Counter

import pandas as pd

try:
    from gtin_analysis import classify_gtin_status
except ImportError:
    from gtin_analysis import (
        VALID_LENGTHS,
        has_valid_gs1_check_digit,
        classify_gtin_status,
    )

from export_utils import to_excel_bytes, to_excel_bytes_inner_outer_paired


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


def load_duplicate_data_from_path(file_path: str):
    """Load data and find GTIN Outer, Inner, Generic columns. No Streamlit. Returns (df, gtin_outer_col, gtin_inner_col, generic_gtin_col) or (None, None, None, None) on error."""
    if not os.path.isfile(file_path):
        return None, None, None, None
    df = pd.read_excel(file_path, dtype=str)

    gtin_outer_col = None
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if "gtin" in col_lower and "outer" in col_lower:
            gtin_outer_col = col
            break
    if gtin_outer_col is None:
        for col in df.columns:
            if str(col).lower().strip() in ["gtin-outer", "gtin_outer", "gtinouter"]:
                gtin_outer_col = col
                break

    generic_gtin_col = None
    for col in df.columns:
        if "generic" in str(col).lower() and "gtin" in str(col).lower():
            generic_gtin_col = col
            break

    gtin_inner_col = None
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if "gtin" in col_lower and "inner" in col_lower:
            gtin_inner_col = col
            break
    if gtin_inner_col is None:
        for col in df.columns:
            if str(col).lower().strip() in ["gtin-inner", "gtin_inner", "gtininner"]:
                gtin_inner_col = col
                break

    if gtin_outer_col is None:
        return None, None, None, None

    def get_gtin_outer_normalized(row):
        has_outer = gtin_outer_col and pd.notna(row.get(gtin_outer_col)) and str(row.get(gtin_outer_col)).strip() not in ["", "nan"]
        has_generic = generic_gtin_col and pd.notna(row.get(generic_gtin_col)) and str(row.get(generic_gtin_col)).strip() not in ["", "nan"]
        if has_outer and has_generic:
            return normalize_gtin(row[gtin_outer_col])
        elif has_outer:
            return normalize_gtin(row[gtin_outer_col])
        elif has_generic:
            return normalize_gtin(row[generic_gtin_col])
        return None

    df["gtin_outer_normalized"] = df.apply(get_gtin_outer_normalized, axis=1)
    df["gtin_source"] = df.apply(
        lambda r: "GTIN Outer (both filled)" if (gtin_outer_col and pd.notna(r.get(gtin_outer_col)) and generic_gtin_col and pd.notna(r.get(generic_gtin_col))) else
                 ("GTIN Outer" if (gtin_outer_col and pd.notna(r.get(gtin_outer_col)) and str(r.get(gtin_outer_col)).strip() not in ["", "nan"]) else
                  ("Generic GTIN" if (generic_gtin_col and pd.notna(r.get(generic_gtin_col))) else "None")),
        axis=1
    )
    if gtin_inner_col:
        df["gtin_inner_normalized"] = df[gtin_inner_col].apply(normalize_gtin)
    else:
        df["gtin_inner_normalized"] = None

    return df, gtin_outer_col, gtin_inner_col, generic_gtin_col


def is_suspect_gtin(gtin):
    if pd.isna(gtin) or gtin is None:
        return False
    gtin_str = normalize_gtin(gtin)
    if not gtin_str or not gtin_str.isdigit():
        return False
    digit_counts = Counter(gtin_str)
    max_count = max(digit_counts.values())
    if gtin_str.endswith("0" * max(6, len(gtin_str) // 2)):
        return True
    return max_count >= len(gtin_str) * 0.6


def analyze_duplicates(df, gtin_outer_col, gtin_inner_col):
    results = {}
    outer_duplicates = df[df.duplicated(subset=["gtin_outer_normalized"], keep=False)].copy()
    results["outer"] = {
        "total_duplicates": len(outer_duplicates),
        "unique_duplicated_gtins": outer_duplicates["gtin_outer_normalized"].nunique() if len(outer_duplicates) > 0 else 0,
        "duplicate_df": outer_duplicates,
    }
    if gtin_inner_col:
        inner_duplicates = df[df.duplicated(subset=["gtin_inner_normalized"], keep=False)].copy()
        results["inner"] = {
            "total_duplicates": len(inner_duplicates),
            "unique_duplicated_gtins": inner_duplicates["gtin_inner_normalized"].nunique() if len(inner_duplicates) > 0 else 0,
            "duplicate_df": inner_duplicates,
        }
        outer_values = set(df["gtin_outer_normalized"].dropna().unique())
        inner_values = set(df["gtin_inner_normalized"].dropna().unique())
        cross_duplicates = outer_values.intersection(inner_values)
        cross_df = df[df["gtin_outer_normalized"].isin(cross_duplicates) | df["gtin_inner_normalized"].isin(cross_duplicates)].copy() if cross_duplicates else pd.DataFrame()
        results["cross"] = {
            "unique_cross_gtins": len(cross_duplicates),
            "total_records": len(cross_df),
            "cross_df": cross_df,
            "gtin_list": list(cross_duplicates),
        }
    else:
        results["inner"] = None
        results["cross"] = None
    return results


def analyze_generic_gtins(df, gtin_outer_col, generic_gtin_col=None):
    df = df.copy()
    df["gtin_status"] = df["gtin_outer_normalized"].apply(lambda x: classify_gtin_status(x) if x is not None else "MISSING")
    if generic_gtin_col and generic_gtin_col in df.columns:
        generic_df = df[df[generic_gtin_col].notna() & (df[generic_gtin_col].astype(str).str.strip() != "")].copy()
        if len(generic_df) == 0:
            generic_df = df[df["gtin_status"] == "GENERIC_GTIN"].copy()
    else:
        generic_df = df[df["gtin_status"] == "GENERIC_GTIN"].copy()
    if len(generic_df) == 0:
        return {"total": 0, "unique_gtins": 0, "duplicate_count": 0, "unique_duplicated_gtins": 0, "by_entity": pd.DataFrame(), "duplicate_summary": pd.DataFrame(), "gtin_list": [], "full_df": pd.DataFrame()}
    generic_duplicates = generic_df[generic_df.duplicated(subset=["gtin_outer_normalized"], keep=False)].copy()
    duplicate_count = len(generic_duplicates)
    unique_duplicated_gtins = generic_duplicates["gtin_outer_normalized"].nunique() if duplicate_count > 0 else 0
    by_entity = generic_df.groupby("Legal Entity").agg({"gtin_outer_normalized": ["count", "nunique"]}).reset_index()
    by_entity.columns = ["Legal Entity", "Total Records", "Unique Generic GTINs"]
    by_entity = by_entity.sort_values("Total Records", ascending=False)
    duplicate_summary = []
    if duplicate_count > 0:
        for gtin in generic_duplicates["gtin_outer_normalized"].unique():
            gtin_records = generic_duplicates[generic_duplicates["gtin_outer_normalized"] == gtin]
            duplicate_summary.append({
                "Generic GTIN": gtin,
                "Occurrences": len(gtin_records),
                "Legal Entities": ", ".join(sorted(gtin_records["Legal Entity"].unique().tolist())),
                "Entity Count": len(gtin_records["Legal Entity"].unique()),
            })
        duplicate_summary_df = pd.DataFrame(duplicate_summary).sort_values("Occurrences", ascending=False)
    else:
        duplicate_summary_df = pd.DataFrame()
    return {
        "total": len(generic_df),
        "unique_gtins": generic_df["gtin_outer_normalized"].dropna().nunique(),
        "duplicate_count": duplicate_count,
        "unique_duplicated_gtins": unique_duplicated_gtins,
        "by_entity": by_entity,
        "duplicate_summary": duplicate_summary_df,
        "gtin_list": generic_df["gtin_outer_normalized"].dropna().unique().tolist(),
        "full_df": generic_df,
    }


def analyze_placeholder_gtins(df, gtin_outer_col):
    df = df.copy()
    df["gtin_status"] = df["gtin_outer_normalized"].apply(lambda x: classify_gtin_status(x) if x is not None else "MISSING")
    placeholder_df = df[df["gtin_status"] == "EXPLICIT_BLOCKED"].copy()
    if len(placeholder_df) == 0:
        return {"total": 0, "unique_gtins": 0, "by_entity": pd.DataFrame(), "gtin_list": [], "full_df": pd.DataFrame()}
    by_entity = placeholder_df.groupby("Legal Entity").agg({"gtin_outer_normalized": ["count", "nunique"]}).reset_index()
    by_entity.columns = ["Legal Entity", "Total Records", "Unique Placeholder GTINs"]
    by_entity = by_entity.sort_values("Total Records", ascending=False)
    return {
        "total": len(placeholder_df),
        "unique_gtins": placeholder_df["gtin_outer_normalized"].dropna().nunique(),
        "by_entity": by_entity,
        "gtin_list": placeholder_df["gtin_outer_normalized"].dropna().unique().tolist(),
        "full_df": placeholder_df,
    }


def analyze_suspect_gtins(df, gtin_outer_col):
    df = df.copy()
    df["is_suspect"] = df[gtin_outer_col].apply(is_suspect_gtin)
    df["gtin_status"] = df["gtin_outer_normalized"].apply(lambda x: classify_gtin_status(x) if x is not None else "MISSING")
    suspect_df = df[(df["is_suspect"] == True) & (df["gtin_status"] != "GENERIC_GTIN")].copy()
    if len(suspect_df) == 0:
        return {"total": 0, "unique_gtins": 0, "by_entity": pd.DataFrame(), "gtin_list": [], "full_df": pd.DataFrame()}
    by_entity = suspect_df.groupby("Legal Entity").agg({gtin_outer_col: "count", "gtin_outer_normalized": "nunique"}).reset_index()
    by_entity.columns = ["Legal Entity", "Total Records", "Unique Suspect GTINs"]
    by_entity = by_entity.sort_values("Total Records", ascending=False)
    return {
        "total": len(suspect_df),
        "unique_gtins": suspect_df["gtin_outer_normalized"].nunique(),
        "by_entity": by_entity,
        "gtin_list": suspect_df["gtin_outer_normalized"].unique().tolist(),
        "full_df": suspect_df,
    }


def _same_row_result(same_row_df):
    return {
        "total": len(same_row_df),
        "unique_gtins": same_row_df["gtin_inner_normalized"].nunique() if len(same_row_df) > 0 else 0,
        "df": same_row_df,
        "gtin_list": same_row_df["gtin_inner_normalized"].unique().tolist() if len(same_row_df) > 0 else [],
    }


def analyze_inner_equals_outer(df, gtin_outer_col, gtin_inner_col):
    if not gtin_inner_col or gtin_inner_col not in df.columns or "gtin_inner_normalized" not in df.columns:
        return {
            "same_row": {"total": 0, "unique_gtins": 0, "df": pd.DataFrame(), "gtin_list": []},
            "same_entity": {"total": 0, "unique_gtins": 0, "df": pd.DataFrame(), "gtin_list": []},
            "other_entity": {"total": 0, "unique_gtins": 0, "df": pd.DataFrame(), "gtin_list": []},
            "has_inner": False,
        }
    df = df.copy()
    # Classify only unique GTINs (huge win on 144k+ rows: ~288k -> ~50k-100k unique)
    uniq_outer = df["gtin_outer_normalized"].dropna().unique()
    uniq_inner = df["gtin_inner_normalized"].dropna().unique()
    status_outer = {v: classify_gtin_status(v) for v in uniq_outer}
    status_inner = {v: classify_gtin_status(v) for v in uniq_inner}
    df["_outer_status"] = df["gtin_outer_normalized"].map(status_outer).fillna("MISSING")
    df["_inner_status"] = df["gtin_inner_normalized"].map(status_inner).fillna("MISSING")
    excluded = {"GENERIC_GTIN", "EXPLICIT_BLOCKED"}
    ok_outer = ~df["_outer_status"].isin(excluded) & df["gtin_outer_normalized"].notna()
    ok_inner = ~df["_inner_status"].isin(excluded) & df["gtin_inner_normalized"].notna()
    outer_str = df["gtin_outer_normalized"].astype(str).str.strip()
    inner_str = df["gtin_inner_normalized"].astype(str).str.strip()
    inner_eq_outer_row = (inner_str == outer_str) & outer_str.ne("") & inner_str.ne("")
    same_row_df = df[ok_outer & ok_inner & inner_eq_outer_row].copy()
    same_row_df = same_row_df.drop(columns=["_outer_status", "_inner_status"], errors="ignore")
    ok_rows = df[ok_outer].copy()
    ok_rows["_outer_key"] = ok_rows["gtin_outer_normalized"].astype(str).str.strip()
    # Build entities_by_outer_gtin in one pass (no get_group per key)
    entities_by_outer_gtin = {}
    for k, g in ok_rows.groupby("_outer_key", dropna=False):
        entities_by_outer_gtin[k] = set(g["Legal Entity"].dropna().unique())
    with_inner = df[ok_inner & df["gtin_inner_normalized"].notna() & (inner_str != "") & (~inner_eq_outer_row)].copy()
    with_inner = with_inner.drop(columns=["_outer_status", "_inner_status"], errors="ignore")
    with_inner["_inner_key"] = with_inner["gtin_inner_normalized"].astype(str).str.strip()
    if len(with_inner) == 0:
        return {
            "same_row": _same_row_result(same_row_df),
            "same_entity": {"total": 0, "unique_gtins": 0, "df": pd.DataFrame(), "gtin_list": []},
            "other_entity": {"total": 0, "unique_gtins": 0, "df": pd.DataFrame(), "gtin_list": []},
            "has_inner": True,
        }
    _empty = frozenset()
    get_ent = entities_by_outer_gtin.get
    keys_arr = with_inner["_inner_key"].values
    entities_arr = with_inner["Legal Entity"].values
    buckets = []
    for i in range(len(keys_arr)):
        ent_set = get_ent(keys_arr[i], _empty)
        if not ent_set:
            buckets.append("none")
        elif ent_set == {entities_arr[i]}:
            buckets.append("same_entity")
        else:
            buckets.append("other_entity")
    with_inner["_bucket"] = buckets
    same_entity_df = with_inner[with_inner["_bucket"] == "same_entity"].drop(columns=["_inner_key", "_bucket"], errors="ignore")
    other_entity_df = with_inner[with_inner["_bucket"] == "other_entity"].drop(columns=["_inner_key", "_bucket"], errors="ignore")
    return {
        "same_row": _same_row_result(same_row_df),
        "same_entity": {"total": len(same_entity_df), "unique_gtins": same_entity_df["gtin_inner_normalized"].nunique() if len(same_entity_df) > 0 else 0, "df": same_entity_df, "gtin_list": same_entity_df["gtin_inner_normalized"].unique().tolist() if len(same_entity_df) > 0 else []},
        "other_entity": {"total": len(other_entity_df), "unique_gtins": other_entity_df["gtin_inner_normalized"].nunique() if len(other_entity_df) > 0 else 0, "df": other_entity_df, "gtin_list": other_entity_df["gtin_inner_normalized"].unique().tolist() if len(other_entity_df) > 0 else []},
        "has_inner": True,
    }


def analyze_valid_gtins_by_entity(df, gtin_outer_col):
    df = df.copy()
    df["gtin_status"] = df[gtin_outer_col].apply(classify_gtin_status)
    valid_statuses = ["GTIN_8", "GTIN_13", "GTIN_14"]
    valid_df = df[df["gtin_status"].isin(valid_statuses)].copy()
    if len(valid_df) == 0:
        return {"total": 0, "unique_gtins": 0, "shared_gtins": pd.DataFrame(), "sharing_details": pd.DataFrame(), "entity_sharing": pd.DataFrame(), "full_df": valid_df}
    gtin_entity_counts = valid_df.groupby("gtin_outer_normalized")["Legal Entity"].nunique().reset_index()
    gtin_entity_counts.columns = ["GTIN", "Entity Count"]
    shared_gtins = gtin_entity_counts[gtin_entity_counts["Entity Count"] > 1].sort_values("Entity Count", ascending=False)
    sharing_details = []
    for gtin in shared_gtins["GTIN"].head(100):
        entities = valid_df[valid_df["gtin_outer_normalized"] == gtin]["Legal Entity"].unique().tolist()
        sharing_details.append({"GTIN": gtin, "Entity Count": len(entities), "Legal Entities": ", ".join(sorted(entities))})
    sharing_df = pd.DataFrame(sharing_details) if sharing_details else pd.DataFrame()
    entity_list = sorted(valid_df["Legal Entity"].unique())
    entity_sharing = []
    for i, entity1 in enumerate(entity_list):
        for entity2 in entity_list[i + 1 :]:
            gtins1 = set(valid_df[valid_df["Legal Entity"] == entity1]["gtin_outer_normalized"].unique())
            gtins2 = set(valid_df[valid_df["Legal Entity"] == entity2]["gtin_outer_normalized"].unique())
            shared_count = len(gtins1.intersection(gtins2))
            if shared_count > 0:
                entity_sharing.append({"Entity 1": entity1, "Entity 2": entity2, "Shared GTINs": shared_count})
    entity_sharing_df = pd.DataFrame(entity_sharing).sort_values("Shared GTINs", ascending=False) if entity_sharing else pd.DataFrame()
    return {
        "total": len(valid_df),
        "unique_gtins": valid_df["gtin_outer_normalized"].nunique(),
        "shared_gtins": shared_gtins,
        "sharing_details": sharing_df,
        "entity_sharing": entity_sharing_df,
        "full_df": valid_df,
    }


OUTPUTS_BASE = "outputs"
OUTPUT_MANIFEST = "manifest.json"
OUTPUT_OVERVIEW = "overview.json"

# Quality Dashboard: map gtin_analysis status to Quality page status
_QUALITY_STATUS_MAP = {
    "MISSING": "INVALID", "NON_NUMERIC": "INVALID", "INVALID_LENGTH": "INVALID", "SUSPECT": "INVALID",
    "EXPLICIT_BLOCKED": "PLACEHOLDER", "GENERIC_GTIN": "GENERIC",
    "GTIN_8": "8_digits", "GTIN_13": "13_digits", "GTIN_14": "14_digits",
}


def _classify_gtin_quality(gtin_raw):
    """Classify for Quality Dashboard: INVALID, GENERIC, PLACEHOLDER, 8_digits, 13_digits, 14_digits."""
    return _QUALITY_STATUS_MAP.get(classify_gtin_status(gtin_raw), "INVALID")


# Generic GTIN Analysis: taxonomy mapping (same as page 5)
GENERIC_GTIN_TAXONOMY = {
    "10000000000009": {"lov": "Butchery", "business_centres": ["BEEF", "PORK", "POULTRY"]},
    "30000000000009": {"lov": "Equipment", "business_centres": ["SUPPLIES & EQUIPMENT"]},
    "40000000000009": {"lov": "Fishmongery", "business_centres": ["SEAFOOD"]},
    "70000000000009": {"lov": "Produce", "business_centres": ["PRODUCE"]},
    "20000000000009": {"lov": "Not in MDD", "business_centres": []},
    "50000000000009": {"lov": "Not in MDD", "business_centres": []},
    "60000000000009": {"lov": "Not in MDD", "business_centres": []},
    "80000000000009": {"lov": "Not in MDD", "business_centres": []},
}
EXPECTED_GTIN_BY_TAXONOMY = {}
for _gtin14, _info in GENERIC_GTIN_TAXONOMY.items():
    for _bc in _info["business_centres"]:
        EXPECTED_GTIN_BY_TAXONOMY[_bc.upper()] = _gtin14


def _gtin_to_14(gtin):
    if not gtin or not str(gtin).isdigit():
        return gtin or ""
    s = str(gtin).strip()
    if len(s) == 13:
        return "0" + s
    return s if len(s) == 14 else s


def run_quality_analysis(df, gtin_outer_col, output_dir: str):
    """Run Quality Dashboard logic (all legal entities). Write quality_*.xlsx and quality_overview.json."""
    df = df.copy()
    df["gtin_status"] = df["gtin_outer_normalized"].apply(_classify_gtin_quality)
    valid_statuses = ["8_digits", "13_digits", "14_digits"]
    total_valid = df[df["gtin_status"].isin(valid_statuses)].shape[0]
    total_invalid = df[df["gtin_status"] == "INVALID"].shape[0]
    total_generic = df[df["gtin_status"] == "GENERIC"].shape[0]
    total_blocked = df[df["gtin_status"].isin(["PLACEHOLDER", "BLOCKED"])].shape[0]
    total_rows = len(df)
    compliance_rate = (total_valid / total_rows * 100) if total_rows > 0 else 0
    legal_entities = sorted(df["Legal Entity"].dropna().unique().tolist())
    entity_counts = df.groupby("Legal Entity").size().to_dict()

    analysis_data = []
    for entity in legal_entities:
        entity_df = df[df["Legal Entity"] == entity]
        total = len(entity_df)
        status_counts = entity_df["gtin_status"].value_counts().to_dict()
        valid_count = sum(status_counts.get(s, 0) for s in valid_statuses)
        invalid_count = status_counts.get("INVALID", 0)
        generic_count = status_counts.get("GENERIC", 0)
        blocked_count = status_counts.get("PLACEHOLDER", 0) + status_counts.get("BLOCKED", 0)
        compliance = (valid_count / total * 100) if total > 0 else 0
        analysis_data.append({
            "Legal Entity": entity,
            "Total Products": total,
            "Valid GTINs": valid_count,
            "Invalid GTINs": invalid_count,
            "Generic GTINs": generic_count,
            "Placeholder GTINs (999...99)": blocked_count,
            "Compliance Rate (%)": round(compliance, 2),
            "8 digits": status_counts.get("8_digits", 0),
            "13 digits": status_counts.get("13_digits", 0),
            "14 digits": status_counts.get("14_digits", 0),
        })
    quality_by_entity = pd.DataFrame(analysis_data)
    quality_by_entity.to_excel(os.path.join(output_dir, "quality_by_entity.xlsx"), index=False)
    df.to_excel(os.path.join(output_dir, "quality_full_classified.xlsx"), index=False)

    brand_col = next((c for c in df.columns if str(c).strip().lower() == "brand"), None)
    if brand_col:
        generics_df = df[df["gtin_status"] == "GENERIC"].copy()
        is_not_eupcker = generics_df[brand_col].fillna("").astype(str).str.strip().str.upper() != "EUPCKER"
        generics_non_eupcker = generics_df[is_not_eupcker]
        if len(generics_non_eupcker) > 0:
            pc = [c for c in ["Legal Entity", "SUPC", "Local Product Description", brand_col, "OSD Classification", "gtin_outer_normalized"] if c in generics_non_eupcker.columns]
            if pc:
                generics_non_eupcker[pc].to_excel(os.path.join(output_dir, "generics_non_eupcker.xlsx"), index=False)
    quality_overview = {
        "total_rows": total_rows,
        "legal_entities": legal_entities,
        "entity_total_products": entity_counts,
        "total_valid": total_valid,
        "total_invalid": total_invalid,
        "total_generic": total_generic,
        "total_placeholder": total_blocked,
        "compliance_rate": round(compliance_rate, 2),
    }
    with open(os.path.join(output_dir, "quality_overview.json"), "w", encoding="utf-8") as f:
        json.dump(quality_overview, f, indent=2)


def run_generic_analysis(df, gtin_outer_col, output_dir: str):
    """Run Generic GTIN conformity analysis (all legal entities). Write generic_*.xlsx and generic_overview.json."""
    df = df.copy()
    df["gtin_status_gen"] = df["gtin_outer_normalized"].apply(_classify_gtin_quality)
    generic_df = df[df["gtin_status_gen"] == "GENERIC"].copy()
    if len(generic_df) == 0:
        with open(os.path.join(output_dir, "generic_overview.json"), "w", encoding="utf-8") as f:
            json.dump({"total": 0, "legal_entities": [], "conforming_count": 0, "non_conforming_count": 0}, f, indent=2)
        return
    osd_col = next((c for c in df.columns if str(c).strip().upper() == "OSD CLASSIFICATION"), None)
    if osd_col is not None:
        generic_df["osd_prefix"] = generic_df[osd_col].fillna("").astype(str).str.strip().str.split("-").str[0].str.strip()
    else:
        generic_df["osd_prefix"] = ""
    generic_df["gtin_14"] = generic_df["gtin_outer_normalized"].apply(_gtin_to_14)
    generic_df["expected_gtin"] = generic_df["osd_prefix"].apply(
        lambda x: EXPECTED_GTIN_BY_TAXONOMY.get(str(x).strip().upper()) if pd.notna(x) and str(x).strip() else None
    )
    generic_df["conforming"] = generic_df["expected_gtin"].notna() & (generic_df["gtin_14"] == generic_df["expected_gtin"])
    conforming_count = generic_df["conforming"].sum()
    non_conforming_count = len(generic_df) - conforming_count
    by_ent = generic_df.groupby("Legal Entity").agg(total=("gtin_14", "count"), conforming=("conforming", "sum")).reset_index()
    by_ent["non_conforming"] = by_ent["total"] - by_ent["conforming"]
    by_ent["conforming_%"] = (by_ent["conforming"] / by_ent["total"] * 100).round(1)
    by_ent = by_ent.sort_values("non_conforming", ascending=False)
    by_ent.to_excel(os.path.join(output_dir, "generic_conformity_by_entity.xlsx"), index=False)
    non_conforming_df = generic_df[~generic_df["conforming"]].copy()
    if len(non_conforming_df) > 0:
        display_nc = non_conforming_df[["Legal Entity", "osd_prefix", "gtin_14", "expected_gtin"]].copy()
        display_nc.columns = ["Legal Entity", "OSD prefix (taxonomy)", "Generic used", "Expected Generic"]
        display_nc.to_excel(os.path.join(output_dir, "generic_non_conforming.xlsx"), index=False)
    sample_cols = [c for c in ["Legal Entity", "osd_prefix", "gtin_14", "expected_gtin", "conforming", "SUPC", "Local Product Description"] if c in generic_df.columns]
    if sample_cols:
        generic_df[sample_cols].to_excel(os.path.join(output_dir, "generic_all_records_with_conformity.xlsx"), index=False)
    generic_overview = {
        "total": len(generic_df),
        "conforming_count": int(conforming_count),
        "non_conforming_count": int(non_conforming_count),
        "legal_entities": sorted(generic_df["Legal Entity"].dropna().unique().tolist()),
    }
    with open(os.path.join(output_dir, "generic_overview.json"), "w", encoding="utf-8") as f:
        json.dump(generic_overview, f, indent=2)


def run_generate_email_reports(df, gtin_outer_col, output_dir: str):
    """Generate one Excel report per legal entity (Summary + Generic + Placeholder sheets). All entities only."""
    df = df.copy()
    df["gtin_status"] = df["gtin_outer_normalized"].apply(_classify_gtin_quality)
    email_dir = os.path.join(output_dir, "email_reports")
    Path(email_dir).mkdir(parents=True, exist_ok=True)
    legal_entities = sorted(df["Legal Entity"].dropna().unique().tolist())
    for entity in legal_entities:
        entity_data = df[df["Legal Entity"] == entity].copy()
        generic_blocked = entity_data[entity_data["gtin_status"].isin(["GENERIC", "PLACEHOLDER", "BLOCKED"])].copy()
        generic_gtins = generic_blocked[generic_blocked["gtin_status"] == "GENERIC"].copy()
        blocked_gtins = generic_blocked[generic_blocked["gtin_status"].isin(["PLACEHOLDER", "BLOCKED"])].copy()
        generic_count = len(generic_gtins)
        blocked_count = len(blocked_gtins)
        total_count = len(generic_blocked)
        safe_name = entity.replace(" ", "_").replace("/", "_")
        path = os.path.join(email_dir, f"{safe_name}.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame({
                "Legal Entity": [entity],
                "Total Generic GTINs": [generic_count],
                "Total Placeholder GTINs (999...99)": [blocked_count],
                "Total to Review": [total_count],
                "Report Date": [datetime.now().strftime("%Y-%m-%d")],
            }).to_excel(writer, sheet_name="Summary", index=False)
            if len(generic_gtins) > 0:
                generic_gtins.to_excel(writer, sheet_name="Generic GTINs", index=False)
            if len(blocked_gtins) > 0:
                blocked_gtins.to_excel(writer, sheet_name="Placeholder GTINs (999...99)", index=False)
    email_overview = {"legal_entities": legal_entities, "report_count": len(legal_entities)}
    with open(os.path.join(output_dir, "email_overview.json"), "w", encoding="utf-8") as f:
        json.dump(email_overview, f, indent=2)


def run_full_analysis(input_excel_path: str, output_dir: str = None, extract_date: str = None) -> str:
    """
    Load data from input_excel_path, run all duplicate analyses, write results to output_dir.
    output_dir defaults to outputs/YYYY-MM-DD (extract_date or today).
    Returns the path to the created output directory.
    """
    result = load_duplicate_data_from_path(input_excel_path)
    if result[0] is None:
        raise ValueError(f"Failed to load data from {input_excel_path} (check file and GTIN-Outer column).")
    df, gtin_outer_col, gtin_inner_col, generic_gtin_col = result
    total_rows = len(df)

    if extract_date:
        out_date = extract_date
    else:
        out_date = datetime.now().strftime("%Y-%m-%d")
    if output_dir is None:
        output_dir = os.path.join(OUTPUTS_BASE, out_date)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print("Running duplicate analysis...")
    duplicate_results = analyze_duplicates(df, gtin_outer_col, gtin_inner_col)
    print("Running generic GTINs analysis...")
    generic_results = analyze_generic_gtins(df, gtin_outer_col, generic_gtin_col)
    print("Running placeholder GTINs analysis...")
    placeholder_results = analyze_placeholder_gtins(df, gtin_outer_col)
    print("Running suspect GTINs analysis...")
    suspect_results = analyze_suspect_gtins(df, gtin_outer_col)
    print("Running valid GTINs by entity...")
    valid_results = analyze_valid_gtins_by_entity(df, gtin_outer_col)
    print("Running Inner = Outer analysis...")
    inner_eq_outer_results = analyze_inner_equals_outer(df, gtin_outer_col, gtin_inner_col)

    legal_entities = sorted(df["Legal Entity"].dropna().unique().tolist())
    entity_counts = df.groupby("Legal Entity").size().to_dict()
    # Overview for Streamlit
    overview = {
        "source_file": os.path.basename(input_excel_path),
        "extract_date": out_date,
        "total_rows": total_rows,
        "filtered_rows": total_rows,
        "legal_entities": legal_entities,
        "entity_total_products": entity_counts,
        "outer_duplicates": duplicate_results["outer"]["total_duplicates"],
        "outer_unique_duplicated": duplicate_results["outer"]["unique_duplicated_gtins"],
        "inner_duplicates": duplicate_results["inner"]["total_duplicates"] if duplicate_results["inner"] else 0,
        "inner_unique_duplicated": duplicate_results["inner"]["unique_duplicated_gtins"] if duplicate_results["inner"] else 0,
        "cross_unique_gtins": duplicate_results["cross"]["unique_cross_gtins"] if duplicate_results["cross"] else 0,
        "cross_total_records": duplicate_results["cross"]["total_records"] if duplicate_results["cross"] else 0,
        "generic_total": generic_results["total"],
        "generic_unique": generic_results["unique_gtins"],
        "placeholder_total": placeholder_results["total"],
        "placeholder_unique": placeholder_results["unique_gtins"],
        "suspect_total": suspect_results["total"],
        "suspect_unique": suspect_results["unique_gtins"],
        "valid_total": valid_results["total"],
        "valid_unique": valid_results["unique_gtins"],
        "same_row_total": inner_eq_outer_results["same_row"]["total"],
        "inner_eq_outer_same_entity_total": inner_eq_outer_results["same_entity"]["total"],
        "inner_eq_outer_other_entity_total": inner_eq_outer_results["other_entity"]["total"],
    }
    with open(os.path.join(output_dir, OUTPUT_OVERVIEW), "w", encoding="utf-8") as f:
        json.dump(overview, f, indent=2)
    manifest = {
        "source_file": os.path.basename(input_excel_path),
        "extract_date": out_date,
        "total_rows": total_rows,
        "gtin_outer_col": gtin_outer_col,
        "gtin_inner_col": gtin_inner_col,
        "generic_gtin_col": generic_gtin_col,
    }
    with open(os.path.join(output_dir, OUTPUT_MANIFEST), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Excel outputs
    def write_excel(name, data_bytes):
        path = os.path.join(output_dir, name)
        with open(path, "wb") as f:
            f.write(data_bytes)

    if duplicate_results["cross"] and len(duplicate_results["cross"]["cross_df"]) > 0:
        write_excel("cross_duplicates.xlsx", to_excel_bytes(duplicate_results["cross"]["cross_df"]))
    duplicate_results["outer"]["duplicate_df"].to_excel(os.path.join(output_dir, "outer_duplicates.xlsx"), index=False)
    if duplicate_results.get("inner"):
        duplicate_results["inner"]["duplicate_df"].to_excel(os.path.join(output_dir, "inner_duplicates.xlsx"), index=False)
    generic_results["by_entity"].to_excel(os.path.join(output_dir, "generic_by_entity.xlsx"), index=False)
    ds = generic_results.get("duplicate_summary", pd.DataFrame())
    if ds is not None and len(ds) > 0:
        generic_results["duplicate_summary"].to_excel(os.path.join(output_dir, "generic_duplicate_summary.xlsx"), index=False)
    placeholder_results["by_entity"].to_excel(os.path.join(output_dir, "placeholder_by_entity.xlsx"), index=False)
    suspect_results["by_entity"].to_excel(os.path.join(output_dir, "suspect_by_entity.xlsx"), index=False)
    valid_results["shared_gtins"].to_excel(os.path.join(output_dir, "valid_shared_gtins.xlsx"), index=False)
    valid_results["entity_sharing"].to_excel(os.path.join(output_dir, "valid_entity_sharing.xlsx"), index=False)
    if len(valid_results["sharing_details"]) > 0:
        valid_results["sharing_details"].to_excel(os.path.join(output_dir, "valid_sharing_details.xlsx"), index=False)

    inner_eq_outer_results["same_row"]["df"].to_excel(os.path.join(output_dir, "outer_eq_inner_same_row.xlsx"), index=False)
    same_entity_df = inner_eq_outer_results["same_entity"]["df"]
    other_entity_df = inner_eq_outer_results["other_entity"]["df"]
    if len(same_entity_df) > 0:
        write_excel("inner_eq_outer_same_entity.xlsx", to_excel_bytes_inner_outer_paired(same_entity_df, df, same_entity=True))
    if len(other_entity_df) > 0:
        write_excel("inner_eq_outer_other_entity.xlsx", to_excel_bytes_inner_outer_paired(other_entity_df, df, same_entity=False))

    print("Running Quality Dashboard analysis...")
    run_quality_analysis(df, gtin_outer_col, output_dir)
    print("Running Generic GTIN analysis...")
    run_generic_analysis(df, gtin_outer_col, output_dir)
    print("Running Generate Email reports (one per Legal Entity)...")
    run_generate_email_reports(df, gtin_outer_col, output_dir)

    print(f"Done. Outputs written to {output_dir}")
    return output_dir


def list_output_dates(base_dir: str = None) -> list:
    """List available output dates (subdirs of outputs/). Returns sorted list of (date_str, path)."""
    base = base_dir or OUTPUTS_BASE
    if not os.path.isdir(base):
        return []
    out = []
    for name in os.listdir(base):
        path = os.path.join(base, name)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, OUTPUT_OVERVIEW)):
            out.append((name, path))
    return sorted(out, key=lambda x: x[0], reverse=True)


def load_overview(output_dir: str) -> dict:
    """Load overview.json from an output directory."""
    path = os.path.join(output_dir, OUTPUT_OVERVIEW)
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_manifest(output_dir: str) -> dict:
    """Load manifest.json from an output directory."""
    path = os.path.join(output_dir, OUTPUT_MANIFEST)
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_output_results(output_dir: str, selected_entities: list = None):
    """
    Load pre-computed results from output_dir and optionally filter by selected_entities.
    Returns (overview, manifest, duplicate_results, generic_results, placeholder_results,
             suspect_results, valid_results, inner_eq_outer_results) for Streamlit.
    """
    overview = load_overview(output_dir)
    manifest = load_manifest(output_dir)
    if not overview:
        return None
    legal = overview.get("legal_entities", [])
    entities = selected_entities if selected_entities else legal
    total_rows = overview.get("total_rows", 0)

    def _filter(df):
        if df is None or df.empty:
            return df
        if "Legal Entity" in df.columns and entities:
            return df[df["Legal Entity"].isin(entities)].copy()
        return df

    def _read(path):
        p = os.path.join(output_dir, path)
        if not os.path.isfile(p):
            return pd.DataFrame()
        return pd.read_excel(p, dtype=str)

    gtin_outer_col = manifest.get("gtin_outer_col", "GTIN-Outer")
    gtin_inner_col = manifest.get("gtin_inner_col") or ("GTIN-Inner" if os.path.isfile(os.path.join(output_dir, "inner_duplicates.xlsx")) else None)

    # Duplicate results
    cross_df = _filter(_read("cross_duplicates.xlsx"))
    outer_df = _filter(_read("outer_duplicates.xlsx"))
    inner_df = _filter(_read("inner_duplicates.xlsx")) if gtin_inner_col else pd.DataFrame()
    duplicate_results = {
        "outer": {
            "total_duplicates": len(outer_df),
            "unique_duplicated_gtins": outer_df["gtin_outer_normalized"].nunique() if len(outer_df) > 0 and "gtin_outer_normalized" in outer_df.columns else 0,
            "duplicate_df": outer_df,
        },
        "inner": {
            "total_duplicates": len(inner_df),
            "unique_duplicated_gtins": inner_df["gtin_inner_normalized"].nunique() if len(inner_df) > 0 and "gtin_inner_normalized" in inner_df.columns else 0,
            "duplicate_df": inner_df,
        } if gtin_inner_col else None,
        "cross": {
            "unique_cross_gtins": overview.get("cross_unique_gtins", 0) if not entities or entities == legal else cross_df["gtin_outer_normalized"].nunique() if "gtin_outer_normalized" in cross_df.columns else 0,
            "total_records": len(cross_df),
            "cross_df": cross_df,
            "gtin_list": cross_df["gtin_outer_normalized"].dropna().unique().tolist() if len(cross_df) > 0 and "gtin_outer_normalized" in cross_df.columns else [],
        } if gtin_inner_col else None,
    }
    if duplicate_results["cross"] and entities != legal:
        duplicate_results["cross"]["unique_cross_gtins"] = cross_df["gtin_outer_normalized"].nunique() if len(cross_df) > 0 and "gtin_outer_normalized" in cross_df.columns else 0

    # Generic, placeholder, suspect (by_entity tables)
    generic_by = _filter(_read("generic_by_entity.xlsx"))
    generic_results = {
        "total": generic_by["Total Records"].astype(int).sum() if len(generic_by) > 0 else 0,
        "unique_gtins": generic_by["Unique Generic GTINs"].astype(int).sum() if len(generic_by) > 0 and "Unique Generic GTINs" in generic_by.columns else 0,
        "duplicate_count": overview.get("generic_total", 0) if entities == legal else generic_by["Total Records"].astype(int).sum(),
        "unique_duplicated_gtins": overview.get("generic_unique", 0) if entities == legal else (generic_by["Unique Generic GTINs"].astype(int).sum() if "Unique Generic GTINs" in generic_by.columns else 0),
        "by_entity": generic_by,
        "duplicate_summary": _read("generic_duplicate_summary.xlsx"),
        "full_df": pd.DataFrame(),
    }
    placeholder_by = _filter(_read("placeholder_by_entity.xlsx"))
    placeholder_results = {
        "total": placeholder_by["Total Records"].astype(int).sum() if len(placeholder_by) > 0 else 0,
        "unique_gtins": placeholder_by["Unique Placeholder GTINs"].astype(int).sum() if len(placeholder_by) > 0 and "Unique Placeholder GTINs" in placeholder_by.columns else 0,
        "by_entity": placeholder_by,
        "gtin_list": [],
        "full_df": pd.DataFrame(),
    }
    suspect_by = _filter(_read("suspect_by_entity.xlsx"))
    suspect_results = {
        "total": suspect_by["Total Records"].astype(int).sum() if len(suspect_by) > 0 else 0,
        "unique_gtins": suspect_by["Unique Suspect GTINs"].astype(int).sum() if len(suspect_by) > 0 and "Unique Suspect GTINs" in suspect_by.columns else 0,
        "by_entity": suspect_by,
        "gtin_list": [],
        "full_df": pd.DataFrame(),
    }
    valid_shared = _read("valid_shared_gtins.xlsx")
    valid_entity = _read("valid_entity_sharing.xlsx")
    valid_details = _read("valid_sharing_details.xlsx")
    valid_results = {
        "total": overview.get("valid_total", 0),
        "unique_gtins": overview.get("valid_unique", 0),
        "shared_gtins": valid_shared,
        "sharing_details": valid_details,
        "entity_sharing": valid_entity,
        "full_df": pd.DataFrame(),
    }
    same_row_df = _filter(_read("outer_eq_inner_same_row.xlsx"))
    same_entity_df = _filter(_read("inner_eq_outer_same_entity.xlsx"))
    other_entity_df = _filter(_read("inner_eq_outer_other_entity.xlsx"))
    inner_eq_outer_results = {
        "same_row": {"total": len(same_row_df), "unique_gtins": same_row_df["gtin_inner_normalized"].nunique() if len(same_row_df) > 0 and "gtin_inner_normalized" in same_row_df.columns else 0, "df": same_row_df, "gtin_list": []},
        "same_entity": {"total": len(same_entity_df), "unique_gtins": same_entity_df["gtin_inner_normalized"].nunique() if len(same_entity_df) > 0 and "gtin_inner_normalized" in same_entity_df.columns else 0, "df": same_entity_df, "gtin_list": []},
        "other_entity": {"total": len(other_entity_df), "unique_gtins": other_entity_df["gtin_inner_normalized"].nunique() if len(other_entity_df) > 0 and "gtin_inner_normalized" in other_entity_df.columns else 0, "df": other_entity_df, "gtin_list": []},
        "has_inner": gtin_inner_col is not None,
    }

    return overview, manifest, duplicate_results, generic_results, placeholder_results, suspect_results, valid_results, inner_eq_outer_results, total_rows, gtin_outer_col, gtin_inner_col


def load_quality_results(output_dir: str):
    """
    Load Quality Dashboard pre-computed results (all legal entities). Streamlit page filters by selected_entities in memory.
    Returns dict: overview, by_entity_df, full_classified_df, generics_non_eupcker_df, legal_entities, total_rows, gtin_outer_col.
    """
    overview_path = os.path.join(output_dir, "quality_overview.json")
    if not os.path.isfile(overview_path):
        return None
    with open(overview_path, "r", encoding="utf-8") as f:
        overview = json.load(f)
    legal_entities = overview.get("legal_entities", [])

    def _read(path):
        p = os.path.join(output_dir, path)
        if not os.path.isfile(p):
            return pd.DataFrame()
        return pd.read_excel(p, dtype=str)

    by_entity_df = _read("quality_by_entity.xlsx")
    full_classified_df = _read("quality_full_classified.xlsx")
    generics_non_eupcker_df = _read("generics_non_eupcker.xlsx")
    manifest = load_manifest(output_dir)
    gtin_outer_col = manifest.get("gtin_outer_col", "GTIN-Outer")
    total_rows = overview.get("total_rows", 0)
    return {
        "overview": overview,
        "by_entity_df": by_entity_df,
        "full_classified_df": full_classified_df,
        "generics_non_eupcker_df": generics_non_eupcker_df,
        "legal_entities": legal_entities,
        "total_rows": total_rows,
        "gtin_outer_col": gtin_outer_col,
    }


def load_generic_results(output_dir: str):
    """
    Load Generic GTIN pre-computed results (all legal entities). Streamlit page filters by selected_entities in memory.
    Returns dict: overview, by_entity_df, non_conforming_df, all_records_df, legal_entities, gtin_outer_col.
    """
    overview_path = os.path.join(output_dir, "generic_overview.json")
    if not os.path.isfile(overview_path):
        return None
    with open(overview_path, "r", encoding="utf-8") as f:
        overview = json.load(f)
    legal_entities = overview.get("legal_entities", [])

    def _read(path):
        p = os.path.join(output_dir, path)
        if not os.path.isfile(p):
            return pd.DataFrame()
        return pd.read_excel(p, dtype=str)

    by_entity_df = _read("generic_conformity_by_entity.xlsx")
    non_conforming_df = _read("generic_non_conforming.xlsx")
    all_records_df = _read("generic_all_records_with_conformity.xlsx")
    manifest = load_manifest(output_dir)
    gtin_outer_col = manifest.get("gtin_outer_col", "GTIN-Outer")
    return {
        "overview": overview,
        "by_entity_df": by_entity_df,
        "non_conforming_df": non_conforming_df,
        "all_records_df": all_records_df,
        "legal_entities": legal_entities,
        "gtin_outer_col": gtin_outer_col,
    }


def list_email_reports(output_dir: str):
    """List available email report Excel files (one per Legal Entity). Returns list of (entity_name, file_path)."""
    overview_path = os.path.join(output_dir, "email_overview.json")
    email_dir = os.path.join(output_dir, "email_reports")
    if not os.path.isdir(email_dir):
        return []
    entities = []
    if os.path.isfile(overview_path):
        with open(overview_path, "r", encoding="utf-8") as f:
            entities = json.load(f).get("legal_entities", [])
    out = []
    for entity in entities:
        safe_name = entity.replace(" ", "_").replace("/", "_") + ".xlsx"
        path = os.path.join(email_dir, safe_name)
        if os.path.isfile(path):
            out.append((entity, path))
    if not out:
        for name in os.listdir(email_dir):
            if name.endswith(".xlsx"):
                path = os.path.join(email_dir, name)
                entity_name = name.replace(".xlsx", "").replace("_", " ")
                out.append((entity_name, path))
    return sorted(out, key=lambda x: x[0])

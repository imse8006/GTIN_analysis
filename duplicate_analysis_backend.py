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
    df["_outer_status"] = df["gtin_outer_normalized"].apply(lambda x: classify_gtin_status(x) if x is not None else "MISSING")
    df["_inner_status"] = df["gtin_inner_normalized"].apply(lambda x: classify_gtin_status(x) if x is not None else "MISSING")
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
    entities_by_outer_gtin = ok_rows.groupby("_outer_key")["Legal Entity"].apply(lambda s: set(s.dropna().unique())).to_dict()
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

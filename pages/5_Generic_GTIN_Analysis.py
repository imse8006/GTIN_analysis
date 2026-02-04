"""
Generic GTIN Analysis page: check if Generic GTINs CORRESPOND to the taxonomy.
Taxonomy = first part of "OSD Classification" (before first dash), e.g. "BEEF" from "BEEF-YYYY-ZZZZ".
Compare product's Generic GTIN to the expected Generic for that taxonomy (mapping).
Only analyzes Generic GTINs with business_centres mapping: 10000000000009, 30000000000009, 40000000000009, 70000000000009.
Data loaded from pre-computed outputs/ (run batch first).
"""
import os
import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path
import sys

st.set_page_config(
    page_title="Generic GTIN Analysis",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

sys.path.append(str(Path(__file__).parent.parent))
from export_utils import to_excel_bytes
from auth_utils import render_login_form
from duplicate_analysis_backend import list_output_dates, load_generic_results, load_manifest, OUTPUTS_BASE, load_duplicate_data_from_path


@st.cache_data(ttl=3600)
def _cached_load_generic_results(output_dir: str):
    """Cache Generic GTIN results (avoids re-reading Excel on every rerun)."""
    return load_generic_results(output_dir)

@st.cache_data(ttl=3600)
def _cached_load_source_file(file_path: str):
    """Cache source file loading (avoids re-reading Excel on every rerun)."""
    result = load_duplicate_data_from_path(file_path)
    if result[0] is None:
        return None, None, None
    df, gtin_outer_col, _, _ = result
    return df, gtin_outer_col, file_path

# Generic GTIN set (same as other pages)
GENERIC_GTINS = {
    "10000000000009", "20000000000009", "30000000000009", "40000000000009",
    "50000000000009", "60000000000009", "70000000000009", "80000000000009",
}
EXPLICIT_BLOCKED = "99999999999999"
VALID_LENGTHS = {8, 13, 14}

# Mapping: Generic GTIN (14 digits) -> LOV + Business Centres (taxonomy). From MDD.
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

# Generic GTINs with business_centres mapping (only these will be analyzed)
GENERIC_GTINS_WITH_MAPPING = {
    gtin for gtin, info in GENERIC_GTIN_TAXONOMY.items() 
    if info["business_centres"]  # Only GTINs with non-empty business_centres
}

# Expected Generic GTIN per taxonomy (OSD prefix = part before first dash in "OSD Classification")
# Keys normalized to uppercase for lookup (OSD can be "BEEF" or "Beef")
EXPECTED_GTIN_BY_TAXONOMY = {}
for gtin_14, info in GENERIC_GTIN_TAXONOMY.items():
    for bc in info["business_centres"]:
        EXPECTED_GTIN_BY_TAXONOMY[bc.upper()] = gtin_14

# Target taxonomies to analyze (filter products on these taxonomies only)
TARGET_TAXONOMIES = {"BEEF", "PORK", "POULTRY", "SUPPLIES & EQUIPMENT", "SEAFOOD", "PRODUCE"}

# Reverse mapping: Generic GTIN -> Expected OSD Taxonomy (for display)
EXPECTED_OSD_BY_GTIN = {}
for gtin_14, info in GENERIC_GTIN_TAXONOMY.items():
    if info["business_centres"]:
        # Join multiple taxonomies with comma if multiple
        EXPECTED_OSD_BY_GTIN[gtin_14] = ", ".join(info["business_centres"])


def normalize_gtin(value):
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


def gtin_to_14(gtin: str) -> str:
    """Normalize GTIN to 14 digits for taxonomy lookup (pad with leading zero if 13)."""
    if not gtin or not gtin.isdigit():
        return gtin or ""
    if len(gtin) == 13:
        return "0" + gtin
    return gtin if len(gtin) == 14 else gtin


def has_valid_gs1_check_digit(gtin: str, length: int) -> bool:
    if length == 8:
        return True
    if length not in (13, 14) or not gtin.isdigit():
        return False
    digits = [int(d) for d in gtin]
    body, check_digit = digits[:-1], digits[-1]
    total = 0
    for i, d in enumerate(reversed(body), start=1):
        multiplier = 1 if (length == 13 and i % 2 == 1) or (length == 14 and i % 2 == 0) else 3
        total += d * multiplier
    calc = (10 - (total % 10)) % 10
    return calc == check_digit


def classify_gtin_status_full(gtin_raw):
    if pd.isna(gtin_raw) or gtin_raw is None:
        return "INVALID"
    gtin = normalize_gtin(gtin_raw)
    if gtin is None:
        return "INVALID"
    if gtin == EXPLICIT_BLOCKED:
        return "PLACEHOLDER"
    if gtin in GENERIC_GTINS:
        return "GENERIC"
    if not gtin.isdigit():
        return "INVALID"
    length = len(gtin)
    if length not in VALID_LENGTHS:
        return "INVALID"
    if not has_valid_gs1_check_digit(gtin, length):
        return "INVALID"
    if length == 8:
        return "8_digits"
    elif length == 13:
        return "13_digits"
    else:
        return "14_digits"


def check_password():
    return render_login_form("Generic GTIN Analysis", password_key="password_gen_gtin")


st.markdown("""
    <style>
    .main-header { font-size: 3rem; font-weight: 700; color: #94a3b8; text-align: center; margin-bottom: 1rem; padding: 1rem 0; }
    .section-header { font-size: 1.5rem; font-weight: 600; color: #94a3b8; margin-top: 2rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #475569; }
    .filter-section { background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; margin-bottom: 2rem; border: 1px solid #334155; }
    .stMetric { background-color: #1e293b; padding: 1.5rem; border-radius: 0.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.3); border: 1px solid #334155; min-height: 8rem; }
    .stApp { background-color: #0f172a; }
    </style>
""", unsafe_allow_html=True)


def main():
    if not check_password():
        return

    output_dates = list_output_dates()
    if not output_dates:
        st.info(f"No pre-computed results. Run the batch then reload. Results in `{OUTPUTS_BASE}/YYYY-MM-DD/`.")
        return

    date_options = [f"{d[0]} ({d[1]})" for d in output_dates]
    date_paths = {date_options[i]: output_dates[i][1] for i in range(len(output_dates))}
    selected_date_label = st.selectbox("**Extract date**", date_options, index=0, key="gen_gtin_date")
    output_dir = date_paths[selected_date_label]

    # Load manifest to get source file path
    manifest = load_manifest(output_dir)
    source_file = manifest.get("source_file", "")
    if not source_file:
        st.error("Source file not found in manifest. Cannot load original data.")
        return
    
    # Resolve source file path (could be relative or absolute)
    # Try multiple possible locations - same logic as other pages
    source_file_resolved = None
    
    # Normalize output_dir to absolute path first
    output_dir_path = Path(output_dir).resolve()
    # Get the project root (parent of outputs/)
    project_root = output_dir_path.parent.parent
    
    # Debug: print paths to understand the issue (can be removed later)
    # st.write(f"Debug: output_dir={output_dir}, output_dir_path={output_dir_path}, project_root={project_root}")
    
    # Try absolute path first
    if os.path.isabs(source_file) and os.path.isfile(source_file):
        source_file_resolved = source_file
    # Try relative to project root (most common case - file should be at project root)
    elif (project_root / source_file).is_file():
        source_file_resolved = str((project_root / source_file).resolve())
    # Try script directory (parent of pages/) - this is where the file actually is
    elif (Path(__file__).parent.parent / source_file).is_file():
        source_file_resolved = str((Path(__file__).parent.parent / source_file).resolve())
    # Try current working directory
    elif Path(source_file).is_file():
        source_file_resolved = str(Path(source_file).resolve())
    # Try relative to output_dir parent
    elif (output_dir_path.parent / source_file).is_file():
        source_file_resolved = str((output_dir_path.parent / source_file).resolve())
    
    if not source_file_resolved or not os.path.isfile(source_file_resolved):
        st.warning(f"⚠️ Source file not found: {source_file}. The analysis will use pre-computed results only. To enable full analysis, ensure the source file is available.")
        df_source = None
        gtin_outer_col = None
    else:
        source_file = source_file_resolved
        st.markdown('<h1 class="main-header">Generic GTIN Analysis</h1>', unsafe_allow_html=True)
        st.markdown(f'<div style="text-align: center; color: #cbd5e1; margin-bottom: 1rem;">Source: <strong style="color: #94a3b8;">{os.path.basename(source_file)}</strong></div>', unsafe_allow_html=True)

        with st.spinner("Loading source data…"):
            df_source, gtin_outer_col, _ = _cached_load_source_file(source_file)
            if df_source is None:
                st.error("Failed to load source file.")
                df_source = None
                gtin_outer_col = None
    
    # If source file not available, show header and use pre-computed results only
    if df_source is None:
        st.markdown('<h1 class="main-header">Generic GTIN Analysis</h1>', unsafe_allow_html=True)
        st.info("ℹ️ Using pre-computed results only. Source file not available for detailed analysis.")
        # Load pre-computed results and show them
        generic_data = _cached_load_generic_results(output_dir)
        if generic_data and generic_data.get("overview"):
            overview = generic_data["overview"]
            st.markdown(f"**Total Generic GTINs:** {overview.get('total', 0):,}")
            st.markdown(f"**Conforming:** {overview.get('conforming_count', 0):,}")
            st.markdown(f"**Non-conforming:** {overview.get('non_conforming_count', 0):,}")
            if len(generic_data.get("by_entity_df", pd.DataFrame())) > 0:
                st.dataframe(generic_data["by_entity_df"], use_container_width=True, hide_index=True)
        return
    
    # Step 1: Filter on Generic GTINs with mapping FIRST (10000000000009, 30000000000009, 40000000000009, 70000000000009)
    # Normalize GTIN-Outer to 14 digits
    gtin_outer_normalized = df_source[gtin_outer_col].fillna("").astype(str).str.strip()
    gtin_14_series = gtin_outer_normalized.apply(lambda x: gtin_to_14(str(x)) if pd.notna(x) and str(x) else "")
    df_source["gtin_14"] = gtin_14_series
    
    # Keep only Generic GTINs with business_centres mapping
    df_filtered = df_source[df_source["gtin_14"].isin(GENERIC_GTINS_WITH_MAPPING)].copy()
    
    if len(df_filtered) == 0:
        st.info("No Generic GTINs with business_centres mapping found.")
        return

    # Step 2: Extract OSD prefix (taxonomy) for comparison
    osd_col = next((c for c in df_filtered.columns if str(c).strip().upper() == "OSD CLASSIFICATION"), None)
    if osd_col is None:
        st.error("OSD Classification column not found in source data.")
        return
    
    # Extract OSD prefix (taxonomy) - first part before first dash
    df_filtered["osd_prefix"] = df_filtered[osd_col].fillna("").astype(str).str.strip().str.split("-").str[0].str.strip().str.upper()

    # Step 3: Compare with expected GTINs
    # For each Generic GTIN, determine the expected GTIN based on taxonomy
    # If taxonomy is in mapping, use mapped GTIN; otherwise, use the Generic GTIN itself as expected
    df_filtered["expected_gtin"] = df_filtered["osd_prefix"].map(EXPECTED_GTIN_BY_TAXONOMY)
    # For products without taxonomy mapping, set expected_gtin to the Generic GTIN itself
    # This way we can still see what GTIN is expected even if taxonomy doesn't match
    df_filtered["expected_gtin"] = df_filtered["expected_gtin"].fillna(df_filtered["gtin_14"])
    # Add expected OSD taxonomy based on Generic GTIN
    df_filtered["expected_osd"] = df_filtered["gtin_14"].map(EXPECTED_OSD_BY_GTIN)
    df_filtered["conforming"] = df_filtered["osd_prefix"].isin(TARGET_TAXONOMIES) & (df_filtered["gtin_14"] == df_filtered["expected_gtin"])

    # Get legal entities
    legal_entities = sorted(df_filtered["Legal Entity"].dropna().unique().tolist())

    st.markdown('<div class="filter-section">', unsafe_allow_html=True)
    st.markdown("### Filters")
    if "selected_entities_gen_gtin" not in st.session_state:
        st.session_state.selected_entities_gen_gtin = legal_entities
    col1, col2 = st.columns([4, 1])
    with col1:
        selected_entities = st.multiselect("Select Legal Entities", legal_entities, default=st.session_state.selected_entities_gen_gtin, key="gen_gtin_entities")
        st.session_state.selected_entities_gen_gtin = selected_entities
    with col2:
        st.markdown('<div style="padding-top: 1.5rem;">', unsafe_allow_html=True)
        if st.button("Reset to All", use_container_width=True, key="gen_gtin_reset_all"):
            st.session_state.selected_entities_gen_gtin = legal_entities
            st.rerun()
        if st.button("Reset", use_container_width=True, key="gen_gtin_reset"):
            st.session_state.selected_entities_gen_gtin = []
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if not selected_entities:
        st.warning("Please select at least one Legal Entity")
        return

    # Filter by selected entities
    df_filtered = df_filtered[df_filtered["Legal Entity"].isin(selected_entities)].copy()

    # Calculate statistics
    total_gen = len(df_filtered)
    conforming_count = int(df_filtered["conforming"].sum())
    non_conforming_count = total_gen - conforming_count
    conforming_pct = (conforming_count / total_gen * 100) if total_gen > 0 else 0

    # Group by entity for statistics
    by_ent = df_filtered.groupby("Legal Entity").agg(
        total=("gtin_14", "count"),
        conforming=("conforming", "sum"),
    ).reset_index()
    by_ent["non_conforming"] = by_ent["total"] - by_ent["conforming"]
    by_ent["conforming_%"] = (by_ent["conforming"] / by_ent["total"] * 100).round(1)
    by_ent = by_ent.sort_values("non_conforming", ascending=False)

    # Non-conforming records (with all original columns)
    non_conforming_df = df_filtered[~df_filtered["conforming"]].copy()

    st.markdown('<div class="section-header">Conformity: Generic GTIN vs taxonomy (OSD prefix)</div>', unsafe_allow_html=True)
    st.markdown("*Analysis filtered on Generic GTINs: **10000000000009, 30000000000009, 40000000000009, 70000000000009**. Taxonomy = first part of **OSD Classification** (before first dash). Check: does the product's Generic GTIN match the expected one for that taxonomy? (Expected taxonomies: BEEF, PORK, POULTRY, SUPPLIES & EQUIPMENT, SEAFOOD, PRODUCE)*")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total records", f"{total_gen:,}", help=f"Products with Generic GTINs: 10000000000009, 30000000000009, 40000000000009, 70000000000009")
    with col2:
        st.metric("Conforming", f"{conforming_count:,}", f"{conforming_pct:.1f}%")
    with col3:
        st.metric("Non-conforming", f"{non_conforming_count:,}", f"{100 - conforming_pct:.1f}%")

    st.markdown('<div class="section-header">Non-conforming records</div>', unsafe_allow_html=True)
    if len(non_conforming_df) > 0:
        # Display overview with requested columns: SUPC, Description, OSD Taxonomy, OSD expected, GTIN outer, Legal entity
        overview_cols = ["SUPC", "Local Product Description", "osd_prefix", "expected_osd", gtin_outer_col, "Legal Entity"]
        # Filter to only columns that exist
        available_overview_cols = [c for c in overview_cols if c in non_conforming_df.columns]
        if available_overview_cols:
            # Rename columns for display
            display_df = non_conforming_df[available_overview_cols].copy()
            display_df = display_df.rename(columns={
                "osd_prefix": "OSD Taxonomy",
                "expected_osd": "OSD Expected",
                gtin_outer_col: "GTIN Outer",
                "Local Product Description": "Description"
            })
            st.dataframe(display_df.head(20), use_container_width=True, hide_index=True)
            st.caption(f"Showing first 20 rows. Total: {len(non_conforming_df):,} non-conforming records.")
        else:
            st.dataframe(non_conforming_df.head(20), use_container_width=True, hide_index=True)
        
        # Download: all original columns from source file (remove analysis columns we added)
        analysis_cols = {"osd_prefix", "gtin_14", "expected_gtin", "expected_osd", "conforming"}
        original_cols = [c for c in non_conforming_df.columns if c not in analysis_cols]
        non_conforming_export = non_conforming_df[original_cols].copy()
        _nc_bytes = to_excel_bytes(non_conforming_export)
        st.download_button("Download as Excel", data=_nc_bytes, file_name="generic_non_conforming.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_non_conforming")
    else:
        st.success("All Generic GTINs conform to the taxonomy (OSD prefix) mapping.")

    st.markdown('<div class="section-header">Conformity by Legal Entity</div>', unsafe_allow_html=True)
    st.dataframe(by_ent, use_container_width=True, hide_index=True)
    _by_path = os.path.join(output_dir, "generic_conformity_by_entity.xlsx")
    if set(selected_entities) == set(legal_entities) and os.path.isfile(_by_path):
        with open(_by_path, "rb") as _f:
            _by_bytes = _f.read()
    else:
        _by_bytes = to_excel_bytes(by_ent)
    st.download_button("Download as Excel", data=_by_bytes, file_name="generic_conformity_by_entity.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_by_ent")

    if len(by_ent) > 0:
        st.markdown("#### Conforming vs non-conforming by Legal Entity")
        fig = px.bar(by_ent, x="Legal Entity", y=["conforming", "non_conforming"], title="Generic GTIN conformity by Legal Entity", barmode="stack", labels={"value": "Records", "variable": ""}, color_discrete_sequence=["#2ecc71", "#e74c3c"])
        fig.update_layout(template="plotly_dark", height=400, plot_bgcolor="#1e293b", paper_bgcolor="#0f172a", font=dict(color="#f1f5f9"))
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("Mapping reference (OSD prefix / taxonomy → Expected Generic GTIN)"):
        ref = []
        for bc, gtin in sorted(EXPECTED_GTIN_BY_TAXONOMY.items()):
            ref.append({"OSD prefix (taxonomy)": bc, "Expected Generic GTIN": gtin, "LOV": GENERIC_GTIN_TAXONOMY.get(gtin, {}).get("lov", "")})
        st.dataframe(pd.DataFrame(ref), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()

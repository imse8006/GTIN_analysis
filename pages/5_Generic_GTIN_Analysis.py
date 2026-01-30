"""
Generic GTIN Analysis page: check if Generic GTINs CORRESPOND to the taxonomy.
Taxonomy = first part of "OSD Classification" (before first dash), e.g. "BEEF" from "BEEF-YYYY-ZZZZ".
Compare product's Generic GTIN to the expected Generic for that taxonomy (mapping).
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
from duplicate_analysis_backend import list_output_dates, load_generic_results, load_manifest, OUTPUTS_BASE


@st.cache_data(ttl=3600)
def _cached_load_generic_results(output_dir: str):
    """Cache Generic GTIN results (avoids re-reading Excel on every rerun)."""
    return load_generic_results(output_dir)

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

# Expected Generic GTIN per taxonomy (OSD prefix = part before first dash in "OSD Classification")
# Keys normalized to uppercase for lookup (OSD can be "BEEF" or "Beef")
EXPECTED_GTIN_BY_TAXONOMY = {}
for gtin_14, info in GENERIC_GTIN_TAXONOMY.items():
    for bc in info["business_centres"]:
        EXPECTED_GTIN_BY_TAXONOMY[bc.upper()] = gtin_14


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
        st.info(f"Aucun résultat pré-calculé. Exécutez le batch puis rechargez. Résultats dans `{OUTPUTS_BASE}/YYYY-MM-DD/`.")
        return

    date_options = [f"{d[0]} ({d[1]})" for d in output_dates]
    date_paths = {date_options[i]: output_dates[i][1] for i in range(len(output_dates))}
    selected_date_label = st.selectbox("**Extract date**", date_options, index=0, key="gen_gtin_date")
    output_dir = date_paths[selected_date_label]

    with st.spinner("Chargement des données…"):
        data = _cached_load_generic_results(output_dir)
    if data is None:
        st.error("Impossible de charger les résultats Generic GTIN pour cette date (ou aucun Generic dans les données).")
        return

    overview = data["overview"]
    by_entity_df = data["by_entity_df"]
    non_conforming_df_full = data["non_conforming_df"]
    all_records_df = data["all_records_df"]
    legal_entities = data["legal_entities"]
    gtin_outer_col = data["gtin_outer_col"]

    st.markdown('<h1 class="main-header">Generic GTIN Analysis</h1>', unsafe_allow_html=True)
    source_file = load_manifest(output_dir).get("source_file", "") or overview.get("source_file", "")
    st.markdown(f'<div style="text-align: center; color: #cbd5e1; margin-bottom: 1rem;">Source: <strong style="color: #94a3b8;">{source_file}</strong> (from outputs)</div>', unsafe_allow_html=True)

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

    by_ent = by_entity_df[by_entity_df["Legal Entity"].isin(selected_entities)] if selected_entities else by_entity_df
    non_conforming_df = non_conforming_df_full[non_conforming_df_full["Legal Entity"].isin(selected_entities)] if selected_entities and not non_conforming_df_full.empty else non_conforming_df_full
    generic_df = all_records_df[all_records_df["Legal Entity"].isin(selected_entities)] if selected_entities and not all_records_df.empty else all_records_df

    if len(generic_df) == 0:
        st.info("No Generic GTINs in the selected Legal Entities.")
        return

    # Columns are read as str from Excel; convert to numeric before sum (else .sum() concatenates strings)
    conforming_count = int(pd.to_numeric(by_ent["conforming"], errors="coerce").fillna(0).sum()) if "conforming" in by_ent.columns else 0
    non_conforming_count = int(pd.to_numeric(by_ent["non_conforming"], errors="coerce").fillna(0).sum()) if "non_conforming" in by_ent.columns else len(non_conforming_df)
    total_gen = len(generic_df)
    conforming_pct = (conforming_count / total_gen * 100) if total_gen > 0 else 0

    st.markdown('<div class="section-header">Conformity: Generic GTIN vs taxonomy (OSD prefix)</div>', unsafe_allow_html=True)
    st.markdown("*Taxonomy = first part of **OSD Classification** (before first dash). Check: does the product's Generic GTIN match the expected one for that taxonomy?*")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Generic records", f"{total_gen:,}")
    with col2:
        st.metric("Conforming", f"{conforming_count:,}", f"{conforming_pct:.1f}%")
    with col3:
        st.metric("Non-conforming", f"{non_conforming_count:,}", f"{100 - conforming_pct:.1f}%")
    with col4:
        no_map = generic_df["expected_gtin"].isna().sum() if "expected_gtin" in generic_df.columns else 0
        st.metric("No mapping (OSD prefix)", f"{no_map:,}", help="OSD prefix not in mapping (e.g. GROCERY, BAKERY)")

    st.markdown('<div class="section-header">Non-conforming records</div>', unsafe_allow_html=True)
    if len(non_conforming_df) > 0:
        display_nc = non_conforming_df.copy()
        for col in ["Expected Generic", "expected_gtin"]:
            if col in display_nc.columns:
                display_nc[col] = display_nc[col].fillna("— (no mapping)")
                break
        st.dataframe(display_nc, use_container_width=True, hide_index=True)
        _all_ent = set(selected_entities) == set(legal_entities)
        _nc_path = os.path.join(output_dir, "generic_non_conforming.xlsx")
        if _all_ent and os.path.isfile(_nc_path):
            with open(_nc_path, "rb") as _f:
                _nc_bytes = _f.read()
        else:
            _nc_bytes = to_excel_bytes(non_conforming_df)
        st.download_button("Download as Excel", data=_nc_bytes, file_name="generic_non_conforming.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_non_conforming")
        with st.expander("View full non-conforming records (all columns)"):
            full_cols = [c for c in ["Legal Entity", "osd_prefix", "gtin_14", "expected_gtin", "SUPC", "Local Product Description", "Brand"] if c in non_conforming_df.columns]
            st.dataframe(non_conforming_df[full_cols], use_container_width=True, hide_index=True)
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

    st.markdown('<div class="section-header">Sample Generic records (with conformity)</div>', unsafe_allow_html=True)
    sample_cols = [c for c in ["Legal Entity", "osd_prefix", "gtin_14", "expected_gtin", "conforming", "SUPC", "Local Product Description"] if c in generic_df.columns]
    sample_df = generic_df[sample_cols].head(50) if sample_cols else generic_df.head(50)
    st.dataframe(sample_df, use_container_width=True, hide_index=True)
    _all_path = os.path.join(output_dir, "generic_all_records_with_conformity.xlsx")
    if set(selected_entities) == set(legal_entities) and os.path.isfile(_all_path):
        with open(_all_path, "rb") as _f:
            _all_bytes = _f.read()
    else:
        _all_bytes = to_excel_bytes(generic_df[sample_cols] if sample_cols else generic_df)
    st.download_button("Download as Excel (all records)", data=_all_bytes, file_name="generic_all_records_with_conformity.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_sample")


if __name__ == "__main__":
    main()

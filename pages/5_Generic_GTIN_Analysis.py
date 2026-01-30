"""
Generic GTIN Analysis page: check if Generic GTINs CORRESPOND to the taxonomy.
Taxonomy = first part of "OSD Classification" (before first dash), e.g. "BEEF" from "BEEF-YYYY-ZZZZ".
Compare product's Generic GTIN to the expected Generic for that taxonomy (mapping).
"""
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
INPUT_FILE = "all-products-prod-2026-01-22_15.44.25.xlsx"

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


@st.cache_data
def load_and_classify_data():
    df = pd.read_excel(INPUT_FILE, dtype=str)
    gtin_col = None
    for col in df.columns:
        c = str(col).lower().strip()
        if "gtin" in c and "outer" in c:
            gtin_col = col
            break
    if gtin_col is None:
        for col in df.columns:
            if str(col).lower().strip() in ["gtin-outer", "gtin_outer", "gtinouter"]:
                gtin_col = col
                break
    if gtin_col is None:
        return None, None
    df["gtin_status"] = df[gtin_col].apply(classify_gtin_status_full)
    df["gtin_outer_normalized"] = df[gtin_col].apply(normalize_gtin)
    df["gtin_14"] = df["gtin_outer_normalized"].apply(gtin_to_14)
    df["taxonomy"] = df["gtin_14"].map(
        lambda x: GENERIC_GTIN_TAXONOMY.get(x, {}).get("lov", "Unknown") if x else "Unknown"
    )
    df["business_centres"] = df["gtin_14"].map(
        lambda x: ", ".join(GENERIC_GTIN_TAXONOMY.get(x, {}).get("business_centres", [])) if x else ""
    )
    # OSD Classification: extract taxonomy prefix (before first dash), e.g. "BEEF" from "BEEF-YYYY-ZZZZ"
    osd_col = None
    for col in df.columns:
        if str(col).strip().upper() == "OSD CLASSIFICATION":
            osd_col = col
            break
    if osd_col is None:
        df["osd_prefix"] = ""
    else:
        df["osd_prefix"] = df[osd_col].fillna("").astype(str).str.strip().str.split("-").str[0].str.strip()
    return df, gtin_col


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

    st.markdown('<h1 class="main-header">Generic GTIN Analysis</h1>', unsafe_allow_html=True)
    st.markdown(f'<div style="text-align: center; color: #cbd5e1; margin-bottom: 1rem;">Source file: <strong style="color: #94a3b8;">{INPUT_FILE}</strong></div>', unsafe_allow_html=True)

    with st.spinner("Loading data..."):
        result = load_and_classify_data()
        if result[0] is None:
            st.error("GTIN-Outer column not found!")
            return
        df, _ = result

    # Filters
    st.markdown('<div class="filter-section">', unsafe_allow_html=True)
    st.markdown("### Filters")
    legal_entities = sorted(df["Legal Entity"].unique())
    if "selected_entities_gen_gtin" not in st.session_state:
        st.session_state.selected_entities_gen_gtin = legal_entities
    col1, col2 = st.columns([4, 1])
    with col1:
        selected_entities = st.multiselect(
            "Select Legal Entities",
            legal_entities,
            default=st.session_state.selected_entities_gen_gtin,
            key="gen_gtin_entities"
        )
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

    df_filtered = df[df["Legal Entity"].isin(selected_entities)].copy()
    generic_df = df_filtered[df_filtered["gtin_status"] == "GENERIC"].copy()

    if len(generic_df) == 0:
        st.info("No Generic GTINs in the selected Legal Entities.")
        return

    # Expected Generic per OSD prefix (taxonomy = part before first dash in OSD Classification)
    generic_df["expected_gtin"] = generic_df["osd_prefix"].apply(
        lambda x: EXPECTED_GTIN_BY_TAXONOMY.get(str(x).strip().upper()) if pd.notna(x) and str(x).strip() else None
    )
    generic_df["conforming"] = generic_df["expected_gtin"].notna() & (generic_df["gtin_14"] == generic_df["expected_gtin"])
    conforming_count = generic_df["conforming"].sum()
    non_conforming_count = len(generic_df) - conforming_count
    conforming_pct = (conforming_count / len(generic_df) * 100) if len(generic_df) > 0 else 0

    # Overview: conformity check
    st.markdown('<div class="section-header">Conformity: Generic GTIN vs taxonomy (OSD prefix)</div>', unsafe_allow_html=True)
    st.markdown("*Taxonomy = first part of **OSD Classification** (before first dash). Check: does the product's Generic GTIN match the expected one for that taxonomy?*")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Generic records", f"{len(generic_df):,}")
    with col2:
        st.metric("Conforming", f"{conforming_count:,}", f"{conforming_pct:.1f}%")
    with col3:
        st.metric("Non-conforming", f"{non_conforming_count:,}", f"{100 - conforming_pct:.1f}%")
    with col4:
        st.metric("No mapping (OSD prefix)", f"{(generic_df['expected_gtin'].isna()).sum():,}", help="OSD prefix not in mapping (e.g. GROCERY, BAKERY)")

    # Non-conforming records (wrong Generic for this taxonomy)
    st.markdown('<div class="section-header">Non-conforming records</div>', unsafe_allow_html=True)
    non_conforming_df = generic_df[~generic_df["conforming"]].copy()
    if len(non_conforming_df) > 0:
        display_nc = non_conforming_df[["Legal Entity", "osd_prefix", "gtin_14", "expected_gtin", "taxonomy"]].copy()
        display_nc.columns = ["Legal Entity", "OSD prefix (taxonomy)", "Generic used", "Expected Generic", "LOV of used GTIN"]
        display_nc["Expected Generic"] = display_nc["Expected Generic"].fillna("— (no mapping)")
        st.dataframe(display_nc, use_container_width=True, hide_index=True)
        st.download_button("Download as Excel", data=to_excel_bytes(display_nc), file_name="generic_non_conforming.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_non_conforming")
        with st.expander("View full non-conforming records (all columns)"):
            osd_col = next((c for c in df.columns if str(c).strip().upper() == "OSD CLASSIFICATION"), None)
            full_cols = [c for c in ["Legal Entity", "osd_prefix", "gtin_14", "expected_gtin", "SUPC", "Local Product Description", "Brand"] if c in non_conforming_df.columns]
            if osd_col and osd_col not in full_cols:
                full_cols.insert(2, osd_col)
            st.dataframe(non_conforming_df[full_cols], use_container_width=True, hide_index=True)
    else:
        st.success("All Generic GTINs conform to the taxonomy (OSD prefix) mapping.")

    # By Legal Entity: conforming rate
    st.markdown('<div class="section-header">Conformity by Legal Entity</div>', unsafe_allow_html=True)
    by_ent = generic_df.groupby("Legal Entity").agg(
        total=("gtin_14", "count"),
        conforming=("conforming", "sum")
    ).reset_index()
    by_ent["non_conforming"] = by_ent["total"] - by_ent["conforming"]
    by_ent["conforming_%"] = (by_ent["conforming"] / by_ent["total"] * 100).round(1)
    by_ent = by_ent.sort_values("non_conforming", ascending=False)
    st.dataframe(by_ent, use_container_width=True, hide_index=True)
    st.download_button("Download as Excel", data=to_excel_bytes(by_ent), file_name="generic_conformity_by_entity.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_by_ent")

    # Chart: conforming vs non-conforming by Legal Entity
    if len(by_ent) > 0:
        st.markdown("#### Conforming vs non-conforming by Legal Entity")
        fig = px.bar(by_ent, x="Legal Entity", y=["conforming", "non_conforming"], title="Generic GTIN conformity by Legal Entity", barmode="stack", labels={"value": "Records", "variable": ""}, color_discrete_sequence=["#2ecc71", "#e74c3c"])
        fig.update_layout(template="plotly_dark", height=400, plot_bgcolor="#1e293b", paper_bgcolor="#0f172a", font=dict(color="#f1f5f9"))
        st.plotly_chart(fig, use_container_width=True)

    # Mapping reference (OSD prefix → Expected Generic)
    with st.expander("Mapping reference (OSD prefix / taxonomy → Expected Generic GTIN)"):
        ref = []
        for bc, gtin in sorted(EXPECTED_GTIN_BY_TAXONOMY.items()):
            ref.append({"OSD prefix (taxonomy)": bc, "Expected Generic GTIN": gtin, "LOV": GENERIC_GTIN_TAXONOMY.get(gtin, {}).get("lov", "")})
        st.dataframe(pd.DataFrame(ref), use_container_width=True, hide_index=True)

    # Sample of all Generic records (with conformity)
    st.markdown('<div class="section-header">Sample Generic records (with conformity)</div>', unsafe_allow_html=True)
    sample_cols = [c for c in ["Legal Entity", "osd_prefix", "gtin_14", "expected_gtin", "conforming", "SUPC", "Local Product Description"] if c in generic_df.columns]
    sample_df = generic_df[sample_cols].head(50)
    st.dataframe(sample_df, use_container_width=True, hide_index=True)
    st.download_button("Download as Excel (all records)", data=to_excel_bytes(generic_df[sample_cols]), file_name="generic_all_records_with_conformity.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_sample")


if __name__ == "__main__":
    main()

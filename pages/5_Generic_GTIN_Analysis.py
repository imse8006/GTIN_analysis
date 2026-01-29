"""
Generic GTIN Analysis page: analyze GENERIC GTINs by their exact number (taxonomy / LOV mapping).
Filter by Legal Entity. Mapping: Generic GTIN -> LOV Value in MDD (Business Centre).
"""
import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path
import sys

st.set_page_config(
    page_title="Generic GTIN Analysis - MDM",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

sys.path.append(str(Path(__file__).parent.parent))
INPUT_FILE = "all-products-prod-2026-01-22_15.44.25.xlsx"

# Generic GTIN set (same as other pages)
GENERIC_GTINS = {
    "10000000000009", "20000000000009", "30000000000009", "40000000000009",
    "50000000000009", "60000000000009", "70000000000009", "80000000000009",
}
EXPLICIT_BLOCKED = "99999999999999"
VALID_LENGTHS = {8, 13, 14}

# Mapping: Generic GTIN (14 digits) -> LOV Value in MDD (taxonomy). From Business Centre mapping.
# Business Centres using the same GTIN share the same LOV (e.g. BEEF, PORK, POULTRY -> Butchery).
GENERIC_GTIN_TAXONOMY = {
    "10000000000009": {"lov": "Butchery", "business_centres": ["BEEF", "PORK", "POULTRY"]},
    "30000000000009": {"lov": "Equipment", "business_centres": ["SUPPLIES & EQUIPMENT"]},
    "40000000000009": {"lov": "Fishmongery", "business_centres": ["SEAFOOD"]},
    "70000000000009": {"lov": "Produce", "business_centres": ["PRODUCE"]},
    # 20000000000009, 50000000000009, 60000000000009, 80000000000009: not in MDD mapping
    "20000000000009": {"lov": "Not in MDD", "business_centres": []},
    "50000000000009": {"lov": "Not in MDD", "business_centres": []},
    "60000000000009": {"lov": "Not in MDD", "business_centres": []},
    "80000000000009": {"lov": "Not in MDD", "business_centres": []},
}


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
    return df, gtin_col


def check_password():
    def password_entered():
        try:
            correct_password = st.secrets["PASSWORD"]
        except (KeyError, FileNotFoundError):
            correct_password = "OSDTeam123"
        if st.session_state.get("password") == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True
    st.markdown('<div style="text-align: center; padding: 2rem;">', unsafe_allow_html=True)
    st.markdown('<div style="color: #94a3b8; font-size: 2.5rem; font-weight: 700;">Generic GTIN Analysis</div>', unsafe_allow_html=True)
    st.text_input("Password", type="password", on_change=password_entered, key="password_gen_gtin", label_visibility="visible")
    if "password" in st.session_state and st.session_state.get("password_correct") is False:
        st.error("Incorrect password")
    if st.session_state.get("password_correct", False):
        st.markdown('</div>', unsafe_allow_html=True)
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    return False


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

    # Overview metrics
    st.markdown('<div class="section-header">Overview</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Generic records", f"{len(generic_df):,}")
    with col2:
        st.metric("Unique Generic GTINs", f"{generic_df['gtin_14'].nunique():,}")
    with col3:
        st.metric("Taxonomies (LOV)", f"{generic_df['taxonomy'].nunique():,}")

    # By taxonomy (LOV)
    st.markdown('<div class="section-header">By taxonomy (LOV Value in MDD)</div>', unsafe_allow_html=True)
    by_tax = generic_df.groupby("taxonomy").agg(
        records=("gtin_14", "count"),
        unique_gtins=("gtin_14", "nunique")
    ).reset_index()
    by_tax = by_tax.sort_values("records", ascending=False)
    st.dataframe(by_tax, use_container_width=True, hide_index=True)

    # By Generic GTIN (detail)
    st.markdown('<div class="section-header">By Generic GTIN</div>', unsafe_allow_html=True)
    by_gtin = generic_df.groupby("gtin_14").agg(
        taxonomy=("taxonomy", "first"),
        business_centres=("business_centres", "first"),
        records=("gtin_14", "count")
    ).reset_index()
    by_gtin.columns = ["Generic GTIN", "LOV (taxonomy)", "Business Centres", "Records"]
    by_gtin = by_gtin.sort_values("Records", ascending=False)
    st.dataframe(by_gtin, use_container_width=True, hide_index=True)

    # By Legal Entity x taxonomy
    st.markdown('<div class="section-header">By Legal Entity and taxonomy</div>', unsafe_allow_html=True)
    by_ent_tax = generic_df.groupby(["Legal Entity", "taxonomy"]).size().reset_index(name="Records")
    pivot = by_ent_tax.pivot(index="Legal Entity", columns="taxonomy", values="Records").fillna(0).astype(int)
    st.dataframe(pivot, use_container_width=True, hide_index=True)

    # Charts
    st.markdown('<div class="section-header">Charts</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Records by taxonomy")
        fig_tax = px.bar(by_tax, x="taxonomy", y="records", labels={"taxonomy": "LOV (taxonomy)", "records": "Records"})
        fig_tax.update_layout(template="plotly_dark", height=400, plot_bgcolor="#1e293b", paper_bgcolor="#0f172a", font=dict(color="#f1f5f9"))
        st.plotly_chart(fig_tax, use_container_width=True)
    with col2:
        st.markdown("#### Records by Generic GTIN")
        fig_gtin = px.bar(by_gtin, x="Generic GTIN", y="Records", color="LOV (taxonomy)")
        fig_gtin.update_layout(template="plotly_dark", height=400, plot_bgcolor="#1e293b", paper_bgcolor="#0f172a", font=dict(color="#f1f5f9"))
        st.plotly_chart(fig_gtin, use_container_width=True)

    # Mapping reference
    with st.expander("Mapping reference (Generic GTIN → LOV / Business Centre)"):
        ref = []
        for gtin, info in GENERIC_GTIN_TAXONOMY.items():
            ref.append({
                "Generic GTIN": gtin,
                "LOV (MDD)": info["lov"],
                "Business Centres": ", ".join(info["business_centres"]) if info["business_centres"] else "—"
            })
        st.dataframe(pd.DataFrame(ref), use_container_width=True, hide_index=True)

    # Sample records
    st.markdown('<div class="section-header">Sample Generic records</div>', unsafe_allow_html=True)
    sample_cols = [c for c in ["Legal Entity", "SUPC", "Local Product Description", "Brand", "gtin_outer_normalized", "taxonomy", "business_centres"] if c in generic_df.columns]
    st.dataframe(generic_df[sample_cols].head(50), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()

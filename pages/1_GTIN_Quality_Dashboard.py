import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path
from datetime import date
import io
import base64
import tempfile
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Try to import win32com for Outlook integration (Windows only)
OUTLOOK_AVAILABLE = False
OUTLOOK_ERROR_MSG = None
import sys
import platform

# Check if running on Windows
IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    try:
        import win32com.client
        OUTLOOK_AVAILABLE = True
    except ImportError as e:
        OUTLOOK_AVAILABLE = False
        python_path = sys.executable
        OUTLOOK_ERROR_MSG = f"pywin32 is not installed in the Python environment used by Streamlit. Python path: {python_path}"
    except Exception as e:
        OUTLOOK_AVAILABLE = False
        OUTLOOK_ERROR_MSG = f"Error importing win32com: {str(e)}"
else:
    # Not on Windows - Outlook integration not available
    OUTLOOK_AVAILABLE = False
    python_path = sys.executable
    OUTLOOK_ERROR_MSG = f"Outlook integration is only available on Windows. Current system: {platform.system()}, Python path: {python_path}"

# Page configuration
st.set_page_config(
    page_title="GTIN Quality Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"  # Expanded to show navigation
)

# Custom CSS for professional dark theme look
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
    .filter-section {
        background-color: #1e293b;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 2rem;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .stMetric {
        background-color: #1e293b;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        border: 1px solid #334155;
        min-height: 8rem;
    }
    .stMetric label {
        font-size: 0.9rem;
        font-weight: 600;
        color: #cbd5e1;
    }
    .stMetric [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    /* Overview 7 metrics: equal column width */
    div[data-testid="stHorizontalBlock"]:has(> div:nth-of-type(7)) > div {
        flex: 1 1 0 !important;
        min-width: 0 !important;
    }
    /* Breakdown (8/13/14): smaller font to avoid truncation */
    div[data-testid="stHorizontalBlock"]:has(> div:nth-of-type(7)) > div:nth-of-type(6) [data-testid="stMetricValue"] {
        font-size: 1.15rem !important;
    }
    .stMetric [data-testid="stMetricDelta"] {
        font-size: 1rem;
        font-weight: 600;
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
    .stDataFrame {
        background-color: #1e293b;
        border-radius: 0.5rem;
        padding: 1rem;
    }
    /* Override Streamlit default background */
    .stApp {
        background-color: #0f172a;
    }
    /* Custom Save button styling - softer blue */
    button[kind="primary"][data-testid="baseButton-save_quality_analysis_top"] {
        background-color: #3b82f6 !important;
        border-color: #3b82f6 !important;
        color: white !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    button[kind="primary"][data-testid="baseButton-save_quality_analysis_top"]:hover {
        background-color: #2563eb !important;
        border-color: #2563eb !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
    }
    /* Style for selectbox and multiselect in dark theme */
    .stSelectbox label, .stMultiSelect label {
        color: #cbd5e1 !important;
    }
    /* Footer styling */
    .footer {
        background-color: #1e293b;
        border-radius: 0.5rem;
        padding: 1.5rem;
        border: 1px solid #334155;
    }
    /* Hide spinner borders and status indicators */
    [data-testid="stStatusWidget"] {
        display: none !important;
    }
    /* Hide the status box with black borders */
    div[data-testid="stStatusWidget"] {
        display: none !important;
    }
    /* Hide spinner container borders */
    .stSpinner {
        border: none !important;
    }
    .stSpinner > div {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    /* Hide empty Streamlit elements */
    [data-testid="stEmpty"] {
        display: none !important;
    }
    div[data-testid="stElementContainer"]:has([data-testid="stEmpty"]) {
        display: none !important;
    }
    /* Ensure subject field shows full text and is left-aligned */
    .stTextInput > div > div {
        width: 100% !important;
    }
    .stTextInput input {
        width: 100% !important;
        max-width: 100% !important;
    }
    /* Ensure subject field shows full text */
    div[data-testid="stTextInput"] {
        width: 100% !important;
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
    </style>
""", unsafe_allow_html=True)

# Import des fonctions de classification depuis gtin_analysis.py
import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent))
from export_utils import to_excel_bytes
from auth_utils import render_login_form
from duplicate_analysis_backend import list_output_dates, load_quality_results, load_manifest, OUTPUTS_BASE
from tracker_utils import save_tracker_data, has_tracker_entry_for


@st.cache_data(ttl=3600)
def _cached_load_quality_results(output_dir: str):
    """Cache Quality results (avoids re-reading 144k-row Excel on every rerun)."""
    return load_quality_results(output_dir)

# MDM Business Rules
GENERIC_GTINS = {
    "10000000000009", "20000000000009", "30000000000009", "40000000000009",
    "50000000000009", "60000000000009", "70000000000009", "80000000000009",
}
EXPLICIT_BLOCKED = "99999999999999"
VALID_LENGTHS = {8, 13, 14}

# Legal Entity to Email Recipients Mapping
LEGAL_ENTITY_EMAILS = {
    "Brakes": ["samantha.smith@sysco.com"],
    "Sysco ROI": ["glen-timperley@sysco.com", "sarah-graham@sysco.com"],
    "Sysco NI": ["glen-timperley@sysco.com", "sarah-graham@sysco.com"],
    "Classic Drinks": ["glen-timperley@sysco.com", "sarah-graham@sysco.com"],
    "Ready Chef": ["glen-timperley@sysco.com", "sarah-graham@sysco.com"],
    "Menigo": ["paula.sterner@menigo.se"],
    "Fruktservice": ["paula.sterner@menigo.se"],
    "Servicestyckarna": ["paula.sterner@menigo.se"],
    "Ekofisk": ["paula.sterner@menigo.se"],
    "Fresh Direct": ["ben.newby@sysco.com"],
    "KFF": ["joseph.maczka@sysco.com"],
    "Medina": ["joseph.maczka@sysco.com"],
    "France": ["severine.branciard@sysco.com"],
    "LAG": ["severine.branciard@sysco.com"],
}


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


def has_valid_gs1_check_digit(gtin: str) -> bool:
    """Valide la clé de contrôle GS1 pour tout format (GTIN-8, 12, 13, 14, SSCC)."""
    if not gtin.isdigit() or len(gtin) not in (8, 12, 13, 14, 18):
        return False

    # On récupère les chiffres sous forme d'entiers
    digits = [int(d) for d in gtin]
    body = digits[:-1]
    check_digit = digits[-1]

    # Règle universelle GS1 : 
    # En partant de la droite (avant la clé), le multiplicateur est toujours 3, puis 1, puis 3...
    total = 0
    for i, d in enumerate(reversed(body)):
        multiplier = 3 if i % 2 == 0 else 1
        total += d * multiplier

    calc = (10 - (total % 10)) % 10
    return calc == check_digit


def classify_gtin_status(gtin_raw):
    """Classify GTIN according to MDM rules.
    Returns: INVALID, GENERIC, PLACEHOLDER, 8_digits, 13_digits, 14_digits
    """
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
    
    # Check digit validation - if invalid, mark as INVALID
    if not has_valid_gs1_check_digit(gtin, length):
        return "INVALID"
    
    # Valid GTINs
    if length == 8:
        return "8_digits"
    elif length == 13:
        return "13_digits"
    else:  # length == 14
        return "14_digits"


def check_password():
    """Returns `True` if the user had the correct password."""
    return render_login_form("GTIN Quality Dashboard")


def main():
    # Password protection
    if not check_password():
        st.stop()

    # Load from pre-computed outputs (batch writes to outputs/YYYY-MM-DD/)
    output_dates = list_output_dates()
    if not output_dates:
        st.info(
            f"No pre-computed results. Run the batch then reload:\n\n"
            f"`python run_duplicate_analysis_batch.py [file.xlsx]`\n\n"
            f"Results in `{OUTPUTS_BASE}/YYYY-MM-DD/`."
        )
        return

    date_options = [f"{d[0]} ({d[1]})" for d in output_dates]
    date_paths = {date_options[i]: output_dates[i][1] for i in range(len(output_dates))}
    selected_date_label = st.selectbox("**Extract date**", date_options, index=0, key="quality_select_date")
    output_dir = date_paths[selected_date_label]

    load_ph = st.empty()
    with load_ph.container():
        st.markdown("<div style='text-align: center; padding: 4rem 2rem; color: #94a3b8;'>", unsafe_allow_html=True)
        with st.spinner("Loading data…"):
            data = _cached_load_quality_results(output_dir)
        st.markdown("</div>", unsafe_allow_html=True)
    if data is None:
        st.error("Unable to load Quality results for this date.")
        return
    load_ph.empty()

    overview = data["overview"]
    by_entity_df = data["by_entity_df"]
    full_classified_df = data["full_classified_df"]
    generics_non_eupcker_df = data["generics_non_eupcker_df"]
    legal_entities = data["legal_entities"]
    total_rows = data["total_rows"]
    gtin_col = data["gtin_outer_col"]
    source_file = overview.get("source_file", "")

    # Header
    st.markdown('<h1 class="main-header">GTIN Quality Dashboard</h1>', unsafe_allow_html=True)
    st.markdown(f'<div style="text-align: center; color: #cbd5e1; margin-bottom: 1rem;">Source: <strong style="color: #94a3b8;">{source_file}</strong></div>', unsafe_allow_html=True)

    # Auto-save to tracker when this output is not yet recorded
    extract_date = Path(output_dir).name
    manifest = load_manifest(output_dir)
    source_file_tracker = manifest.get("source_file", source_file)
    if not has_tracker_entry_for(extract_date, source_file_tracker, "quality"):
        entity_metrics = []
        for _, row in by_entity_df.iterrows():
            entity_metrics.append({
                "legal_entity": row.get("Legal Entity", ""),
                "total_products": int(row["Total Products"]) if "Total Products" in row and pd.notna(row["Total Products"]) else 0,
                "valid_gtins": int(row["Valid GTINs"]) if "Valid GTINs" in row and pd.notna(row["Valid GTINs"]) else 0,
                "invalid_gtins": int(row["Invalid GTINs"]) if "Invalid GTINs" in row and pd.notna(row["Invalid GTINs"]) else 0,
                "generic_gtins": int(row["Generic GTINs"]) if "Generic GTINs" in row and pd.notna(row["Generic GTINs"]) else 0,
                "placeholder_gtins": int(row["Placeholder GTINs (999...99)"]) if "Placeholder GTINs (999...99)" in row and pd.notna(row["Placeholder GTINs (999...99)"]) else 0,
                "compliance_rate": round(float(row["Compliance Rate (%)"]), 2) if "Compliance Rate (%)" in row and pd.notna(row["Compliance Rate (%)"]) else 0,
            })
        tracker_entry = {
            "analysis_type": "quality",
            "extract_date": extract_date,
            "source_file": source_file_tracker,
            "legal_entities": legal_entities,
            "total_products": overview.get("total_rows", 0),
            "total_valid": overview.get("total_valid", 0),
            "total_invalid": overview.get("total_invalid", 0),
            "total_generic": overview.get("total_generic", 0),
            "total_placeholder": overview.get("total_placeholder", 0),
            "compliance_rate": round(float(overview.get("compliance_rate", 0)), 2),
            "breakdown": {},
            "entity_metrics": entity_metrics,
        }
        if "8 digits" in by_entity_df.columns and "13 digits" in by_entity_df.columns and "14 digits" in by_entity_df.columns:
            try:
                tracker_entry["breakdown"] = {"8_digits": int(by_entity_df["8 digits"].sum()), "13_digits": int(by_entity_df["13 digits"].sum()), "14_digits": int(by_entity_df["14 digits"].sum())}
            except Exception:
                pass
        save_tracker_data(tracker_entry)

    st.markdown('<div class="filter-section">', unsafe_allow_html=True)
    st.markdown("### Filters")
    search_query = st.text_input("🔍 Search SUPC or GTIN", placeholder="e.g. 12345 or 08701234567890", key="search_supc_gtin", help="Exact match on SUPC or GTIN (Outer, normalized).")
    if "selected_entities_quality" not in st.session_state:
        st.session_state.selected_entities_quality = legal_entities
    
    col1, col2 = st.columns([4, 1])
    with col1:
        # Handle reset buttons first
        if st.button("Reset to All", use_container_width=True, key="quality_reset_all"):
            st.session_state.selected_entities_quality = legal_entities
            st.session_state.quality_entities = legal_entities
            st.rerun()
        if st.button("Reset", use_container_width=True, key="quality_reset"):
            st.session_state.selected_entities_quality = []
            st.session_state.quality_entities = []
            st.rerun()
        
        selected_entities = st.multiselect("**Select Legal Entities**", legal_entities, default=st.session_state.selected_entities_quality, help="Select one or more Legal Entities to analyze", key="quality_entities")
        st.session_state.selected_entities_quality = selected_entities
    with col2:
        st.markdown('<div style="padding-top: 1.5rem;">', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    selected_entities = st.session_state.selected_entities_quality
    if not selected_entities:
        st.warning("Please select at least one Legal Entity")
        return

    # Filter in memory (all data loaded from outputs/)
    entity_counts = overview.get("entity_total_products", {})
    filtered_len = sum(entity_counts.get(e, 0) for e in selected_entities) if selected_entities else total_rows
    by_entity_filtered = by_entity_df[by_entity_df["Legal Entity"].isin(selected_entities)] if selected_entities else by_entity_df
    df_filtered = full_classified_df[full_classified_df["Legal Entity"].isin(selected_entities)].copy() if selected_entities else full_classified_df.copy()
    generics_filtered = generics_non_eupcker_df[generics_non_eupcker_df["Legal Entity"].isin(selected_entities)] if not generics_non_eupcker_df.empty and selected_entities else generics_non_eupcker_df
    
    # Search filter (SUPC or GTIN, exact match)
    if search_query and str(search_query).strip():
        q = str(search_query).strip()
        parts = []
        if "SUPC" in df_filtered.columns:
            parts.append(df_filtered["SUPC"].fillna("").astype(str).str.strip() == q)
        parts.append(df_filtered[gtin_col].fillna("").astype(str).str.strip() == q)
        if "gtin_outer_normalized" in df_filtered.columns:
            parts.append(df_filtered["gtin_outer_normalized"].fillna("").astype(str).str.strip() == q)
        if parts:
            mask = parts[0]
            for p in parts[1:]:
                mask = mask | p
            df_filtered = df_filtered[mask].copy()
        if len(df_filtered) == 0:
            st.info("No results for your search.")
    
    # Overall metrics
    st.markdown('<div class="section-header">Overview</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
    valid_statuses = ["8_digits", "13_digits", "14_digits"]
    
    total_valid = df_filtered[df_filtered["gtin_status"].isin(valid_statuses)].shape[0]
    total_invalid = df_filtered[df_filtered["gtin_status"] == "INVALID"].shape[0]
    total_generic = df_filtered[df_filtered["gtin_status"] == "GENERIC"].shape[0]
    # Accept both PLACEHOLDER and BLOCKED for backward compatibility with cached data
    total_blocked = df_filtered[df_filtered["gtin_status"].isin(["PLACEHOLDER", "BLOCKED"])].shape[0]
    total_8 = df_filtered[df_filtered["gtin_status"] == "8_digits"].shape[0]
    total_13 = df_filtered[df_filtered["gtin_status"] == "13_digits"].shape[0]
    total_14 = df_filtered[df_filtered["gtin_status"] == "14_digits"].shape[0]
    
    brand_col = next((c for c in df_filtered.columns if str(c).strip().lower() == "brand"), None)
    generics_non_eupcker = generics_filtered
    total_generics_non_eupcker = len(generics_filtered)
    
    compliance_rate = (total_valid / filtered_len * 100) if filtered_len > 0 else 0
    invalid_rate = (total_invalid / filtered_len * 100) if filtered_len > 0 else 0
    generic_rate = (total_generic / filtered_len * 100) if filtered_len > 0 else 0
    placeholder_rate = (total_blocked / filtered_len * 100) if filtered_len > 0 else 0

    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    with col1:
        st.metric("Total Products", f"{filtered_len:,}")
    with col2:
        st.metric("✅ Valid GTINs", f"{total_valid:,}", f"{compliance_rate:.1f}%")
    with col3:
        st.metric("❌ Invalid GTINs", f"{total_invalid:,}", f"{invalid_rate:.1f}%")
    with col4:
        st.metric("Generic GTINs", f"{total_generic:,}", f"{generic_rate:.1f}%")
    with col5:
        st.metric("Placeholder GTINs (999...99)", f"{total_blocked:,}", f"{placeholder_rate:.1f}%")
    with col6:
        st.metric("Breakdown", f"{total_8}/{total_13}/{total_14}", help="8 digits / 13 digits / 14 digits")
    with col7:
        if brand_col is not None:
            st.metric("Generics (Brand ≠ EUPCKER)", f"{total_generics_non_eupcker:,}", help="Generic GTINs where Brand is not EUPCKER")
        else:
            st.metric("Generics (Brand ≠ EUPCKER)", "N/A", help="Column Brand not found")
    
    # Downloads for Invalid, Generic, and Placeholder GTINs
    # Only show download buttons when exactly ONE Legal Entity is selected
    if len(selected_entities) == 1 and (total_invalid > 0 or total_generic > 0 or total_blocked > 0):
        st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)
        col_inv, col_gen, col_place = st.columns(3)
        
        with col_inv:
            if total_invalid > 0:
                invalid_df = df_filtered[df_filtered["gtin_status"] == "INVALID"].copy()
                # Download ALL Invalid GTINs (not just sample)
                # Select relevant columns for export
                export_cols_inv = [c for c in ["Legal Entity", "SUPC", "Local Product Description", gtin_col, "gtin_outer_normalized", "gtin_status"] if c in invalid_df.columns]
                st.download_button(
                    f"📥 Download All Invalid GTINs ({len(invalid_df):,} records)",
                    data=to_excel_bytes(invalid_df[export_cols_inv]),
                    file_name=f"invalid_gtins_all_{extract_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_invalid_all",
                    use_container_width=True
                )
        
        with col_gen:
            if total_generic > 0:
                generic_df = df_filtered[df_filtered["gtin_status"] == "GENERIC"].copy()
                # Download ALL Generic GTINs (not just sample)
                # Select relevant columns for export
                export_cols_gen = [c for c in ["Legal Entity", "SUPC", "Local Product Description", gtin_col, "gtin_outer_normalized", "gtin_status"] if c in generic_df.columns]
                st.download_button(
                    f"📥 Download All Generic GTINs ({len(generic_df):,} records)",
                    data=to_excel_bytes(generic_df[export_cols_gen]),
                    file_name=f"generic_gtins_all_{extract_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_generic_all",
                    use_container_width=True
                )
        
        with col_place:
            if total_blocked > 0:
                placeholder_df = df_filtered[df_filtered["gtin_status"].isin(["PLACEHOLDER", "BLOCKED"])].copy()
                # Download ALL Placeholder GTINs
                # Select relevant columns for export
                export_cols_place = [c for c in ["Legal Entity", "SUPC", "Local Product Description", gtin_col, "gtin_outer_normalized", "gtin_status"] if c in placeholder_df.columns]
                st.download_button(
                    f"📥 Download All Placeholder GTINs ({len(placeholder_df):,} records)",
                    data=to_excel_bytes(placeholder_df[export_cols_place]),
                    file_name=f"placeholder_gtins_all_{extract_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_placeholder_all",
                    use_container_width=True
                )
    
    # Analysis by Legal Entity
    st.markdown('<div class="section-header">Analysis by Legal Entity</div>', unsafe_allow_html=True)
    
    # Create analysis dataframe
    analysis_data = []
    for entity in selected_entities:
        entity_df = df_filtered[df_filtered["Legal Entity"] == entity]
        total = len(entity_df)
        
        status_counts = entity_df["gtin_status"].value_counts().to_dict()
        
        valid_count = sum(status_counts.get(s, 0) for s in valid_statuses)
        invalid_count = status_counts.get("INVALID", 0)
        generic_count = status_counts.get("GENERIC", 0)
        # Accept both PLACEHOLDER and BLOCKED for backward compatibility
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
    
    analysis_df = pd.DataFrame(analysis_data)
    
    # Display table with better formatting
    display_df = analysis_df.copy()
    display_df = display_df.sort_values("Compliance Rate (%)", ascending=False)
    
    # Create styled dataframe - keep numeric for gradient, format for display
    styled_df = display_df.style.background_gradient(
        subset=["Compliance Rate (%)"], 
        cmap="RdYlGn", 
        vmin=0, 
        vmax=100
    )
    
    # Format the percentage column for display
    styled_df = styled_df.format({
        "Compliance Rate (%)": "{:.2f}%"
    })
    
    st.dataframe(
        styled_df,
        use_container_width=True,
        height=400
    )
    _all_entities = set(selected_entities) == set(legal_entities)
    _quality_by_entity_path = os.path.join(output_dir, "quality_by_entity.xlsx")
    if _all_entities and os.path.isfile(_quality_by_entity_path):
        with open(_quality_by_entity_path, "rb") as _f:
            _quality_bytes = _f.read()
    else:
        _quality_bytes = to_excel_bytes(display_df)
    st.download_button(
        "Download as Excel",
        data=_quality_bytes,
        file_name="quality_analysis_by_legal_entity.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dl_quality_analysis"
    )
    
    st.markdown('<div style="margin-top: 2rem;"></div>', unsafe_allow_html=True)
    
    # Charts
    if len(selected_entities) > 1:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Compliance Rate by Legal Entity")
            fig_compliance = px.bar(
                analysis_df.sort_values("Compliance Rate (%)", ascending=True),
                x="Compliance Rate (%)",
                y="Legal Entity",
                orientation='h',
                color="Compliance Rate (%)",
                color_continuous_scale="RdYlGn",
                text="Compliance Rate (%)",
                labels={"Compliance Rate (%)": "Compliance Rate (%)", "Legal Entity": "Legal Entity"}
            )
            fig_compliance.update_traces(texttemplate='%{text:.1f}%', textposition='outside', textfont=dict(color='#f1f5f9', size=11))
            fig_compliance.update_layout(height=450, showlegend=False, template='plotly_dark', plot_bgcolor='#1e293b', paper_bgcolor='#0f172a', font=dict(size=12, color='#f1f5f9'), xaxis=dict(gridcolor='#334155', gridwidth=1), yaxis=dict(showgrid=False))
            st.plotly_chart(fig_compliance, use_container_width=True)
        with col2:
            st.markdown("#### GTIN Status Distribution")
            status_summary = df_filtered["gtin_status"].value_counts().reset_index()
            status_summary.columns = ["Status", "Count"]
            fig_pie = px.pie(status_summary, values="Count", names="Status", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
            fig_pie.update_traces(textposition='inside', textinfo='percent+label', textfont=dict(size=11, color='#f1f5f9'))
            fig_pie.update_layout(height=450, template='plotly_dark', plot_bgcolor='#1e293b', paper_bgcolor='#0f172a', font=dict(size=12, color='#f1f5f9'), showlegend=True, legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.1, font=dict(color='#f1f5f9', size=11), bgcolor='rgba(30, 41, 59, 0.8)', bordercolor='#334155', borderwidth=1))
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.markdown("#### GTIN Status Distribution")
        status_summary = df_filtered["gtin_status"].value_counts().reset_index()
        status_summary.columns = ["Status", "Count"]
        fig_pie = px.pie(status_summary, values="Count", names="Status", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label', textfont=dict(size=11, color='#f1f5f9'))
        fig_pie.update_layout(height=450, template='plotly_dark', plot_bgcolor='#1e293b', paper_bgcolor='#0f172a', font=dict(size=12, color='#f1f5f9'), showlegend=True, legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.1, font=dict(color='#f1f5f9', size=11), bgcolor='rgba(30, 41, 59, 0.8)', bordercolor='#334155', borderwidth=1))
        st.plotly_chart(fig_pie, use_container_width=True)
    
    if len(selected_entities) > 1:
        st.markdown('<div class="section-header">Status Details by Legal Entity</div>', unsafe_allow_html=True)
        status_cols = ["Valid GTINs", "Invalid GTINs", "Generic GTINs", "Placeholder GTINs (999...99)"]
        chart_data = analysis_df[["Legal Entity"] + status_cols].copy()
        chart_data = chart_data.sort_values("Legal Entity")
        chart_melted = pd.melt(chart_data, id_vars=["Legal Entity"], value_vars=status_cols, var_name="Status", value_name="Count")
        fig_stacked = px.bar(chart_melted, x="Legal Entity", y="Count", color="Status", barmode='stack', labels={"Count": "Number of Products", "Legal Entity": "Legal Entity"}, color_discrete_map={"Valid GTINs": "#2ecc71", "Invalid GTINs": "#e74c3c", "Generic GTINs": "#f39c12", "Placeholder GTINs (999...99)": "#34495e"})
        fig_stacked.update_layout(height=500, template='plotly_dark', plot_bgcolor='#1e293b', paper_bgcolor='#0f172a', font=dict(size=12, color='#f1f5f9'), xaxis_title="Legal Entity", yaxis_title="Number of Products", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color='#f1f5f9', size=11), bgcolor='rgba(30, 41, 59, 0.8)', bordercolor='#334155', borderwidth=1), xaxis={'categoryorder': 'total descending'})
        fig_stacked.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#334155', griddash='dash')
        fig_stacked.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#334155', griddash='dash')
        st.plotly_chart(fig_stacked, use_container_width=True)
    
    # Generics with Brand != EUPCKER
    st.markdown('<div class="section-header">Generics with Brand ≠ EUPCKER</div>', unsafe_allow_html=True)
    if brand_col is None:
        st.warning("Column **Brand** not found in the data. This analysis is not available.")
    elif len(generics_non_eupcker) == 0:
        st.success("No Generic GTINs with Brand ≠ EUPCKER.")
    else:
        st.markdown(f"*Generic GTINs where Brand is not EUPCKER: **{total_generics_non_eupcker:,}** records.*")
        by_ent = generics_non_eupcker.groupby("Legal Entity").size().reset_index(name="Generics (Brand ≠ EUPCKER)")
        total_gen_ent = df_filtered[df_filtered["gtin_status"] == "GENERIC"].groupby("Legal Entity").size()
        by_ent = by_ent.merge(total_gen_ent.rename("Total Generics"), left_on="Legal Entity", right_index=True, how="left")
        by_ent["% of Entity Generics"] = (by_ent["Generics (Brand ≠ EUPCKER)"] / by_ent["Total Generics"] * 100).round(2)
        by_ent = by_ent.sort_values("Generics (Brand ≠ EUPCKER)", ascending=False)
        st.dataframe(by_ent, use_container_width=True, hide_index=True)
        st.download_button(
            "Download as Excel",
            data=to_excel_bytes(by_ent),
            file_name="generics_brand_not_eupcker_by_entity.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_generics_by_ent"
        )
        if len(selected_entities) > 1:
            fig_ge = px.bar(by_ent, x="Legal Entity", y="Generics (Brand ≠ EUPCKER)", title="Generics (Brand ≠ EUPCKER) by Legal Entity", labels={"Generics (Brand ≠ EUPCKER)": "Count"})
            fig_ge.update_layout(template="plotly_dark", height=400, plot_bgcolor="#1e293b", paper_bgcolor="#0f172a", font=dict(color="#f1f5f9"))
            st.plotly_chart(fig_ge, use_container_width=True)
        st.markdown("##### Sample (first 20)")
        pc = [c for c in ["Legal Entity", "SUPC", "Local Product Description", brand_col, "OSD Classification", "gtin_outer_normalized"] if c in generics_non_eupcker.columns]
        st.dataframe(generics_non_eupcker[pc].head(20), use_container_width=True, hide_index=True)
        st.download_button(
            "Download as Excel (all records)",
            data=to_excel_bytes(generics_non_eupcker[pc]),
            file_name="generics_brand_not_eupcker_all.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_generics_non_eupcker_all"
        )
    
    # Detailed status breakdown
    st.markdown('<div class="section-header">Detailed Status Breakdown</div>', unsafe_allow_html=True)
    
    selected_entity_detail = st.selectbox(
        "**Select a Legal Entity for detailed analysis**",
        selected_entities,
        key="entity_detail"
    )
    
    if selected_entity_detail:
        entity_detail_df = df_filtered[df_filtered["Legal Entity"] == selected_entity_detail]
        status_detail = entity_detail_df["gtin_status"].value_counts().reset_index()
        status_detail.columns = ["Status", "Count"]
        status_detail["Percentage"] = (status_detail["Count"] / len(entity_detail_df) * 100).round(2)
        status_detail = status_detail.sort_values("Count", ascending=False)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            fig_detail = px.bar(
                status_detail,
                x="Status",
                y="Count",
                text="Count",
                color="Status",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_detail.update_traces(textposition='outside', textfont=dict(size=11, color='#f1f5f9'))
            fig_detail.update_layout(
                height=450,
                template='plotly_dark',
                plot_bgcolor='#1e293b',
                paper_bgcolor='#0f172a',
                font=dict(size=12, color='#f1f5f9'),
                xaxis_title="GTIN Status",
                yaxis_title="Number of Products"
            )
            fig_detail.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#334155', griddash='dash')
            fig_detail.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#334155', griddash='dash')
            st.plotly_chart(fig_detail, use_container_width=True)
        
        with col2:
            st.markdown("#### Status Summary")
            status_detail_display = status_detail.copy()
            status_detail_display["Count"] = status_detail_display["Count"].apply(lambda x: f"{int(x):,}")
            status_detail_display["Percentage"] = status_detail_display["Percentage"].apply(lambda x: f"{x:.2f}%")
            st.dataframe(status_detail_display, use_container_width=True, hide_index=True)
            st.download_button(
                "Download as Excel",
                data=to_excel_bytes(status_detail),
                file_name="detailed_status_breakdown.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_status_detail"
            )
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"<div class='footer' style='text-align: center; color: #cbd5e1;'>"
        f"Report generated on {date.today().strftime('%B %d, %Y')} | "
        f"Filtered: <strong style='color: #94a3b8;'>{filtered_len:,}</strong> products from <strong style='color: #94a3b8;'>{total_rows:,}</strong> total"
        f"</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

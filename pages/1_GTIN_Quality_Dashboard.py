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
    page_title="GTIN Quality Dashboard - MDM Analysis",
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
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

# Import necessary functions
INPUT_FILE = "all-products-prod-2026-01-13_15.30.30.xlsx"

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


def has_valid_gs1_check_digit(gtin: str, length: int) -> bool:
    """Validate GS1 check digit for GTIN-13 or GTIN-14."""
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


@st.cache_data
def load_and_classify_data():
    """Load and classify GTIN data."""
    df = pd.read_excel(INPUT_FILE, dtype=str)
    
    # Find GTIN-Outer column
    gtin_col = None
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if "gtin" in col_lower and "outer" in col_lower:
            gtin_col = col
            break
    
    if gtin_col is None:
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if col_lower in ["gtin-outer", "gtin_outer", "gtinouter"]:
                gtin_col = col
                break
    
    if gtin_col is None:
        st.error("GTIN-Outer column not found!")
        return None
    
    # Classify GTIN status
    df["gtin_status"] = df[gtin_col].apply(classify_gtin_status)
    df["gtin_outer_normalized"] = df[gtin_col].apply(normalize_gtin)
    
    return df, gtin_col


def check_password():
    """Returns `True` if the user had the correct password."""
    
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        # Get password from secrets (Streamlit Cloud) or use default for local
        try:
            correct_password = st.secrets["PASSWORD"]
        except (KeyError, FileNotFoundError):
            correct_password = "OSDTeam123"
        
        if st.session_state["password"] == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False
    
    # Simple CSS for clean login page
    st.markdown("""
        <style>
        .login-wrapper {
            padding: 2rem 0;
            display: flex;
            justify-content: center;
        }
        .login-card {
            max-width: 400px;
            width: 100%;
            text-align: center;
        }
        .login-title {
            color: #94a3b8;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            text-align: center;
        }
        .login-subtitle {
            color: #94a3b8;
            font-size: 0.9rem;
            text-align: center;
            margin-bottom: 1.5rem;
        }
        .stTextInput {
            max-width: 300px;
            margin: 0 auto;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Check if password is already correct - return immediately without showing anything
    if st.session_state.get("password_correct", False):
        return True
    
    # Show login form (first run or incorrect password)
    st.markdown('<div class="login-wrapper">', unsafe_allow_html=True)
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    
    st.markdown('<div class="login-title">GTIN Quality Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-subtitle">MDM Analysis Portal</div>', unsafe_allow_html=True)
    
    password = st.text_input(
        "Password",
        type="password",
        on_change=password_entered,
        key="password",
        label_visibility="visible"
    )
    
    # Check if password was just entered and was incorrect
    if "password" in st.session_state and st.session_state.get("password_correct", None) == False:
        st.error("Incorrect password")
    
    # If password was just entered correctly, rerun to refresh page
    if st.session_state.get("password_correct", False):
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    return False


def main():
    # Password protection
    if not check_password():
        st.stop()
    
    # Header
    st.markdown('<h1 class="main-header">📊 GTIN Quality Dashboard - MDM Analysis</h1>', unsafe_allow_html=True)
    
    # Display source file info
    st.markdown(f'<div style="text-align: center; color: #cbd5e1; margin-bottom: 1rem;">📁 Source file: <strong style="color: #94a3b8;">{INPUT_FILE}</strong></div>', unsafe_allow_html=True)
    
    # Save Analysis button - positioned right after source file with improved centered design
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])
    with col_btn2:
        if st.button("💾 Save Analysis and Report to Tracker", use_container_width=True, type="primary", key="save_quality_analysis_top"):
            st.session_state["save_quality_requested"] = True
    
    # Load data
    with st.spinner("Loading and analyzing data..."):
        result = load_and_classify_data()
        if result is None:
            return
        df, gtin_col = result
    
    total_rows = len(df)
    
    # Horizontal filters section
    st.markdown('<div class="filter-section">', unsafe_allow_html=True)
    st.markdown("### 🔍 Filters")
    
    # Legal Entity filter
    legal_entities = sorted(df["Legal Entity"].unique())
    
    # Initialize session state for selected entities
    if "selected_entities" not in st.session_state:
        st.session_state.selected_entities = legal_entities
    
    col1, col2 = st.columns([4, 1])
    with col1:
        selected_entities = st.multiselect(
            "**Select Legal Entities**",
            legal_entities,
            default=st.session_state.selected_entities,
            help="Select one or more Legal Entities to analyze"
        )
        # Update session state
        st.session_state.selected_entities = selected_entities
    
    with col2:
        # Stack buttons vertically, aligned with multiselect
        st.markdown('<div style="padding-top: 1.5rem;">', unsafe_allow_html=True)
        if st.button("🔄 Reset to All", use_container_width=True):
            st.session_state.selected_entities = legal_entities
            st.rerun()
        if st.button("Reset", use_container_width=True):
            st.session_state.selected_entities = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Ensure filter-section div is properly closed and remove empty elements
    st.markdown("""
    <script>
    (function() {
        setTimeout(function() {
            // Remove empty filter-section divs and their containers
            const containers = document.querySelectorAll('div[data-testid="stElementContainer"]');
            containers.forEach(container => {
                const filterSection = container.querySelector('div.filter-section, div[class*="filter-section"]');
                if (filterSection && (filterSection.textContent.trim() === '' || filterSection.children.length === 0)) {
                    container.style.display = 'none';
                    container.remove();
                }
            });
            
            // Force multiselect height to match Reset buttons
            const multiselect = document.querySelector('div[data-testid="stMultiSelect"]');
            const resetColumn = document.querySelector('div[data-testid="column"]:has(button)');
            if (multiselect && resetColumn) {
                const resetButtons = resetColumn.querySelectorAll('button');
                let totalHeight = 0;
                resetButtons.forEach(btn => {
                    totalHeight += btn.offsetHeight + 8; // 8px for gap
                });
                if (totalHeight > 0) {
                    multiselect.style.minHeight = totalHeight + 'px';
                    const multiselectInner = multiselect.querySelector('div > div');
                    if (multiselectInner) {
                        multiselectInner.style.minHeight = totalHeight + 'px';
                    }
                }
            }
        }, 100);
    })();
    </script>
    """, unsafe_allow_html=True)
    
    # Use session state for filtering
    selected_entities = st.session_state.selected_entities
    
    if not selected_entities:
        st.warning("⚠️ Please select at least one Legal Entity")
        return
    
    # Filter data
    df_filtered = df[df["Legal Entity"].isin(selected_entities)].copy()
    
    # Overall metrics
    st.markdown('<div class="section-header">📈 Overview</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    valid_statuses = ["8_digits", "13_digits", "14_digits"]
    
    total_valid = df_filtered[df_filtered["gtin_status"].isin(valid_statuses)].shape[0]
    total_invalid = df_filtered[df_filtered["gtin_status"] == "INVALID"].shape[0]
    total_generic = df_filtered[df_filtered["gtin_status"] == "GENERIC"].shape[0]
    # Accept both PLACEHOLDER and BLOCKED for backward compatibility with cached data
    total_blocked = df_filtered[df_filtered["gtin_status"].isin(["PLACEHOLDER", "BLOCKED"])].shape[0]
    total_8 = df_filtered[df_filtered["gtin_status"] == "8_digits"].shape[0]
    total_13 = df_filtered[df_filtered["gtin_status"] == "13_digits"].shape[0]
    total_14 = df_filtered[df_filtered["gtin_status"] == "14_digits"].shape[0]
    
    compliance_rate = (total_valid / len(df_filtered) * 100) if len(df_filtered) > 0 else 0
    invalid_rate = (total_invalid / len(df_filtered) * 100) if len(df_filtered) > 0 else 0
    
    with col1:
        st.metric("📦 Total Products", f"{len(df_filtered):,}")
    with col2:
        st.metric("✅ Valid GTINs", f"{total_valid:,}", f"{compliance_rate:.1f}%")
    with col3:
        st.metric("❌ Invalid GTINs", f"{total_invalid:,}", f"{invalid_rate:.1f}%")
    with col4:
        st.metric("⚠️ Generic GTINs", f"{total_generic:,}")
    with col5:
        st.metric("🚫 Placeholder GTINs (999...99)", f"{total_blocked:,}")
    with col6:
        st.metric("📊 Breakdown", f"{total_8}/{total_13}/{total_14}", help="8 digits / 13 digits / 14 digits")
    
    # Handle save button click (button is at the top, but logic is here after data is loaded)
    if st.session_state.get("save_quality_requested", False):
        st.session_state["save_quality_requested"] = False  # Reset flag
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).parent.parent))
        from tracker_utils import save_tracker_data
        
        # Prepare metrics by legal entity
        entity_metrics = []
        for entity in selected_entities:
            entity_df = df_filtered[df_filtered["Legal Entity"] == entity]
            entity_total = len(entity_df)
            entity_valid = entity_df[entity_df["gtin_status"].isin(valid_statuses)].shape[0]
            entity_invalid = entity_df[entity_df["gtin_status"] == "INVALID"].shape[0]
            entity_generic = entity_df[entity_df["gtin_status"] == "GENERIC"].shape[0]
            entity_blocked = entity_df[entity_df["gtin_status"].isin(["PLACEHOLDER", "BLOCKED"])].shape[0]
            entity_compliance = (entity_valid / entity_total * 100) if entity_total > 0 else 0
            
            entity_metrics.append({
                "legal_entity": entity,
                "total_products": entity_total,
                "valid_gtins": entity_valid,
                "invalid_gtins": entity_invalid,
                "generic_gtins": entity_generic,
                "placeholder_gtins": entity_blocked,
                "compliance_rate": round(entity_compliance, 2)
            })
        
        # Save to tracker
        tracker_entry = {
            "analysis_type": "quality",
            "legal_entities": selected_entities,
            "total_products": len(df_filtered),
            "total_valid": total_valid,
            "total_invalid": total_invalid,
            "total_generic": total_generic,
            "total_placeholder": total_blocked,
            "compliance_rate": round(compliance_rate, 2),
            "breakdown": {
                "8_digits": total_8,
                "13_digits": total_13,
                "14_digits": total_14
            },
            "entity_metrics": entity_metrics
        }
        
        if save_tracker_data(tracker_entry):
            st.success("✅ Analysis saved to tracker successfully!")
        else:
            st.error("❌ Error saving analysis to tracker")
    
    # Analysis by Legal Entity
    st.markdown('<div class="section-header">🏢 Analysis by Legal Entity</div>', unsafe_allow_html=True)
    
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
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Compliance Rate by Legal Entity")
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
        fig_compliance.update_layout(
            height=450, 
            showlegend=False,
            template='plotly_dark',
            plot_bgcolor='#1e293b',
            paper_bgcolor='#0f172a',
            font=dict(size=12, color='#f1f5f9'),
            xaxis=dict(gridcolor='#334155', gridwidth=1),
            yaxis=dict(showgrid=False)
        )
        st.plotly_chart(fig_compliance, use_container_width=True)
    
    with col2:
        st.markdown("#### 📈 GTIN Status Distribution")
        status_summary = df_filtered["gtin_status"].value_counts().reset_index()
        status_summary.columns = ["Status", "Count"]
        
        fig_pie = px.pie(
            status_summary,
            values="Count",
            names="Status",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_pie.update_traces(
            textposition='inside', 
            textinfo='percent+label',
            textfont=dict(size=11, color='#f1f5f9')
        )
        fig_pie.update_layout(
            height=450,
            template='plotly_dark',
            plot_bgcolor='#1e293b',
            paper_bgcolor='#0f172a',
            font=dict(size=12, color='#f1f5f9'),
            showlegend=True,
            legend=dict(
                orientation="v", 
                yanchor="middle", 
                y=0.5, 
                xanchor="left", 
                x=1.1,
                font=dict(color='#f1f5f9', size=11),
                bgcolor='rgba(30, 41, 59, 0.8)',
                bordercolor='#334155',
                borderwidth=1
            )
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # Stacked bar chart by Legal Entity
    st.markdown('<div class="section-header">📊 Status Details by Legal Entity</div>', unsafe_allow_html=True)
    
    # Prepare data for stacked bar - melt for better visualization
    status_cols = ["Valid GTINs", "Invalid GTINs", "Generic GTINs", "Placeholder GTINs (999...99)"]
    chart_data = analysis_df[["Legal Entity"] + status_cols].copy()
    chart_data = chart_data.sort_values("Legal Entity")
    
    # Melt for stacked bar
    chart_melted = pd.melt(
        chart_data,
        id_vars=["Legal Entity"],
        value_vars=status_cols,
        var_name="Status",
        value_name="Count"
    )
    
    fig_stacked = px.bar(
        chart_melted,
        x="Legal Entity",
        y="Count",
        color="Status",
        barmode='stack',
        labels={"Count": "Number of Products", "Legal Entity": "Legal Entity"},
        color_discrete_map={
            "Valid GTINs": "#2ecc71",
            "Invalid GTINs": "#e74c3c",
            "Generic GTINs": "#f39c12",
            "Placeholder GTINs (999...99)": "#34495e"
        }
    )
    fig_stacked.update_layout(
        height=500,
        template='plotly_dark',
        plot_bgcolor='#1e293b',
        paper_bgcolor='#0f172a',
        font=dict(size=12, color='#f1f5f9'),
        xaxis_title="Legal Entity",
        yaxis_title="Number of Products",
        legend=dict(
            orientation="h", 
            yanchor="bottom", 
            y=1.02, 
            xanchor="right", 
            x=1,
            font=dict(color='#f1f5f9', size=11),
            bgcolor='rgba(30, 41, 59, 0.8)',
            bordercolor='#334155',
            borderwidth=1
        ),
        xaxis={'categoryorder': 'total descending'}
    )
    fig_stacked.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#334155', griddash='dash')
    fig_stacked.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#334155', griddash='dash')
    st.plotly_chart(fig_stacked, use_container_width=True)
    
    # Detailed status breakdown
    st.markdown('<div class="section-header">🔍 Detailed Status Breakdown</div>', unsafe_allow_html=True)
    
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
    
    # ---------- EMAIL GENERATION FOR LEGAL ENTITIES ----------
    st.markdown('<div class="section-header">📧 Generate Email for Legal Entity</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        selected_entity_email = st.selectbox(
            "**Select Legal Entity**",
            legal_entities,
            key="entity_email",
            help="Select a Legal Entity to generate email and attachment"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        generate_email = st.button("📧 Generate Email & Report", use_container_width=True)
    
    if generate_email and selected_entity_email:
        # Filter data for selected entity
        entity_data = df[df["Legal Entity"] == selected_entity_email].copy()
        
        # Get Generic and Placeholder GTINs (accept both PLACEHOLDER and BLOCKED for backward compatibility)
        generic_blocked = entity_data[entity_data["gtin_status"].isin(["GENERIC", "PLACEHOLDER", "BLOCKED"])].copy()
        
        generic_gtins = generic_blocked[generic_blocked["gtin_status"] == "GENERIC"].copy()
        blocked_gtins = generic_blocked[generic_blocked["gtin_status"].isin(["PLACEHOLDER", "BLOCKED"])].copy()
        
        generic_count = len(generic_gtins)
        blocked_count = len(blocked_gtins)
        total_count = len(generic_blocked)
        
        if not generic_blocked.empty:
            # Prepare Excel file - ensure at least one sheet is always created
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Always create Summary sheet first (ensures at least one sheet exists)
                summary_data = {
                    "Legal Entity": [selected_entity_email],
                    "Total Generic GTINs": [generic_count],
                    "Total Placeholder GTINs (999...99)": [blocked_count],
                    "Total to Review": [total_count],
                    "Report Date": [date.today().strftime("%Y-%m-%d")]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)
                
                # Sheet 1: Generic GTINs (if any)
                if not generic_gtins.empty:
                    # Include all columns from original dataframe (raw data)
                    generic_gtins.to_excel(
                        writer, sheet_name="Generic GTINs", index=False
                    )
                
                # Sheet 2: Placeholder GTINs (if any)
                if not blocked_gtins.empty:
                    # Include all columns from original dataframe (raw data)
                    blocked_gtins.to_excel(
                        writer, sheet_name="Placeholder GTINs (999...99)", index=False
                    )
            
            output.seek(0)
            
            # Get recipients for this legal entity
            recipients = LEGAL_ENTITY_EMAILS.get(selected_entity_email, [])
            recipients_str = "; ".join(recipients) if recipients else ""
            
            # Extract first name from recipient email
            first_name = ""
            if recipients:
                # Get the first recipient's email
                first_email = recipients[0]
                # Extract name before @ or before dot
                if "@" in first_email:
                    name_part = first_email.split("@")[0]
                    # Remove hyphens and get first part
                    name_parts = name_part.replace("-", ".").split(".")
                    if name_parts:
                        first_name = name_parts[0].capitalize()
            
            # Build greeting with first name if available
            greeting = f"Hi {first_name}," if first_name else "Hi,"
            
            # Generate email template in English
            email_subject = f"Action Required: Review of Generic and Placeholder GTINs - {selected_entity_email}"
            
            email_body = f"""{greeting}

Your legal entity ({selected_entity_email}) has GTINs that require your attention and action.

**Summary:**
- Generic GTINs: {generic_count:,}
- Placeholder GTINs (999...99): {blocked_count:,}
- Total GTINs to review: {total_count:,}

**Action Required:**
Please review the attached Excel file which contains the detailed list of Generic and Placeholder GTINs (999...99) for your legal entity. These GTINs must be updated or replaced with valid product GTIN codes.

**Next Steps:**
1. Review the attached file
2. Identify the products associated with these GTINs
3. Update the GTINs with valid product codes
4. Confirm completion once updates are completed

If you have any questions or need assistance, please do not hesitate to contact the MDM team.

Best regards

---
Report generated on: {date.today().strftime("%B %d, %Y")}
"""
            
            # Create Excel filename
            excel_filename = f"GTIN_Review_{selected_entity_email.replace(' ', '_').replace('/', '_')}_{date.today().isoformat()}.xlsx"
            
            # Save Excel to temporary file for Outlook attachment
            temp_dir = tempfile.gettempdir()
            temp_excel_path = os.path.join(temp_dir, excel_filename)
            
            # Write Excel to temporary file
            output.seek(0)
            with open(temp_excel_path, 'wb') as f:
                f.write(output.read())
            
            # Reset output for Excel download
            output.seek(0)
            
            # Create .eml file for download (works on all platforms)
            msg = MIMEMultipart()
            msg['Subject'] = email_subject
            msg['From'] = "MDM Team <mdm@sysco.com>"
            if recipients:
                msg['To'] = ", ".join(recipients)
            else:
                msg['To'] = ""
            
            # Add body
            msg.attach(MIMEText(email_body, 'plain', 'utf-8'))
            
            # Add Excel attachment
            output.seek(0)
            attachment = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            attachment.set_payload(output.read())
            encoders.encode_base64(attachment)
            attachment.add_header('Content-Disposition', f'attachment; filename= {excel_filename}')
            msg.attach(attachment)
            
            # Convert to .eml format
            eml_output = io.BytesIO()
            eml_output.write(msg.as_bytes())
            eml_output.seek(0)
            output.seek(0)
            
            # Display email template with improved design
            st.markdown("### 📝 Email Template")
            
            # Subject and download icons in same row - subject left-aligned, icons on right
            col_subject, col_icons = st.columns([4, 1])
            
            with col_subject:
                st.text_input("Subject", value=email_subject, key="email_subject", label_visibility="visible")
            
            with col_icons:
                st.markdown("<br>", unsafe_allow_html=True)  # Spacing to align with input field
                col_dl_eml, col_dl_excel = st.columns(2)
                
                with col_dl_eml:
                    eml_filename = f"Email_Draft_{selected_entity_email.replace(' ', '_').replace('/', '_')}_{date.today().isoformat()}.eml"
                    st.download_button(
                        label="📥",
                        data=eml_output,
                        file_name=eml_filename,
                        mime="message/rfc822",
                        use_container_width=True,
                        key="download_eml_icon",
                        help="Download email with attachment (.eml)"
                    )
                
                with col_dl_excel:
                    st.download_button(
                        label="📊",
                        data=output,
                        file_name=excel_filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="download_excel_icon",
                        help="Download Excel file only"
                    )
            
            # Email body with better styling
            st.text_area("Email Body", value=email_body, height=300, key="email_body")
            
            # Show recipients info with better styling
            st.markdown("---")
            if recipients:
                st.markdown(f"""
                <div style="background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #94a3b8; margin: 1rem 0;">
                    <strong style="color: #94a3b8;">📧 Email Recipients for {selected_entity_email}:</strong><br>
                    <span style="color: #cbd5e1;">{recipients_str}</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #f39c12; margin: 1rem 0;">
                    <strong style="color: #f39c12;">⚠️ No email recipients configured for {selected_entity_email}</strong><br>
                    <span style="color: #cbd5e1;">Please add recipients manually when opening the .eml file in Outlook.</span>
                </div>
                """, unsafe_allow_html=True)
            
            # Display preview
            st.markdown("### 📊 Report Preview")
            st.info(f"**{selected_entity_email}**: {generic_count:,} Generic GTINs, {blocked_count:,} Placeholder GTINs (999...99)")
            
            if not generic_gtins.empty:
                st.markdown("#### Generic GTINs Sample (first 10)")
                preview_cols = ["SUPC", "Local Product Description", "Brand", "OSD Classification"]
                # Add gtin_status and gtin_outer_normalized for context
                additional_cols = ["gtin_outer_normalized", "gtin_status"]
                # Check which columns exist in the dataframe
                available_preview_cols = [col for col in preview_cols + additional_cols if col in generic_gtins.columns]
                if available_preview_cols:
                    st.dataframe(
                        generic_gtins[available_preview_cols].head(10),
                        use_container_width=True,
                        hide_index=True
                    )
            
            if not blocked_gtins.empty:
                st.markdown("#### Placeholder GTINs (999...99) Sample (first 10)")
                preview_cols = ["SUPC", "Local Product Description", "Brand", "OSD Classification"]
                # Add gtin_status and gtin_outer_normalized for context
                additional_cols = ["gtin_outer_normalized", "gtin_status"]
                # Check which columns exist in the dataframe
                available_preview_cols = [col for col in preview_cols + additional_cols if col in blocked_gtins.columns]
                if available_preview_cols:
                    st.dataframe(
                        blocked_gtins[available_preview_cols].head(10),
                        use_container_width=True,
                        hide_index=True
                    )
        else:
            st.success(f"✅ **{selected_entity_email}** has no Generic or Placeholder GTINs. No action required!")
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"<div class='footer' style='text-align: center; color: #cbd5e1;'>"
        f"📅 Report generated on {date.today().strftime('%B %d, %Y')} | "
        f"Total: <strong style='color: #94a3b8;'>{total_rows:,}</strong> products analyzed"
        f"</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path
from datetime import date

# Configuration de la page
st.set_page_config(
    page_title="GTIN Quality Dashboard - MDM Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS personnalisé pour un look professionnel avec thème sombre
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: 700;
        color: #60a5fa;
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
        color: #60a5fa;
        margin-top: 2rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #60a5fa;
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
    </style>
""", unsafe_allow_html=True)

# Import des fonctions de classification depuis gtin_analysis.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

# Import des fonctions nécessaires
INPUT_FILE = "all-products-prod-2026-01-13_15.30.30.xlsx"

# MDM Business Rules
GENERIC_GTINS = {
    "10000000000009", "20000000000009", "30000000000009", "40000000000009",
    "50000000000009", "60000000000009", "70000000000009", "80000000000009",
}
EXPLICIT_BLOCKED = "99999999999999"
VALID_LENGTHS = {8, 13, 14}


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
    Returns: INVALID, GENERIC, BLOCKED, 8_digits, 13_digits, 14_digits
    """
    if pd.isna(gtin_raw) or gtin_raw is None:
        return "INVALID"
    
    gtin = normalize_gtin(gtin_raw)
    if gtin is None:
        return "INVALID"
    
    if gtin == EXPLICIT_BLOCKED:
        return "BLOCKED"
    
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
        correct_password = st.secrets.get("PASSWORD", "OSDTeam123")
        
        if st.session_state["password"] == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False
    
    # Simple CSS for clean login page
    st.markdown("""
        <style>
        .login-wrapper {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 80vh;
        }
        .login-card {
            background-color: #1e293b;
            padding: 2.5rem;
            border-radius: 0.5rem;
            border: 1px solid #334155;
            max-width: 400px;
            width: 100%;
        }
        .login-title {
            color: #60a5fa;
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 0.25rem;
            text-align: center;
        }
        .login-subtitle {
            color: #94a3b8;
            font-size: 0.9rem;
            text-align: center;
            margin-bottom: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # First run, show input for password
    if "password_correct" not in st.session_state:
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
        
        if "password" in st.session_state and st.session_state.get("password_correct", None) == False:
            st.error("Incorrect password")
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return False
    
    # Password correct
    elif st.session_state["password_correct"]:
        return True
    
    # Password incorrect - show again
    else:
        st.markdown('<div class="login-wrapper">', unsafe_allow_html=True)
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        
        st.markdown('<div class="login-title">GTIN Quality Dashboard</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-subtitle">MDM Analysis Portal</div>', unsafe_allow_html=True)
        
        st.text_input(
            "Password",
            type="password",
            on_change=password_entered,
            key="password",
            label_visibility="visible"
        )
        
        st.error("Incorrect password")
        
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
    st.markdown(f'<div style="text-align: center; color: #cbd5e1; margin-bottom: 1.5rem;">📁 Source file: <strong style="color: #60a5fa;">{INPUT_FILE}</strong></div>', unsafe_allow_html=True)
    
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
    
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_entities = st.multiselect(
            "**Select Legal Entities**",
            legal_entities,
            default=legal_entities,
            help="Select one or more Legal Entities to analyze"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)  # Spacing
        if st.button("🔄 Reset to All", use_container_width=True):
            selected_entities = legal_entities
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
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
    total_blocked = df_filtered[df_filtered["gtin_status"] == "BLOCKED"].shape[0]
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
        st.metric("🚫 Blocked GTINs", f"{total_blocked:,}")
    with col6:
        st.metric("📊 Breakdown", f"{total_8}/{total_13}/{total_14}", help="8 digits / 13 digits / 14 digits")
    
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
        blocked_count = status_counts.get("BLOCKED", 0)
        
        compliance = (valid_count / total * 100) if total > 0 else 0
        
        analysis_data.append({
            "Legal Entity": entity,
            "Total Products": total,
            "Valid GTINs": valid_count,
            "Invalid GTINs": invalid_count,
            "Generic GTINs": generic_count,
            "Blocked GTINs": blocked_count,
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
    status_cols = ["Valid GTINs", "Invalid GTINs", "Generic GTINs", "Blocked GTINs"]
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
            "Blocked GTINs": "#34495e"
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
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"<div class='footer' style='text-align: center; color: #cbd5e1;'>"
        f"📅 Report generated on {date.today().strftime('%B %d, %Y')} | "
        f"Total: <strong style='color: #60a5fa;'>{total_rows:,}</strong> products analyzed"
        f"</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

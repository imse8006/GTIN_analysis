import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path
from datetime import date
import io

# Import shared functions and constants
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

# Page configuration
st.set_page_config(
    page_title="GTIN Duplicate Analysis - MDM",
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

INPUT_FILE = "all-products-prod-2026-01-13_15.30.30.xlsx"


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
def load_duplicate_data():
    """Load data and find GTIN Outer and Inner columns."""
    df = pd.read_excel(INPUT_FILE, dtype=str)
    
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
        return None, None, None
    
    if gtin_inner_col is None:
        st.warning("GTIN-Inner column not found! Only Outer duplicates will be analyzed.")
    
    # Normalize GTINs
    df["gtin_outer_normalized"] = df[gtin_outer_col].apply(normalize_gtin)
    if gtin_inner_col:
        df["gtin_inner_normalized"] = df[gtin_inner_col].apply(normalize_gtin)
    else:
        df["gtin_inner_normalized"] = None
    
    return df, gtin_outer_col, gtin_inner_col


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


def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        # Get password from secrets (Streamlit Cloud) or use default for local
        try:
            correct_password = st.secrets["PASSWORD"]
        except (KeyError, FileNotFoundError):
            correct_password = "OSDTeam123"
        
        if st.session_state["password"] == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    
    if "password_correct" not in st.session_state:
        st.markdown('<div style="text-align: center; padding: 2rem;">', unsafe_allow_html=True)
        st.markdown('<div style="color: #94a3b8; font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem;">GTIN Duplicate Analysis</div>', unsafe_allow_html=True)
        password = st.text_input("Password", type="password", on_change=password_entered, key="password", label_visibility="visible")
        if "password" in st.session_state and st.session_state.get("password_correct", None) == False:
            st.error("Incorrect password")
        st.markdown('</div>', unsafe_allow_html=True)
        if st.session_state.get("password_correct", False):
            st.rerun()
        return False
    
    if st.session_state.get("password_correct", False):
        return True
    return False


def main():
    # Password protection
    if not check_password():
        st.stop()
    
    # Header
    st.markdown('<h1 class="main-header">🔍 GTIN Duplicate Analysis</h1>', unsafe_allow_html=True)
    st.markdown(f'<div style="text-align: center; color: #cbd5e1; margin-bottom: 0.5rem;">📁 Source file: <strong style="color: #94a3b8;">{INPUT_FILE}</strong></div>', unsafe_allow_html=True)
    
    # Save Analysis button - positioned right after source file with improved design
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])
    with col_btn2:
        save_button_clicked = st.button(
            "💾 Save Analysis and Report to Tracker",
            use_container_width=True,
            type="primary",
            key="save_duplicate_analysis_top"
        )
        if save_button_clicked:
            st.session_state["save_duplicate_requested"] = True
    
    st.markdown("<br>", unsafe_allow_html=True)  # Spacing
    
    # Load data
    with st.spinner("Loading data and analyzing duplicates..."):
        result = load_duplicate_data()
        if result[0] is None:
            return
        df, gtin_outer_col, gtin_inner_col = result
    
    total_rows = len(df)
    
    # Analyze duplicates
    duplicate_results = analyze_duplicates(df, gtin_outer_col, gtin_inner_col)
    
    # Overview Metrics
    st.markdown('<div class="section-header">📊 Overview</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📦 Total Products", f"{total_rows:,}")
    
    with col2:
        outer_dup = duplicate_results["outer"]["total_duplicates"]
        st.metric("🔄 GTIN Outer Duplicates", f"{outer_dup:,}", 
                 f"{outer_dup/total_rows*100:.1f}%" if total_rows > 0 else "0%")
    
    with col3:
        if duplicate_results["inner"]:
            inner_dup = duplicate_results["inner"]["total_duplicates"]
            st.metric("🔄 GTIN Inner Duplicates", f"{inner_dup:,}",
                     f"{inner_dup/total_rows*100:.1f}%" if total_rows > 0 else "0%")
        else:
            st.metric("🔄 GTIN Inner Duplicates", "N/A", "Column not found")
    
    with col4:
        if duplicate_results["cross"]:
            cross_dup = duplicate_results["cross"]["unique_cross_gtins"]
            st.metric("🔀 Cross Duplicates", f"{cross_dup:,}",
                     f"{duplicate_results['cross']['total_records']:,} records")
        else:
            st.metric("🔀 Cross Duplicates", "N/A", "Inner column not found")
    
    # Handle save button click (button is at the top, but logic is here after data is loaded)
    if st.session_state.get("save_duplicate_requested", False):
        st.session_state["save_duplicate_requested"] = False  # Reset flag
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).parent.parent))
        from tracker_utils import save_tracker_data
        
        # Prepare duplicate metrics
        tracker_entry = {
            "analysis_type": "duplicate",
            "total_products": total_rows,
            "outer_duplicates": duplicate_results["outer"]["total_duplicates"],
            "outer_unique_duplicated": duplicate_results["outer"]["unique_duplicated_gtins"],
            "inner_duplicates": duplicate_results["inner"]["total_duplicates"] if duplicate_results["inner"] else 0,
            "inner_unique_duplicated": duplicate_results["inner"]["unique_duplicated_gtins"] if duplicate_results["inner"] else 0,
            "cross_duplicates": duplicate_results["cross"]["unique_cross_gtins"] if duplicate_results["cross"] else 0,
            "cross_total_records": duplicate_results["cross"]["total_records"] if duplicate_results["cross"] else 0,
            "has_inner_column": gtin_inner_col is not None
        }
        
        if save_tracker_data(tracker_entry):
            st.success("✅ Analysis saved to tracker successfully!")
        else:
            st.error("❌ Error saving analysis to tracker")
    
    # Detailed Analysis
    st.markdown('<div class="section-header">📋 Detailed Analysis</div>', unsafe_allow_html=True)
    
    # Tabs for different duplicate types
    tab1, tab2, tab3 = st.tabs(["GTIN Outer Duplicates", "GTIN Inner Duplicates", "Cross Duplicates"])
    
    with tab1:
        st.markdown("#### GTIN Outer Duplicates")
        outer_df = duplicate_results["outer"]["duplicate_df"]
        
        if len(outer_df) > 0:
            # Summary by GTIN
            outer_summary = outer_df.groupby("gtin_outer_normalized").agg({
                "Legal Entity": "count",
                "SUPC": lambda x: ", ".join(x.dropna().astype(str).unique()[:5]) if "SUPC" in outer_df.columns else "N/A"
            }).reset_index()
            outer_summary.columns = ["GTIN Outer", "Duplicate Count", "Sample SUPCs"]
            outer_summary = outer_summary.sort_values("Duplicate Count", ascending=False)
            
            st.markdown(f"**Found {duplicate_results['outer']['unique_duplicated_gtins']} unique GTINs with duplicates**")
            st.dataframe(outer_summary, use_container_width=True, hide_index=True)
            
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
    
    with tab2:
        st.markdown("#### GTIN Inner Duplicates")
        
        if duplicate_results["inner"]:
            inner_df = duplicate_results["inner"]["duplicate_df"]
            
            if len(inner_df) > 0:
                # Summary by GTIN
                inner_summary = inner_df.groupby("gtin_inner_normalized").agg({
                    "Legal Entity": "count",
                    "SUPC": lambda x: ", ".join(x.dropna().astype(str).unique()[:5]) if "SUPC" in inner_df.columns else "N/A"
                }).reset_index()
                inner_summary.columns = ["GTIN Inner", "Duplicate Count", "Sample SUPCs"]
                inner_summary = inner_summary.sort_values("Duplicate Count", ascending=False)
                
                st.markdown(f"**Found {duplicate_results['inner']['unique_duplicated_gtins']} unique GTINs with duplicates**")
                st.dataframe(inner_summary, use_container_width=True, hide_index=True)
                
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
    
    with tab3:
        st.markdown("#### Cross Duplicates (GTIN appears in both Outer and Inner)")
        
        if duplicate_results["cross"]:
            cross_df = duplicate_results["cross"]["cross_df"]
            
            if len(cross_df) > 0:
                st.markdown(f"**Found {duplicate_results['cross']['unique_cross_gtins']} GTINs that appear in both Outer and Inner columns**")
                
                # Summary
                cross_summary = []
                for gtin in duplicate_results["cross"]["gtin_list"][:50]:  # Limit to first 50
                    outer_count = len(cross_df[cross_df["gtin_outer_normalized"] == gtin])
                    inner_count = len(cross_df[cross_df["gtin_inner_normalized"] == gtin])
                    cross_summary.append({
                        "GTIN": gtin,
                        "As Outer": outer_count,
                        "As Inner": inner_count,
                        "Total Records": outer_count + inner_count
                    })
                
                if cross_summary:
                    cross_summary_df = pd.DataFrame(cross_summary)
                    st.dataframe(cross_summary_df, use_container_width=True, hide_index=True)
                
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
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"<div style='text-align: center; color: #cbd5e1; padding: 1rem;'>"
        f"📅 Analysis generated on {date.today().strftime('%B %d, %Y')} | "
        f"Total: <strong style='color: #94a3b8;'>{total_rows:,}</strong> products analyzed"
        f"</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

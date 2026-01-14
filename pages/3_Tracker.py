import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path
from datetime import datetime, date
import sys

# Import tracker utilities
sys.path.append(str(Path(__file__).parent.parent))
from tracker_utils import (
    load_tracker_data,
    get_quality_tracker_data,
    get_duplicate_tracker_data
)

# Page configuration
st.set_page_config(
    page_title="GTIN Tracker - MDM",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Use same CSS as main dashboard
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
    .section-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #60a5fa;
        margin-top: 2rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #60a5fa;
    }
    .stMetric {
        background-color: #1e293b;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        border: 1px solid #334155;
    }
    </style>
""", unsafe_allow_html=True)


def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
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
        st.markdown('<div style="color: #60a5fa; font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem;">GTIN Tracker</div>', unsafe_allow_html=True)
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
    st.markdown('<h1 class="main-header">📈 GTIN Quality & Duplicate Tracker</h1>', unsafe_allow_html=True)
    
    # Load tracker data
    all_data = load_tracker_data()
    
    if not all_data:
        st.info("ℹ️ No tracker data available yet. Save analyses from the Quality Dashboard or Duplicate Analysis pages to start tracking.")
        return
    
    # Overview metrics
    st.markdown('<div class="section-header">📊 Tracker Overview</div>', unsafe_allow_html=True)
    
    quality_data = get_quality_tracker_data()
    duplicate_data = get_duplicate_tracker_data()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Quality Analyses", len(quality_data))
    
    with col2:
        st.metric("🔍 Duplicate Analyses", len(duplicate_data))
    
    with col3:
        if quality_data:
            latest_quality = quality_data[-1]
            st.metric("📅 Latest Quality", latest_quality.get("date", "N/A"))
        else:
            st.metric("📅 Latest Quality", "N/A")
    
    with col4:
        if duplicate_data:
            latest_duplicate = duplicate_data[-1]
            st.metric("📅 Latest Duplicate", latest_duplicate.get("date", "N/A"))
        else:
            st.metric("📅 Latest Duplicate", "N/A")
    
    # Quality Tracking Section
    st.markdown('<div class="section-header">📈 GTIN Quality Evolution</div>', unsafe_allow_html=True)
    
    if quality_data:
        # Filter by Legal Entity
        all_entities = set()
        for entry in quality_data:
            all_entities.update(entry.get("legal_entities", []))
        all_entities = sorted(list(all_entities))
        
        selected_entity_filter = st.selectbox(
            "**Filter by Legal Entity** (or 'All' for global view)",
            ["All"] + all_entities,
            key="quality_entity_filter"
        )
        
        # Filter data
        if selected_entity_filter == "All":
            filtered_quality_data = quality_data
            chart_title = "GTIN Quality Evolution (All Legal Entities)"
        else:
            filtered_quality_data = get_quality_tracker_data(selected_entity_filter)
            chart_title = f"GTIN Quality Evolution - {selected_entity_filter}"
        
        if filtered_quality_data:
            # Prepare data for charts
            chart_df = pd.DataFrame([
                {
                    "Date": entry.get("date", ""),
                    "Timestamp": entry.get("timestamp", ""),
                    "Compliance Rate (%)": entry.get("compliance_rate", 0),
                    "Total Products": entry.get("total_products", 0),
                    "Valid GTINs": entry.get("total_valid", 0),
                    "Invalid GTINs": entry.get("total_invalid", 0),
                    "Generic GTINs": entry.get("total_generic", 0),
                    "Placeholder GTINs": entry.get("total_placeholder", 0),
                }
                for entry in filtered_quality_data
            ])
            
            # Convert date to datetime for proper sorting
            chart_df["Date"] = pd.to_datetime(chart_df["Date"])
            chart_df = chart_df.sort_values("Date")
            
            # Charts
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.markdown("#### Compliance Rate Evolution")
                fig_compliance = px.line(
                    chart_df,
                    x="Date",
                    y="Compliance Rate (%)",
                    title="Compliance Rate Over Time",
                    markers=True
                )
                fig_compliance.update_traces(line_color='#60a5fa', line_width=3)
                fig_compliance.update_layout(
                    height=400,
                    template='plotly_dark',
                    plot_bgcolor='#1e293b',
                    paper_bgcolor='#0f172a',
                    font=dict(size=12, color='#f1f5f9'),
                    xaxis=dict(gridcolor='#334155'),
                    yaxis=dict(gridcolor='#334155')
                )
                st.plotly_chart(fig_compliance, use_container_width=True)
            
            with col_chart2:
                st.markdown("#### GTIN Status Distribution Over Time")
                status_df = chart_df.melt(
                    id_vars=["Date"],
                    value_vars=["Valid GTINs", "Invalid GTINs", "Generic GTINs", "Placeholder GTINs"],
                    var_name="Status",
                    value_name="Count"
                )
                fig_status = px.area(
                    status_df,
                    x="Date",
                    y="Count",
                    color="Status",
                    title="GTIN Status Distribution Over Time",
                    color_discrete_map={
                        "Valid GTINs": "#2ecc71",
                        "Invalid GTINs": "#e74c3c",
                        "Generic GTINs": "#f39c12",
                        "Placeholder GTINs": "#34495e"
                    }
                )
                fig_status.update_layout(
                    height=400,
                    template='plotly_dark',
                    plot_bgcolor='#1e293b',
                    paper_bgcolor='#0f172a',
                    font=dict(size=12, color='#f1f5f9'),
                    xaxis=dict(gridcolor='#334155'),
                    yaxis=dict(gridcolor='#334155')
                )
                st.plotly_chart(fig_status, use_container_width=True)
            
            # Entity-specific metrics if filtered
            if selected_entity_filter != "All" and filtered_quality_data:
                st.markdown(f"#### Detailed Metrics for {selected_entity_filter}")
                entity_details = []
                for entry in filtered_quality_data:
                    for entity_metric in entry.get("entity_metrics", []):
                        if entity_metric.get("legal_entity") == selected_entity_filter:
                            entity_details.append({
                                "Date": entry.get("date", ""),
                                "Time": entry.get("time", ""),
                                "Total Products": entity_metric.get("total_products", 0),
                                "Valid GTINs": entity_metric.get("valid_gtins", 0),
                                "Invalid GTINs": entity_metric.get("invalid_gtins", 0),
                                "Generic GTINs": entity_metric.get("generic_gtins", 0),
                                "Placeholder GTINs": entity_metric.get("placeholder_gtins", 0),
                                "Compliance Rate (%)": entity_metric.get("compliance_rate", 0)
                            })
                
                if entity_details:
                    entity_df = pd.DataFrame(entity_details)
                    entity_df = entity_df.sort_values("Date")
                    st.dataframe(entity_df, use_container_width=True, hide_index=True)
        else:
            st.info(f"ℹ️ No quality data available for {selected_entity_filter}")
    else:
        st.info("ℹ️ No quality tracking data available yet. Save a quality analysis to start tracking.")
    
    # Duplicate Tracking Section
    st.markdown('<div class="section-header">🔍 Duplicate Evolution</div>', unsafe_allow_html=True)
    
    if duplicate_data:
        # Prepare data for charts
        dup_chart_df = pd.DataFrame([
            {
                "Date": entry.get("date", ""),
                "Timestamp": entry.get("timestamp", ""),
                "Outer Duplicates": entry.get("outer_duplicates", 0),
                "Outer Unique Duplicated": entry.get("outer_unique_duplicated", 0),
                "Inner Duplicates": entry.get("inner_duplicates", 0),
                "Inner Unique Duplicated": entry.get("inner_unique_duplicated", 0),
                "Cross Duplicates": entry.get("cross_duplicates", 0),
                "Total Products": entry.get("total_products", 0)
            }
            for entry in duplicate_data
        ])
        
        # Convert date to datetime for proper sorting
        dup_chart_df["Date"] = pd.to_datetime(dup_chart_df["Date"])
        dup_chart_df = dup_chart_df.sort_values("Date")
        
        # Charts
        col_dup1, col_dup2 = st.columns(2)
        
        with col_dup1:
            st.markdown("#### Duplicate Counts Over Time")
            dup_melted = dup_chart_df.melt(
                id_vars=["Date"],
                value_vars=["Outer Duplicates", "Inner Duplicates", "Cross Duplicates"],
                var_name="Duplicate Type",
                value_name="Count"
            )
            fig_dup = px.line(
                dup_melted,
                x="Date",
                y="Count",
                color="Duplicate Type",
                title="Duplicate Counts Evolution",
                markers=True,
                color_discrete_map={
                    "Outer Duplicates": "#e74c3c",
                    "Inner Duplicates": "#f39c12",
                    "Cross Duplicates": "#9b59b6"
                }
            )
            fig_dup.update_layout(
                height=400,
                template='plotly_dark',
                plot_bgcolor='#1e293b',
                paper_bgcolor='#0f172a',
                font=dict(size=12, color='#f1f5f9'),
                xaxis=dict(gridcolor='#334155'),
                yaxis=dict(gridcolor='#334155')
            )
            st.plotly_chart(fig_dup, use_container_width=True)
        
        with col_dup2:
            st.markdown("#### Unique Duplicated GTINs Over Time")
            unique_dup_melted = dup_chart_df.melt(
                id_vars=["Date"],
                value_vars=["Outer Unique Duplicated", "Inner Unique Duplicated"],
                var_name="Type",
                value_name="Count"
            )
            fig_unique = px.bar(
                unique_dup_melted,
                x="Date",
                y="Count",
                color="Type",
                title="Unique Duplicated GTINs Evolution",
                barmode='group',
                color_discrete_map={
                    "Outer Unique Duplicated": "#e74c3c",
                    "Inner Unique Duplicated": "#f39c12"
                }
            )
            fig_unique.update_layout(
                height=400,
                template='plotly_dark',
                plot_bgcolor='#1e293b',
                paper_bgcolor='#0f172a',
                font=dict(size=12, color='#f1f5f9'),
                xaxis=dict(gridcolor='#334155'),
                yaxis=dict(gridcolor='#334155')
            )
            st.plotly_chart(fig_unique, use_container_width=True)
        
        # Detailed table
        st.markdown("#### Duplicate Analysis History")
        display_dup_df = dup_chart_df[["Date", "Time", "Total Products", "Outer Duplicates", 
                                      "Outer Unique Duplicated", "Inner Duplicates", 
                                      "Inner Unique Duplicated", "Cross Duplicates"]].copy()
        st.dataframe(display_dup_df, use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ No duplicate tracking data available yet. Save a duplicate analysis to start tracking.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"<div style='text-align: center; color: #cbd5e1; padding: 1rem;'>"
        f"📅 Tracker updated on {date.today().strftime('%B %d, %Y')} | "
        f"Total entries: <strong style='color: #60a5fa;'>{len(all_data):,}</strong>"
        f"</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

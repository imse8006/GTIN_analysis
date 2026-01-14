"""
Main entry point for Streamlit multi-page app.
This file allows Streamlit to detect the pages/ directory automatically.
The actual dashboard is in pages/1_GTIN_Quality_Dashboard.py
"""

import streamlit as st

# Minimal page config - Streamlit will auto-detect pages/ directory
st.set_page_config(
    page_title="GTIN Analysis - MDM",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Redirect to main dashboard
st.switch_page("pages/1_GTIN_Quality_Dashboard.py")

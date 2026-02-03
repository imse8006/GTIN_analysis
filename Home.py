"""
Main entry point for Streamlit multi-page app.
This file allows Streamlit to detect the pages/ directory automatically.
Redirects to the Documentation page by default.
"""

import streamlit as st

# Minimal page config - Streamlit will auto-detect pages/ directory
st.set_page_config(
    page_title="GTIN Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Redirect to Documentation page
st.switch_page("pages/0_Documentation.py")

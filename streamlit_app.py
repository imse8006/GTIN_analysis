# Main entry point for Streamlit Cloud
# This file allows Streamlit to automatically detect pages in the pages/ directory
# and create multi-page navigation

import streamlit as st

# Page configuration
st.set_page_config(
    page_title="GTIN Analysis - MDM",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Redirect to the main dashboard page
# Streamlit will automatically detect pages/1_GTIN_Quality_Dashboard.py and pages/2_Duplicate_Analysis.py
# and create navigation in the sidebar

# Import and run the main dashboard
import sys
from pathlib import Path

# Add pages directory to path
pages_dir = Path(__file__).parent / "pages"
sys.path.insert(0, str(pages_dir))

# Import and run the main dashboard
from importlib import import_module
try:
    dashboard = import_module("1_GTIN_Quality_Dashboard")
    dashboard.main()
except Exception as e:
    st.error(f"Error loading dashboard: {str(e)}")
    st.info("Please ensure pages/1_GTIN_Quality_Dashboard.py exists")

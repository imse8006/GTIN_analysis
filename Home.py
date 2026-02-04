"""
Main entry point for Streamlit multi-page app.
Uses st.navigation to explicitly control which pages are displayed.
"""

import streamlit as st

# Page config
st.set_page_config(
    page_title="GTIN Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Explicit navigation - only show pages we want visible
# Note: _Generate_Email.py is excluded from navigation but still accessible via st.switch_page()
pages = [
    st.Page("pages/0_Documentation.py", title="Documentation", icon="📚"),
    st.Page("pages/1_GTIN_Quality_Dashboard.py", title="GTIN Quality Dashboard", icon="📊"),
    st.Page("pages/2_Duplicate_Analysis.py", title="Duplicate Analysis", icon="🔍"),
    st.Page("pages/4_Tracker.py", title="Tracker", icon="📈"),
    st.Page("pages/5_Generic_GTIN_Analysis.py", title="Generic GTIN Analysis", icon="🔢"),
]

# Create navigation
pg = st.navigation(pages)

# Run the selected page
pg.run()

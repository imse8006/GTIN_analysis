"""Shared login UI: same design on all pages."""
import streamlit as st

LOGIN_CSS = """
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
.login-form .stTextInput {
    max-width: 300px;
    margin: 0 auto;
}
</style>
"""

DEFAULT_SUBTITLE = "MDM Analysis Portal"


def render_login_header(title: str, subtitle: str = DEFAULT_SUBTITLE) -> None:
    """Render unified login page: CSS + wrapper + title + subtitle. Call before st.text_input(Password...)."""
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    st.markdown('<div class="login-wrapper">', unsafe_allow_html=True)
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="login-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="login-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def render_login_footer() -> None:
    """Close login wrapper divs. Call after the password form block."""
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

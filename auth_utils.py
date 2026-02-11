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

def render_login_header(title: str, subtitle: str = "") -> None:
    """Render unified login page: CSS + wrapper + title (+ optional subtitle). Call before st.text_input(Password...)."""
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    st.markdown('<div class="login-wrapper">', unsafe_allow_html=True)
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="login-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="login-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def render_login_footer() -> None:
    """Close login wrapper divs. Call after the password form block."""
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_login_form(title: str, subtitle: str = "", password_key: str = "password") -> bool:
    """
    Full login flow: form in a placeholder, on success replace form with "Connexion réussie" then rerun
    so the password field is never left visible. Returns True if already logged in or just logged in.
    """
    def password_entered():
        try:
            correct_password = st.secrets["PASSWORD"]
        except (KeyError, FileNotFoundError):
            correct_password = "OSDTeam123"
        entered = st.session_state.get(password_key, "")
        if entered == correct_password:
            st.session_state["password_correct"] = True
            if password_key in st.session_state:
                del st.session_state[password_key]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    ph = st.empty()
    with ph.container():
        render_login_header(title, subtitle)
        st.text_input("Password", type="password", key=password_key, on_change=password_entered, label_visibility="visible")
        # Only show error if password was actually entered and was incorrect
        # Check if password_correct was explicitly set to False (not just missing)
        if password_key in st.session_state and st.session_state.get(password_key) != "" and st.session_state.get("password_correct") is False:
            st.error("Incorrect password")

    if st.session_state.get("password_correct", False):
        ph.empty()
        with ph.container():
            render_login_header(title, subtitle)
            st.success("Connexion réussie.")
        render_login_footer()
        st.rerun()

    render_login_footer()
    return False

"""
Authentication utilities for Streamlit dashboard.

Usage:
    from src.dashboard.utils.auth import require_authentication

    # Add at the top of your app
    require_authentication()
"""

import streamlit as st


def check_password():
    """
    Returns `True` if user entered correct password.

    Configure password in Streamlit Secrets (Settings → Secrets):
        password = "your_password_here"

    Or use environment variable:
        PASSWORD=your_password streamlit run app.py
    """

    def password_entered():
        """Called when password is submitted."""
        # Get configured password from secrets or fallback to env
        correct_password = st.secrets.get("password", "")

        if not correct_password:
            st.error("⚠️ No password configured! Add to Streamlit Secrets.")
            return

        if st.session_state["password"] == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    # Already authenticated
    if st.session_state.get("password_correct", False):
        return True

    # Show login form
    st.markdown("# 🔐 Market Scraper - Login")
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.text_input(
            "Password",
            type="password",
            on_change=password_entered,
            key="password",
            help="Entre em contato com o administrador para obter acesso"
        )

        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("😕 Senha incorreta. Tente novamente.")

    st.markdown("---")
    st.caption("📊 **Market Scraper Dashboard** - Análise de preços de supermercados")

    return False


def require_authentication():
    """
    Require authentication before allowing access to the app.

    Call this function at the top of your Streamlit app:

        from src.dashboard.utils.auth import require_authentication
        require_authentication()

    If user is not authenticated, shows login screen and stops execution.
    """
    if not check_password():
        st.stop()


def logout():
    """
    Logout current user.

    Usage:
        if st.sidebar.button("Logout"):
            logout()
    """
    st.session_state["password_correct"] = False
    st.rerun()


def get_user_info():
    """
    Get current user information.

    Returns:
        dict: User info (currently just authenticated status)
    """
    return {
        "authenticated": st.session_state.get("password_correct", False),
        "login_time": st.session_state.get("login_time"),
    }

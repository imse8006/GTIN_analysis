import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import date
import io
import tempfile
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import sys
from auth_utils import render_login_header, render_login_footer

# Page configuration
st.set_page_config(
    page_title="Generate Email - MDM",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Path and config
sys.path.append(str(Path(__file__).parent.parent))
INPUT_FILE = "all-products-prod-2026-01-22_15.44.25.xlsx"

# MDM Business Rules
GENERIC_GTINS = {
    "10000000000009", "20000000000009", "30000000000009", "40000000000009",
    "50000000000009", "60000000000009", "70000000000009", "80000000000009",
}
EXPLICIT_BLOCKED = "99999999999999"
VALID_LENGTHS = {8, 13, 14}

LEGAL_ENTITY_EMAILS = {
    "Brakes": ["samantha.smith@sysco.com"],
    "Sysco ROI": ["glen-timperley@sysco.com", "sarah-graham@sysco.com"],
    "Sysco NI": ["glen-timperley@sysco.com", "sarah-graham@sysco.com"],
    "Classic Drinks": ["glen-timperley@sysco.com", "sarah-graham@sysco.com"],
    "Ready Chef": ["glen-timperley@sysco.com", "sarah-graham@sysco.com"],
    "Menigo": ["paula.sterner@menigo.se"],
    "Fruktservice": ["paula.sterner@menigo.se"],
    "Servicestyckarna": ["paula.sterner@menigo.se"],
    "Ekofisk": ["paula.sterner@menigo.se"],
    "Fresh Direct": ["ben.newby@sysco.com"],
    "KFF": ["joseph.maczka@sysco.com"],
    "Medina": ["joseph.maczka@sysco.com"],
    "France": ["severine.branciard@sysco.com"],
    "LAG": ["severine.branciard@sysco.com"],
}


def normalize_gtin(value):
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
    if length == 8:
        return True
    if length not in (13, 14) or not gtin.isdigit():
        return False
    digits = [int(d) for d in gtin]
    body, check_digit = digits[:-1], digits[-1]
    total = 0
    for i, d in enumerate(reversed(body), start=1):
        multiplier = 1 if (length == 13 and i % 2 == 1) or (length == 14 and i % 2 == 0) else 3
        total += d * multiplier
    calc = (10 - (total % 10)) % 10
    return calc == check_digit


def classify_gtin_status(gtin_raw):
    if pd.isna(gtin_raw) or gtin_raw is None:
        return "INVALID"
    gtin = normalize_gtin(gtin_raw)
    if gtin is None:
        return "INVALID"
    if gtin == EXPLICIT_BLOCKED:
        return "PLACEHOLDER"
    if gtin in GENERIC_GTINS:
        return "GENERIC"
    if not gtin.isdigit():
        return "INVALID"
    length = len(gtin)
    if length not in VALID_LENGTHS:
        return "INVALID"
    if not has_valid_gs1_check_digit(gtin, length):
        return "INVALID"
    if length == 8:
        return "8_digits"
    elif length == 13:
        return "13_digits"
    else:
        return "14_digits"


@st.cache_data
def load_and_classify_data():
    df = pd.read_excel(INPUT_FILE, dtype=str)
    gtin_col = None
    for col in df.columns:
        c = str(col).lower().strip()
        if "gtin" in c and "outer" in c:
            gtin_col = col
            break
    if gtin_col is None:
        for col in df.columns:
            if str(col).lower().strip() in ["gtin-outer", "gtin_outer", "gtinouter"]:
                gtin_col = col
                break
    if gtin_col is None:
        st.error("GTIN-Outer column not found!")
        return None, None
    df["gtin_status"] = df[gtin_col].apply(classify_gtin_status)
    df["gtin_outer_normalized"] = df[gtin_col].apply(normalize_gtin)
    return df, gtin_col


def check_password():
    def password_entered():
        try:
            correct_password = st.secrets["PASSWORD"]
        except (KeyError, FileNotFoundError):
            correct_password = "OSDTeam123"
        entered = st.session_state.get("password", "")
        if entered == correct_password:
            st.session_state["password_correct"] = True
            if "password" in st.session_state:
                del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True
    render_login_header("Generate Email")
    st.text_input("Password", type="password", on_change=password_entered, key="password", label_visibility="visible")
    if "password" in st.session_state and st.session_state.get("password_correct") is False:
        st.error("Incorrect password")
    if st.session_state.get("password_correct", False):
        render_login_footer()
        st.rerun()
    render_login_footer()
    return False


def main():
    if not check_password():
        return

    st.markdown('<h1 class="main-header">📧 Generate Email for Legal Entity</h1>', unsafe_allow_html=True)
    st.markdown(f'<div style="text-align: center; color: #cbd5e1; margin-bottom: 1rem;">📁 Source file: <strong style="color: #94a3b8;">{INPUT_FILE}</strong></div>', unsafe_allow_html=True)

    st.markdown("""
    <style>
    .main-header { font-size: 3rem; font-weight: 700; color: #94a3b8; text-align: center; margin-bottom: 1rem; padding: 1rem 0; }
    .section-header { font-size: 1.5rem; font-weight: 600; color: #94a3b8; margin-top: 2rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #475569; }
    </style>
    """, unsafe_allow_html=True)

    with st.spinner("Loading data..."):
        result = load_and_classify_data()
        if result[0] is None:
            return
        df, _ = result

    legal_entities = sorted(df["Legal Entity"].unique())

    st.markdown('<div class="section-header">Select Legal Entity</div>', unsafe_allow_html=True)
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_entity_email = st.selectbox(
            "**Select Legal Entity**",
            legal_entities,
            key="entity_email",
            help="Select a Legal Entity to generate email and attachment"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        generate_email = st.button("📧 Generate Email & Report", use_container_width=True)

    if generate_email and selected_entity_email:
        entity_data = df[df["Legal Entity"] == selected_entity_email].copy()
        generic_blocked = entity_data[entity_data["gtin_status"].isin(["GENERIC", "PLACEHOLDER", "BLOCKED"])].copy()
        generic_gtins = generic_blocked[generic_blocked["gtin_status"] == "GENERIC"].copy()
        blocked_gtins = generic_blocked[generic_blocked["gtin_status"].isin(["PLACEHOLDER", "BLOCKED"])].copy()
        generic_count = len(generic_gtins)
        blocked_count = len(blocked_gtins)
        total_count = len(generic_blocked)

        if not generic_blocked.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                pd.DataFrame({
                    "Legal Entity": [selected_entity_email],
                    "Total Generic GTINs": [generic_count],
                    "Total Placeholder GTINs (999...99)": [blocked_count],
                    "Total to Review": [total_count],
                    "Report Date": [date.today().strftime("%Y-%m-%d")]
                }).to_excel(writer, sheet_name="Summary", index=False)
                if not generic_gtins.empty:
                    generic_gtins.to_excel(writer, sheet_name="Generic GTINs", index=False)
                if not blocked_gtins.empty:
                    blocked_gtins.to_excel(writer, sheet_name="Placeholder GTINs (999...99)", index=False)

            output.seek(0)
            recipients = LEGAL_ENTITY_EMAILS.get(selected_entity_email, [])
            recipients_str = "; ".join(recipients) if recipients else ""

            first_name = ""
            if recipients and "@" in recipients[0]:
                first_name = recipients[0].split("@")[0].replace("-", ".").split(".")[0].capitalize()
            greeting = f"Hi {first_name}," if first_name else "Hi,"

            email_subject = f"Action Required: Review of Generic and Placeholder GTINs - {selected_entity_email}"
            email_body = f"""{greeting}

Your legal entity ({selected_entity_email}) has GTINs that require your attention and action.

**Summary:**
- Generic GTINs: {generic_count:,}
- Placeholder GTINs (999...99): {blocked_count:,}
- Total GTINs to review: {total_count:,}

**Action Required:**
Please review the attached Excel file which contains the detailed list of Generic and Placeholder GTINs (999...99) for your legal entity. These GTINs must be updated or replaced with valid product GTIN codes.

**Next Steps:**
1. Review the attached file
2. Identify the products associated with these GTINs
3. Update the GTINs with valid product codes
4. Confirm completion once updates are completed

If you have any questions or need assistance, please do not hesitate to contact the MDM team.

Best regards

---
Report generated on: {date.today().strftime("%B %d, %Y")}
"""

            excel_filename = f"GTIN_Review_{selected_entity_email.replace(' ', '_').replace('/', '_')}_{date.today().isoformat()}.xlsx"
            output.seek(0)

            msg = MIMEMultipart()
            msg['Subject'] = email_subject
            msg['From'] = "MDM Team <mdm@sysco.com>"
            msg['To'] = ", ".join(recipients) if recipients else ""
            msg.attach(MIMEText(email_body, 'plain', 'utf-8'))
            output.seek(0)
            attachment = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            attachment.set_payload(output.read())
            encoders.encode_base64(attachment)
            attachment.add_header('Content-Disposition', f'attachment; filename= {excel_filename}')
            msg.attach(attachment)
            eml_output = io.BytesIO()
            eml_output.write(msg.as_bytes())
            eml_output.seek(0)
            output.seek(0)

            st.markdown("### 📝 Email Template")
            col_subject, col_icons = st.columns([4, 1])
            with col_subject:
                st.text_input("Subject", value=email_subject, key="email_subject", label_visibility="visible")
            with col_icons:
                st.markdown("<br>", unsafe_allow_html=True)
                col_dl_eml, col_dl_excel = st.columns(2)
                with col_dl_eml:
                    st.download_button(label="📥", data=eml_output, file_name=f"Email_Draft_{selected_entity_email.replace(' ', '_').replace('/', '_')}_{date.today().isoformat()}.eml", mime="message/rfc822", use_container_width=True, key="download_eml_icon", help="Download email with attachment (.eml)")
                with col_dl_excel:
                    st.download_button(label="📊", data=output, file_name=excel_filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key="download_excel_icon", help="Download Excel file only")

            st.text_area("Email Body", value=email_body, height=300, key="email_body")
            st.markdown("---")
            if recipients:
                st.markdown(f'<div style="background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #94a3b8; margin: 1rem 0;"><strong style="color: #94a3b8;">📧 Email Recipients for {selected_entity_email}:</strong><br><span style="color: #cbd5e1;">{recipients_str}</span></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #f39c12; margin: 1rem 0;"><strong style="color: #f39c12;">⚠️ No email recipients configured for {selected_entity_email}</strong><br><span style="color: #cbd5e1;">Please add recipients manually when opening the .eml file in Outlook.</span></div>', unsafe_allow_html=True)

            st.markdown("### 📊 Report Preview")
            st.info(f"**{selected_entity_email}**: {generic_count:,} Generic GTINs, {blocked_count:,} Placeholder GTINs (999...99)")
            if not generic_gtins.empty:
                st.markdown("#### Generic GTINs Sample (first 10)")
                preview_cols = [c for c in ["SUPC", "Local Product Description", "Brand", "OSD Classification", "gtin_outer_normalized", "gtin_status"] if c in generic_gtins.columns]
                if preview_cols:
                    st.dataframe(generic_gtins[preview_cols].head(10), use_container_width=True, hide_index=True)
            if not blocked_gtins.empty:
                st.markdown("#### Placeholder GTINs (999...99) Sample (first 10)")
                preview_cols = [c for c in ["SUPC", "Local Product Description", "Brand", "OSD Classification", "gtin_outer_normalized", "gtin_status"] if c in blocked_gtins.columns]
                if preview_cols:
                    st.dataframe(blocked_gtins[preview_cols].head(10), use_container_width=True, hide_index=True)
        else:
            st.success(f"✅ **{selected_entity_email}** has no Generic or Placeholder GTINs. No action required!")

    st.markdown("---")
    st.markdown(f"<div style='text-align: center; color: #cbd5e1;'>📅 Report generated on {date.today().strftime('%B %d, %Y')} | Total: <strong style='color: #94a3b8;'>{len(df):,}</strong> products in source</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()

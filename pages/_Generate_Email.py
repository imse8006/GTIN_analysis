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
from auth_utils import render_login_form

# Page configuration
st.set_page_config(
    page_title="Generate Email",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Path and config
sys.path.append(str(Path(__file__).parent.parent))
from duplicate_analysis_backend import list_output_dates, list_email_reports, OUTPUTS_BASE

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


def check_password():
    return render_login_form("Generate Email")


def main():
    if not check_password():
        return

    st.markdown("""
    <style>
    .main-header { font-size: 3rem; font-weight: 700; color: #94a3b8; text-align: center; margin-bottom: 1rem; padding: 1rem 0; }
    .section-header { font-size: 1.5rem; font-weight: 600; color: #94a3b8; margin-top: 2rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #475569; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<h1 class="main-header">📧 Generate Email for Legal Entity</h1>', unsafe_allow_html=True)

    output_dates = list_output_dates()
    if not output_dates:
        st.info(f"No pre-computed results. Run the batch then reload. Results in `{OUTPUTS_BASE}/YYYY-MM-DD/`.")
        return

    date_options = [f"{d[0]} ({d[1]})" for d in output_dates]
    date_paths = {date_options[i]: output_dates[i][1] for i in range(len(output_dates))}
    selected_date_label = st.selectbox("**Extract date**", date_options, index=0, key="email_date")
    output_dir = date_paths[selected_date_label]

    email_reports = list_email_reports(output_dir)
    if not email_reports:
        st.warning("No email report for this date (email_reports/ folder is empty).")
        return

    entity_options = [e[0] for e in email_reports]
    entity_to_path = {e[0]: e[1] for e in email_reports}

    st.markdown(f'<div style="text-align: center; color: #cbd5e1; margin-bottom: 1rem;">📁 Source: <strong style="color: #94a3b8;">outputs</strong> (pre-generated reports by Legal Entity)</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-header">Select Legal Entity</div>', unsafe_allow_html=True)
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_entity_email = st.selectbox(
            "**Select Legal Entity**",
            entity_options,
            key="entity_email",
            help="Select a Legal Entity to download report and generate email"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)

    if selected_entity_email:
        report_path = entity_to_path[selected_entity_email]
        with open(report_path, "rb") as f:
            excel_bytes = f.read()
        try:
            summary_df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name="Summary", dtype=str)
            generic_count = int(summary_df["Total Generic GTINs"].iloc[0]) if "Total Generic GTINs" in summary_df.columns else 0
            blocked_count = int(summary_df["Total Placeholder GTINs (999...99)"].iloc[0]) if "Total Placeholder GTINs (999...99)" in summary_df.columns else 0
            total_count = int(summary_df["Total to Review"].iloc[0]) if "Total to Review" in summary_df.columns else 0
        except Exception:
            generic_count = blocked_count = total_count = 0

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
        msg = MIMEMultipart()
        msg['Subject'] = email_subject
        msg['From'] = "MDM Team <mdm@sysco.com>"
        msg['To'] = ", ".join(recipients) if recipients else ""
        msg.attach(MIMEText(email_body, 'plain', 'utf-8'))
        attachment = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        attachment.set_payload(excel_bytes)
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', f'attachment; filename= {excel_filename}')
        msg.attach(attachment)
        eml_output = io.BytesIO(msg.as_bytes())

        st.markdown("### 📝 Email Template")
        col_subject, col_icons = st.columns([4, 1])
        with col_subject:
            st.text_input("Subject", value=email_subject, key="email_subject", label_visibility="visible")
        with col_icons:
            st.markdown("<br>", unsafe_allow_html=True)
            col_dl_eml, col_dl_excel = st.columns(2)
            with col_dl_eml:
                st.download_button(label="📥 .eml", data=eml_output.getvalue(), file_name=f"Email_Draft_{selected_entity_email.replace(' ', '_').replace('/', '_')}_{date.today().isoformat()}.eml", mime="message/rfc822", use_container_width=True, key="download_eml_icon", help="Download email with attachment (.eml)")
            with col_dl_excel:
                st.download_button(label="📊 Excel", data=excel_bytes, file_name=excel_filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key="download_excel_icon", help="Download Excel file only")

        st.text_area("Email Body", value=email_body, height=300, key="email_body")
        st.markdown("---")
        if recipients:
            st.markdown(f'<div style="background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #94a3b8; margin: 1rem 0;"><strong style="color: #94a3b8;">📧 Email Recipients for {selected_entity_email}:</strong><br><span style="color: #cbd5e1;">{recipients_str}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #f39c12; margin: 1rem 0;"><strong style="color: #f39c12;">⚠️ No email recipients configured for {selected_entity_email}</strong><br><span style="color: #cbd5e1;">Please add recipients manually when opening the .eml file in Outlook.</span></div>', unsafe_allow_html=True)

        st.markdown("### 📊 Report Preview")
        if total_count > 0:
            st.info(f"**{selected_entity_email}**: {generic_count:,} Generic GTINs, {blocked_count:,} Placeholder GTINs (999...99)")
            try:
                generic_df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name="Generic GTINs", dtype=str)
                if not generic_df.empty:
                    st.markdown("#### Generic GTINs Sample (first 10)")
                    preview_cols = [c for c in ["SUPC", "Local Product Description", "Brand", "OSD Classification", "gtin_outer_normalized", "gtin_status"] if c in generic_df.columns]
                    st.dataframe(generic_df[preview_cols].head(10) if preview_cols else generic_df.head(10), use_container_width=True, hide_index=True)
                blocked_df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name="Placeholder GTINs (999...99)", dtype=str)
                if not blocked_df.empty:
                    st.markdown("#### Placeholder GTINs (999...99) Sample (first 10)")
                    preview_cols = [c for c in ["SUPC", "Local Product Description", "Brand", "OSD Classification", "gtin_outer_normalized", "gtin_status"] if c in blocked_df.columns]
                    st.dataframe(blocked_df[preview_cols].head(10) if preview_cols else blocked_df.head(10), use_container_width=True, hide_index=True)
            except Exception:
                pass
        else:
            st.success(f"✅ **{selected_entity_email}** has no Generic or Placeholder GTINs. No action required!")

    st.markdown("---")
    st.markdown(f"<div style='text-align: center; color: #cbd5e1;'>📅 Report generated on {date.today().strftime('%B %d, %Y')} | Pre-computed reports from outputs</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()

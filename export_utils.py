"""Export DataFrames to Excel or CSV for download."""
import io
import pandas as pd


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Return a DataFrame as .xlsx bytes (for st.download_button)."""
    if df is None or df.empty:
        buf = io.BytesIO()
        pd.DataFrame().to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        return buf.getvalue()
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return buf.getvalue()


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Return a DataFrame as CSV bytes (for st.download_button)."""
    if df is None or df.empty:
        return b""
    return df.to_csv(index=False).encode("utf-8-sig")

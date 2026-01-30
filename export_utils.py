"""Export DataFrames to Excel or CSV for download."""
import io
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import PatternFill


def _build_inner_outer_paired_df(inner_df, full_df, same_entity):
    """Build a DataFrame with INNER/OUTER rows paired by Match_Group."""
    if inner_df is None or inner_df.empty:
        return pd.DataFrame()
    full_df = full_df.copy()
    full_df["_outer_key"] = full_df["gtin_outer_normalized"].astype(str).str.strip()
    data_cols = [c for c in inner_df.columns if c in full_df.columns]
    rows_out = []
    for match_id, (_, inner_row) in enumerate(inner_df.iterrows(), start=1):
        inner_key = str(inner_row.get("gtin_inner_normalized", "")).strip()
        row_entity = inner_row.get("Legal Entity")
        mask = full_df["_outer_key"] == inner_key
        if same_entity and row_entity is not None:
            mask = mask & (full_df["Legal Entity"] == row_entity)
        outer_rows = full_df.loc[mask]
        row_inner = {"Role": "INNER", "Match_Group": match_id, **{c: inner_row[c] for c in data_cols if c in inner_row.index}}
        rows_out.append(row_inner)
        for _, outer_row in outer_rows.iterrows():
            row_outer = {"Role": "OUTER", "Match_Group": match_id, **{c: outer_row[c] for c in data_cols if c in outer_row.index}}
            rows_out.append(row_outer)
    full_df.drop(columns=["_outer_key"], inplace=True, errors="ignore")
    out = pd.DataFrame(rows_out)
    if out.empty:
        return out
    col_order = ["Role", "Match_Group"] + data_cols
    return out[[c for c in col_order if c in out.columns]]


def to_excel_bytes_inner_outer_paired(inner_df, full_df, same_entity=True) -> bytes:
    """Export Inner rows with matching Outer rows, paired by Match_Group, with alternating green fill."""
    df = _build_inner_outer_paired_df(inner_df, full_df, same_entity)
    if df is None or df.empty:
        buf = io.BytesIO()
        pd.DataFrame(columns=["Role", "Match_Group"]).to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        return buf.getvalue()
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    wb = load_workbook(buf)
    ws = wb.active
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    for row_idx in range(2, ws.max_row + 1):
        try:
            match_group_cell = ws.cell(row=row_idx, column=2)
            if match_group_cell.value is not None:
                mg = int(match_group_cell.value)
                if mg % 2 == 1:
                    for col_idx in range(1, ws.max_column + 1):
                        ws.cell(row=row_idx, column=col_idx).fill = green_fill
        except (TypeError, ValueError):
            pass
    out_buf = io.BytesIO()
    wb.save(out_buf)
    out_buf.seek(0)
    return out_buf.getvalue()


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

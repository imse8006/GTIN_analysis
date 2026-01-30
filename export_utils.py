"""Export DataFrames to Excel or CSV for download."""
import io
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import PatternFill


def _build_inner_outer_paired_df(inner_df, full_df, same_entity):
    """Build a DataFrame with INNER/OUTER rows paired by Match_Group (index-based, no iterrows)."""
    if inner_df is None or inner_df.empty:
        return pd.DataFrame()
    full_df = full_df.copy()
    full_df["_outer_key"] = full_df["gtin_outer_normalized"].astype(str).str.strip()
    data_cols = [c for c in inner_df.columns if c in full_df.columns]
    # Index: (key,) or (key, entity) -> iloc positions of rows in full_df
    if same_entity:
        gb = full_df.groupby(["_outer_key", "Legal Entity"], dropna=False)
        key_to_indices = {k: gb.get_group(k).index.tolist() for k in gb.groups}
    else:
        gb = full_df.groupby("_outer_key", dropna=False)
        key_to_indices = {k: gb.get_group(k).index.tolist() for k in gb.groups}
    blocks = []
    inner_keys = inner_df["gtin_inner_normalized"].astype(str).str.strip()
    entities = inner_df["Legal Entity"]
    for match_id in range(len(inner_df)):
        inner_row = inner_df.iloc[match_id]
        key = inner_keys.iloc[match_id]
        row_entity = entities.iloc[match_id]
        if same_entity and row_entity is not None:
            lookup = (key, row_entity)
        else:
            lookup = key
        indices = key_to_indices.get(lookup, [])
        inner_block = pd.DataFrame([{**{"Role": "INNER", "Match_Group": match_id + 1}, **{c: inner_row[c] for c in data_cols}}])
        blocks.append(inner_block)
        if indices:
            outer_block = full_df.loc[indices, data_cols].copy()
            outer_block.insert(0, "Match_Group", match_id + 1)
            outer_block.insert(0, "Role", "OUTER")
            blocks.append(outer_block)
    full_df.drop(columns=["_outer_key"], inplace=True, errors="ignore")
    out = pd.concat(blocks, ignore_index=True)
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
    # Use DataFrame to know which Excel rows have odd Match_Group (faster than reading cells)
    mg = pd.to_numeric(df["Match_Group"], errors="coerce").fillna(0).astype(int)
    odd_rows = {i + 2 for i in range(len(df)) if mg.iloc[i] % 2 == 1}
    for row_idx in odd_rows:
        for col_idx in range(1, ws.max_column + 1):
            ws.cell(row=row_idx, column=col_idx).fill = green_fill
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

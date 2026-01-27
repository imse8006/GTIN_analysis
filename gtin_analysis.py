import argparse
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

# ----- CONFIG -----
INPUT_FILE = "Full list products in STIBO.xlsx"
OUTPUT_DIR = Path(f"gtin_report_{date.today().isoformat()}")
OUTPUT_DIR.mkdir(exist_ok=True)

# MDM Business Rules: Explicit GTIN classifications
GENERIC_GTINS = {
    "10000000000009",
    "20000000000009",
    "30000000000009",
    "40000000000009",
    "50000000000009",
    "60000000000009",
    "70000000000009",
    "80000000000009",
}

EXPLICIT_BLOCKED = "99999999999999"

# Valid GTIN lengths according to MDM rules
VALID_LENGTHS = {8, 13, 14}


def normalize_gtin(value: Optional[str]) -> Optional[str]:
    """
    Normalize GTIN value from Excel.
    Handles scientific notation (only if truly contains 'E' or 'e').
    Returns a clean string of digits or None.
    """
    if value is None:
        return None

    s = str(value).strip()
    if s == "" or s.lower() == "nan":
        return None

    # Only convert if truly in scientific notation (contains E/e)
    if "E" in s.upper():
        try:
            s = str(int(float(s)))
        except (ValueError, OverflowError):
            return s

    # Remove trailing ".0" if present (but only if it's a float representation)
    if "." in s and s.endswith(".0") and s[:-2].replace(".", "").isdigit():
        s = s[:-2]

    return s


def has_valid_gs1_check_digit(gtin: str, length: int) -> bool:
    """
    Validate GS1 check digit for GTIN-13 or GTIN-14.
    Returns True if valid or if length is 8 (GTIN-8 has different check digit algorithm).
    """
    if length == 8:
        # GTIN-8 check digit validation (different algorithm)
        # For now, we'll accept all numeric GTIN-8 as valid format-wise
        return True
    
    if length not in (13, 14):
        return False
    
    if not gtin.isdigit():
        return False
    
    digits = [int(d) for d in gtin]
    body, check_digit = digits[:-1], digits[-1]
    
    # GS1 check digit: from right to left on body
    # For GTIN-13: odd positions (1,3,5...) * 1, even positions (2,4,6...) * 3
    # For GTIN-14: odd positions (1,3,5...) * 3, even positions (2,4,6...) * 1
    total = 0
    for i, d in enumerate(reversed(body), start=1):
        if length == 13:
            # GTIN-13: odd * 1, even * 3
            multiplier = 1 if i % 2 == 1 else 3
        else:  # GTIN-14
            # GTIN-14: odd * 3, even * 1
            multiplier = 3 if i % 2 == 1 else 1
        total += d * multiplier
    
    calc = (10 - (total % 10)) % 10
    return calc == check_digit


def classify_gtin_status(gtin_raw: Optional[str]) -> str:
    """
    Classify GTIN according to MDM rules.
    Returns: MISSING, NON_NUMERIC, INVALID_LENGTH, GENERIC_GTIN, EXPLICIT_BLOCKED, SUSPECT, GTIN_8, GTIN_13, GTIN_14
    
    Business rules priority:
    1. EXPLICIT_BLOCKED (99999999999999) - highest priority
    2. GENERIC_GTIN (explicit list) - second priority
    3. Format validation (length, numeric)
    4. Check digit validation (for valid formats)
    """
    # Step 1: Check for MISSING
    if gtin_raw is None:
        return "MISSING"
    
    gtin = normalize_gtin(gtin_raw)
    
    if gtin is None:
        return "MISSING"
    
    # Step 2: Check EXPLICIT_BLOCKED (highest business priority)
    if gtin == EXPLICIT_BLOCKED:
        return "EXPLICIT_BLOCKED"
    
    # Step 3: Check GENERIC_GTIN (second business priority)
    if gtin in GENERIC_GTINS:
        return "GENERIC_GTIN"
    
    # Step 4: Check if numeric
    if not gtin.isdigit():
        return "NON_NUMERIC"
    
    # Step 5: Check length
    length = len(gtin)
    
    if length not in VALID_LENGTHS:
        return "INVALID_LENGTH"
    
    # Step 6: For valid lengths, check check digit
    # If check digit is invalid, mark as SUSPECT (format is correct but content is suspicious)
    if not has_valid_gs1_check_digit(gtin, length):
        return "SUSPECT"
    
    # Step 7: Valid GTIN - return status based on length
    if length == 8:
        return "GTIN_8"
    elif length == 13:
        return "GTIN_13"
    else:  # length == 14
        return "GTIN_14"


def main(enable_deduplication: bool = False):
    print(f"Reading Excel file: {INPUT_FILE}")
    
    # Read Excel file
    try:
        df = pd.read_excel(INPUT_FILE, dtype=str)
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {INPUT_FILE}")
    
    # Store initial row count (excluding header)
    initial_row_count = len(df)
    print(f"Total rows in Excel (excluding header): {initial_row_count}")
    
    # Find GTIN-Outer column (case-insensitive, handle variations)
    gtin_col = None
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if "gtin" in col_lower and "outer" in col_lower:
            gtin_col = col
            break
    
    if gtin_col is None:
        # Try alternative names
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if col_lower in ["gtin-outer", "gtin_outer", "gtinouter"]:
                gtin_col = col
                break
    
    if gtin_col is None:
        raise ValueError(f"GTIN-Outer column not found. Available columns: {list(df.columns)}")
    
    print(f"Found GTIN column: '{gtin_col}'")
    
    # Classify GTIN status
    print("Classifying GTIN status according to MDM rules...")
    df["gtin_outer_raw"] = df[gtin_col]
    df["gtin_status"] = df[gtin_col].apply(classify_gtin_status)
    
    # Create normalized GTIN column for reference
    df["gtin_outer_normalized"] = df[gtin_col].apply(normalize_gtin)
    
    # ---------- AGGREGATIONS BY STATUS ----------
    print("\nGenerating aggregations by status...")
    
    # Overall status summary
    status_summary = df["gtin_status"].value_counts().reset_index()
    status_summary.columns = ["gtin_status", "count"]
    status_summary["percentage"] = (status_summary["count"] / len(df) * 100).round(2)
    status_summary = status_summary.sort_values("count", ascending=False)
    
    # Prepare summary Excel file with multiple sheets
    summary_file = OUTPUT_DIR / "gtin_status_audit.xlsx"
    summary_writer = pd.ExcelWriter(summary_file, engine='openpyxl')
    
    # Sheet 1: Overall Status Summary
    status_summary.to_excel(summary_writer, sheet_name="Status Summary", index=False)
    
    # Sheet 2: Detailed breakdown by status
    detailed_breakdown = []
    for status in status_summary["gtin_status"]:
        status_df = df[df["gtin_status"] == status]
        detailed_breakdown.append({
            "gtin_status": status,
            "count": len(status_df),
            "percentage": round(len(status_df) / len(df) * 100, 2),
            "sample_values": ", ".join(status_df["gtin_outer_raw"].head(5).astype(str).tolist()) if len(status_df) > 0 else ""
        })
    
    breakdown_df = pd.DataFrame(detailed_breakdown)
    breakdown_df.to_excel(summary_writer, sheet_name="Status Breakdown", index=False)
    
    # Sheet 3: All rows with status (for audit trail)
    audit_df = df[["gtin_outer_raw", "gtin_outer_normalized", "gtin_status"]].copy()
    audit_df.to_excel(summary_writer, sheet_name="Full Audit Trail", index=False)
    
    # Sheet 4: Invalid GTINs detail (for remediation)
    invalid_statuses = ["MISSING", "NON_NUMERIC", "INVALID_LENGTH", "SUSPECT"]
    invalid_df = df[df["gtin_status"].isin(invalid_statuses)].copy()
    if not invalid_df.empty:
        invalid_df.to_excel(summary_writer, sheet_name="Invalid GTINs", index=False)
    
    # Sheet 5: Business rule overrides (GENERIC_GTIN and EXPLICIT_BLOCKED)
    override_statuses = ["GENERIC_GTIN", "EXPLICIT_BLOCKED"]
    override_df = df[df["gtin_status"].isin(override_statuses)].copy()
    if not override_df.empty:
        override_df.to_excel(summary_writer, sheet_name="Business Overrides", index=False)
    
    # Sheet 6: Valid GTINs by type
    valid_statuses = ["GTIN_8", "GTIN_13", "GTIN_14"]
    valid_df = df[df["gtin_status"].isin(valid_statuses)].copy()
    if not valid_df.empty:
        valid_df.to_excel(summary_writer, sheet_name="Valid GTINs", index=False)
    
    # Close summary writer
    summary_writer.close()
    print(f"✓ GTIN status audit saved to: {summary_file}")
    
    # Print summary to console
    print("\n" + "="*60)
    print("GTIN STATUS SUMMARY")
    print("="*60)
    for _, row in status_summary.iterrows():
        print(f"{row['gtin_status']:20s} : {row['count']:6d} ({row['percentage']:5.2f}%)")
    print("="*60)
    print(f"Total rows analyzed: {initial_row_count}")
    
    # Verification
    total_classified = status_summary["count"].sum()
    if total_classified != initial_row_count:
        print(f"\nWARNING: Classification count mismatch! Expected: {initial_row_count}, Got: {total_classified}")
    else:
        print(f"\n✓ Verification: All {initial_row_count} rows classified successfully")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MDM GTIN Status Analysis")
    parser.add_argument(
        "-deduplication_analysis",
        action="store_true",
        help="Enable deduplication analysis (not implemented yet)",
    )
    args = parser.parse_args()
    
    main(enable_deduplication=args.deduplication_analysis)

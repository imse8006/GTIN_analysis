"""
Complete documentation of all GTIN analyses in the dashboard.
This page explains each operation, comparison, and criterion used in the analyses.
"""
import streamlit as st
from auth_utils import render_login_form

st.set_page_config(
    page_title="Documentation - GTIN Analysis",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main-header { font-size: 3rem; font-weight: 700; color: #94a3b8; text-align: center; margin-bottom: 2rem; padding: 1rem 0; }
    .section-header { font-size: 1.8rem; font-weight: 600; color: #94a3b8; margin-top: 2rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #475569; }
    .subsection-header { font-size: 1.3rem; font-weight: 600; color: #cbd5e1; margin-top: 1.5rem; margin-bottom: 0.8rem; }
    .code-block { background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; border: 1px solid #334155; margin: 1rem 0; }
    .info-box { background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #3b82f6; margin: 1rem 0; }
    .warning-box { background-color: #1e293b; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #f59e0b; margin: 1rem 0; }
    .stApp { background-color: #0f172a; }
    </style>
""", unsafe_allow_html=True)


def check_password():
    return render_login_form("Documentation", password_key="password_doc")


def main():
    if not check_password():
        return

    st.markdown('<h1 class="main-header">📚 Documentation - GTIN Analysis Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<div style="text-align: center; color: #cbd5e1; margin-bottom: 2rem;">Complete guide to all analyses and comparisons performed in the dashboard</div>', unsafe_allow_html=True)

    # Table of Contents
    st.markdown('<div class="section-header">📑 Table of Contents</div>', unsafe_allow_html=True)
    toc = """
    1. [GTIN Classification](#classification)
    2. [GTIN Quality Analysis](#qualite)
    3. [Duplicate Analysis](#doublons)
    4. [Generic GTINs](#generiques)
    5. [Placeholder GTINs](#placeholder)
    6. [Invalid GTINs](#invalid)
    7. [Suspect GTINs](#suspects)
    8. [Valid GTINs](#valides)
    9. [Generic GTIN vs Taxonomy Analysis](#generic-taxonomy)
    """
    st.markdown(toc)

    # 1. Classification
    st.markdown('<div class="section-header" id="classification">1. GTIN Classification</div>', unsafe_allow_html=True)
    st.markdown("""
    The `classify_gtin_status()` function classifies each GTIN according to MDM rules.
    
    **Priority order (from most specific to most general):**
    
    1. **EXPLICIT_BLOCKED / PLACEHOLDER** : GTINs composed only of 9s (e.g., `99999999999999`)
    2. **GENERIC_GTIN** : Generic GTINs from the explicit list :
       - `10000000000009`, `20000000000009`, `30000000000009`, `40000000000009`
       - `50000000000009`, `60000000000009`, `70000000000009`, `80000000000009`
    3. **NON_NUMERIC** : Contains non-numeric characters
    4. **INVALID_LENGTH** : Length different from 8, 13 or 14 digits
    5. **INVALID** : Valid format but invalid GS1 check digit (or other validation failures)
    6. **GTIN_8, GTIN_13, GTIN_14** : Valid GTINs according to their length
    
    **GS1 check digit validation:**
    - For GTIN-13 and GTIN-14, verification of the GS1 algorithm
    - If check digit is incorrect → marked as **INVALID**
    """)

    # 2. Quality Analysis
    st.markdown('<div class="section-header" id="qualite">2. GTIN Quality Analysis</div>', unsafe_allow_html=True)
    st.markdown("""
    **Page: GTIN Quality Dashboard**
    
    This analysis classifies all products according to the quality of their GTIN-Outer.
    
    **Calculated metrics:**
    - **Total Products** : Total number of products analyzed
    - **Valid GTINs** : Valid GTINs (8_digits, 13_digits, 14_digits)
    - **Invalid GTINs** : Invalid GTINs (MISSING, NON_NUMERIC, INVALID_LENGTH)
    - **Generic GTINs** : Generic GTINs
    - **Placeholder GTINs** : Blocked GTINs (999...99)
    - **Compliance Rate** : Percentage of valid GTINs
    
    **Breakdown by length:**
    - 8 digits : Valid GTIN-8
    - 13 digits : Valid GTIN-13
    - 14 digits : Valid GTIN-14
    """)

    # 3. Duplicate Analysis
    st.markdown('<div class="section-header" id="doublons">3. Duplicate Analysis</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="subsection-header">3.1 Cross Duplicates</div>', unsafe_allow_html=True)
    st.markdown("""
    **Definition** : GTINs that appear in both the GTIN-Outer AND GTIN-Inner columns.
    
    **Detection** : A normalized GTIN appears in both columns (not necessarily on the same row).
    
    **Usage** : Identify GTINs shared between Outer and Inner, which may indicate data entry errors.
    """)
    
    st.markdown('<div class="subsection-header">3.2 GTIN Outer Duplicates</div>', unsafe_allow_html=True)
    st.markdown("""
    **Definition** : GTIN-Outer that appears multiple times in the dataset.
    
    **Detection** : Counts the number of occurrences of each normalized GTIN-Outer.
    
    **Analysis** :
    - **Same entity** : The GTIN appears multiple times in the same Legal Entity
    - **Different entities** : The GTIN is shared between multiple Legal Entities (valid sharing)
    """)
    
    st.markdown('<div class="subsection-header">3.3 GTIN Inner Duplicates</div>', unsafe_allow_html=True)
    st.markdown("""
    **Definition** : GTIN-Inner that appears multiple times in the dataset.
    
    **Detection** : Counts the number of occurrences of each normalized GTIN-Inner.
    
    **Analysis** : Identifies duplicated inner GTINs, generally less problematic than Outer duplicates.
    """)
    
    st.markdown('<div class="subsection-header">3.4 Outer = Inner (same row)</div>', unsafe_allow_html=True)
    st.markdown("""
    **Definition** : On the same row, GTIN-Outer = GTIN-Inner.
    
    **Detection** : Direct comparison of normalized values on each row.
    
    **Use case** : Identify products where Outer and Inner are identical (may be normal or suspect depending on context).
    """)
    
    st.markdown('<div class="subsection-header">3.5 Inner = Outer (non-Generic)</div>', unsafe_allow_html=True)
    st.markdown("""
    **Definition** : GTIN-Inner that matches a GTIN-Outer from another row (same entity or other entity).
    
    **Detection** : 
    - Compares each GTIN-Inner with all GTIN-Outer values
    - Excludes Generic GTINs from analysis
    - Distinguishes same entity vs other entities
    
    **Usage** : Identify cases where Inner matches Outer from another product.
    """)

    # 4. Generic GTINs
    st.markdown('<div class="section-header" id="generiques">4. Generic GTINs</div>', unsafe_allow_html=True)
    st.markdown("""
    **Definition** : Generic GTINs used to represent product categories rather than specific products.
    
    **Generic GTIN list:**
    - `10000000000009` → Butchery (BEEF, PORK, POULTRY)
    - `20000000000009` → Not in MDD
    - `30000000000009` → Equipment (SUPPLIES & EQUIPMENT)
    - `40000000000009` → Fishmongery (SEAFOOD)
    - `50000000000009` → Not in MDD
    - `60000000000009` → Not in MDD
    - `70000000000009` → Produce (PRODUCE)
    - `80000000000009` → Not in MDD
    
    **Analysis** :
    - Counts occurrences of each Generic GTIN
    - Analysis by Legal Entity
    - Identifies Generic GTIN duplicates
    """)

    # 5. Placeholder GTINs
    st.markdown('<div class="section-header" id="placeholder">5. Placeholder GTINs</div>', unsafe_allow_html=True)
    st.markdown("""
    **Definition** : Explicitly blocked GTINs, composed only of 9s.
    
    **Criteria** : All digits are 9s (e.g., `99999999999999`, `999`, `99`)
    
    **Examples** :
    - `99999999999999` → Placeholder 14 digits
    - `9999999999999` → Placeholder 13 digits
    - `99999999` → Placeholder 8 digits
    
    **Usage** : Identify products without a real GTIN assigned.
    """)

    # 6. Invalid GTINs
    st.markdown('<div class="section-header" id="invalid">6. Invalid GTINs</div>', unsafe_allow_html=True)
    st.markdown("""
    **Definition** : GTINs that do not meet the MDM validation rules and cannot be considered valid, generic, or placeholder.
    
    **A GTIN is marked as Invalid if any of the following applies:**
    
    1. **Missing or empty** : The GTIN field is null, empty, or cannot be normalized.
    
    2. **Non-numeric** : The value contains characters other than digits (letters, spaces, symbols).
       - Example : `ABC123`, `12-345-678`
    
    3. **Invalid length** : The GTIN does not have 8, 13, or 14 digits.
       - Valid lengths only : 8 (GTIN-8), 13 (GTIN-13 / EAN-13), 14 (GTIN-14)
       - Example : `12345` (5 digits), `123456789012` (12 digits)
    
    4. **Invalid GS1 check digit** : For GTIN-13 and GTIN-14, the last digit (check digit) does not match the result of the GS1 Modulo 10 algorithm.
       - Example : A GTIN-13 where the calculated check digit differs from the 13th digit.
    
    **Order of checks** : Placeholder and Generic are evaluated first; only if the GTIN is neither of those is it then checked for the above Invalid conditions.
    
    **Usage** : Identify products that need data correction (missing GTIN, typo, wrong length, or invalid check digit).
    """)

    # 7. Suspect GTINs
    st.markdown('<div class="section-header" id="suspects">7. Suspect GTINs</div>', unsafe_allow_html=True)
    st.markdown("""
    **Definition** : GTINs with valid format but showing suspicious patterns.
    
    **Detection criteria:**
    
    1. **Excessive repetition** : A single digit appears ≥ 60% of the length
       - Example : `11111111111111` (digit 1 appears 14 times)
       - Example : `18414900000000` (many zeros)
    
    2. **Too many zeros at the end** : 
       - At least 6 consecutive zeros at the end, OR
       - Half the length in zeros at the end
       - Example : `18414900000000` (8 zeros at the end out of 14 digits)
    
    **Exclusion** : Generic GTINs are excluded from suspect analysis.
    
    **Usage** : Identify GTINs that appear to be placeholders or data entry errors.
    """)

    # 8. Valid GTINs
    st.markdown('<div class="section-header" id="valides">8. Valid GTINs</div>', unsafe_allow_html=True)
    st.markdown("""
    **Definition** : GTINs that pass all validations.
    
    **Validity criteria:**
    1. Valid numeric format
    2. Correct length (8, 13 or 14 digits)
    3. Valid GS1 check digit (for 13 and 14 digits)
    4. Not a Generic GTIN
    5. Not a Placeholder (999...99)
    
    **Analysis by entity** :
    - Identifies valid GTINs shared between multiple Legal Entities
    - Distinguishes valid sharing (same GTIN, different entities) from problematic duplicates
    """)

    # 9. Generic GTIN vs Taxonomy
    st.markdown('<div class="section-header" id="generic-taxonomy">9. Generic GTIN vs Taxonomy Analysis</div>', unsafe_allow_html=True)
    st.markdown("""
    **Page: Generic GTIN Analysis**
    
    **Objective** : Verify that Generic GTINs correspond to the correct OSD taxonomy.
    
    **Process:**
    
    1. **Initial filtering** : Selects only products with Generic GTINs :
       - `10000000000009` (Butchery)
       - `30000000000009` (Equipment)
       - `40000000000009` (Fishmongery)
       - `70000000000009` (Produce)
    
    2. **Taxonomy extraction** : Takes the first part of "OSD Classification" (before the first dash)
       - Example : `"BEEF-YYYY-ZZZZ"` → `"BEEF"`
    
    3. **Expected mapping** :
       - `BEEF, PORK, POULTRY` → Expected GTIN: `10000000000009`
       - `SUPPLIES & EQUIPMENT` → Expected GTIN: `30000000000009`
       - `SEAFOOD` → Expected GTIN: `40000000000009`
       - `PRODUCE` → Expected GTIN: `70000000000009`
    
    4. **Comparison** :
       - **Conforming** : Product's Generic GTIN = Expected GTIN for its taxonomy
       - **Non-conforming** : Product's Generic GTIN ≠ Expected GTIN, OR taxonomy not in mapping
    
    **Results** :
    - Global metrics (total, conforming, non-conforming)
    - List of non-conforming records with details (SUPC, Description, OSD Taxonomy, OSD Expected, GTIN Outer, Legal Entity)
    - Statistics by Legal Entity
    """)

    # GTIN-Outer Normalization
    st.markdown('<div class="section-header">🔧 GTIN-Outer Normalization</div>', unsafe_allow_html=True)
    st.markdown("""
    **Priority logic for normalized GTIN-Outer:**
    
    1. If **GTIN-Outer AND Generic GTIN** are filled → Use **GTIN-Outer** (priority)
    2. If only **GTIN-Outer** is filled → Use **GTIN-Outer**
    3. If only **Generic GTIN** is filled → Use **Generic GTIN**
    4. If neither is filled → `None`
    
    **`gtin_source` column** : Indicates which column was used for `gtin_outer_normalized`
    - `"GTIN Outer"` : Only GTIN-Outer filled
    - `"Generic GTIN"` : Only Generic GTIN filled
    - `"GTIN Outer (both filled)"` : Both filled, GTIN-Outer used
    - `"None"` : Neither filled
    """)

    # GTIN-13 to GTIN-14 Conversion
    st.markdown('<div class="section-header">🔄 GTIN-13 → GTIN-14 Conversion</div>', unsafe_allow_html=True)
    st.markdown("""
    **`gtin_to_14()` function** : Converts a GTIN-13 to GTIN-14 by adding a zero at the beginning.
    
    **Rule** :
    - If length = 13 → Add `"0"` at the beginning
    - If length = 14 → Return as is
    - Otherwise → Return as is (no conversion)
    
    **Example** :
    - `"1234567890123"` (13 digits) → `"01234567890123"` (14 digits)
    - `"12345678901234"` (14 digits) → `"12345678901234"` (unchanged)
    """)

    # GS1 Check Digit
    st.markdown('<div class="section-header">✅ GS1 Check Digit Validation</div>', unsafe_allow_html=True)
    st.markdown("""
    **Validation algorithm:**
    
    1. Take body digits (all except the last)
    2. Multiply alternately by 1 and 3 starting from the **left** (standard GS1 algorithm)
    3. Sum all results
    4. Calculate : `(10 - (sum % 10)) % 10`
    5. Compare with the last digit (check digit)
    
    **Rules according to length:**
    - **GTIN-13** : Multiply by 1 the odd positions (1, 3, 5...), by 3 the even positions (2, 4, 6...), counting from the **left**
    - **GTIN-14** : Multiply by 3 the odd positions (1, 3, 5...), by 1 the even positions (2, 4, 6...), counting from the **left**
    
    **Result** :
    - If check digit correct → Valid GTIN
    - If check digit incorrect → Marked as **INVALID**
    """)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #64748b; margin-top: 2rem;">
    📊 GTIN Analysis Dashboard - Complete Documentation<br>
    For any questions, consult the source code in <code>duplicate_analysis_backend.py</code>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()

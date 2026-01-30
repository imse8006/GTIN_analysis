"""
Run full backend batch (Duplicate + Quality + Generic GTIN + Generate Email) then push outputs/ to GitHub.

Usage:
  python run_batch_and_push.py [input_file.xlsx]
  python run_batch_and_push.py --no-push     # run batch only, do not git push

All analyses are pre-computed; Streamlit pages load from outputs/YYYY-MM-DD/. Excel files in outputs/
are for all legal entities; when filtering by entity in the dashboard, downloads are generated on the fly.
"""
import argparse
import subprocess
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(
        description="Run Duplicate Analysis batch and push outputs/ to GitHub."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="all-products-prod-2026-01-22_15.44.25.xlsx",
        help="Input Excel file path (default: same as run_duplicate_analysis_batch.py)",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Run batch only; do not git add/commit/push",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    if not input_path.is_file():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # 1. Run batch
    from duplicate_analysis_backend import run_full_analysis

    try:
        out_dir = run_full_analysis(str(input_path.resolve()))
        print(f"Batch done. Results in: {out_dir}")
    except Exception as e:
        print(f"Batch error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.no_push:
        return

    # 2. Git add outputs/
    subprocess.run(
        ["git", "add", "outputs/"],
        cwd=ROOT,
        check=True,
    )

    # 3. Commit only if there are staged changes
    status = subprocess.run(
        ["git", "diff", "--staged", "--quiet"],
        cwd=ROOT,
    )
    if status.returncode != 0:
        date_part = Path(out_dir).name
        subprocess.run(
            ["git", "commit", "-m", f"Duplicate Analysis: update outputs {date_part}"],
            cwd=ROOT,
            check=True,
        )
        print("Committed outputs/")
    else:
        print("No changes in outputs/ — nothing to commit.")

    # 4. Push
    subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=ROOT,
        check=True,
    )
    print("Pushed to GitHub. Streamlit Cloud will redeploy and source from outputs/.")


if __name__ == "__main__":
    main()

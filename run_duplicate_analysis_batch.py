"""
Run Duplicate Analysis in batch: load input Excel, run all analyses, write results to outputs/YYYY-MM-DD/.
Schedule this script (cron, Task Scheduler) after each extract. Streamlit Duplicate Analysis page then serves from outputs/.
Usage:
  python run_duplicate_analysis_batch.py [input_file.xlsx]
  python run_duplicate_analysis_batch.py --input path/to/file.xlsx [--date YYYY-MM-DD] [--out outputs/YYYY-MM-DD]
"""
import argparse
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from duplicate_analysis_backend import run_full_analysis, OUTPUTS_BASE


def main():
    parser = argparse.ArgumentParser(description="Run Duplicate Analysis batch and write to outputs/<date>/")
    parser.add_argument("input", nargs="?", default="all-products-prod-2026-01-22_15.44.25.xlsx", help="Input Excel file path")
    parser.add_argument("--date", "-d", default=None, help="Extract date for folder name (YYYY-MM-DD). Default: today.")
    parser.add_argument("--out", "-o", default=None, help=f"Output directory. Default: {OUTPUTS_BASE}/<date>")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        out_dir = run_full_analysis(
            str(input_path.resolve()),
            output_dir=args.out,
            extract_date=args.date,
        )
        print(f"Success. Results in: {out_dir}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

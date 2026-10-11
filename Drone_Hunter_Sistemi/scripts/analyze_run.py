"""Kayitli calismayi ozetler.  Kullanim (proje kokunden):
    $env:PYTHONPATH = "src"
    python scripts\analyze_run.py                # son calisma
    python scripts\analyze_run.py --run 3
"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_core.run_analysis import format_report, summarize  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "records" / "dronehunter.db"))
    ap.add_argument("--run", type=int, default=None)
    args = ap.parse_args()
    if not pathlib.Path(args.db).exists():
        sys.exit(f"Veritabani yok: {args.db}  (once orkestratoru calistirin)")
    print(format_report(summarize(args.db, args.run)))


if __name__ == "__main__":
    main()

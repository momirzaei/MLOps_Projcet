"""Manual runner for the Bronze ingestion (Airflow will call the same function)."""
import argparse
import json

from src.ingestion.bronze import run_bronze_ingest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Bronze ingestion")
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download the source file even if already cached",
    )
    args = parser.parse_args()
    summary = run_bronze_ingest(force_download=args.force_download)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

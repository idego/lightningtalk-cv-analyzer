from __future__ import annotations

import argparse
import json
from pathlib import Path

from cv_validator.measurement import load_jsonl, summarize_measurements


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize controlled or previously recorded V1 measurements; never calls a model.")
    parser.add_argument("input", type=Path, help="PII-free JSONL measurement records")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(summarize_measurements(load_jsonl(args.input)), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")


if __name__ == "__main__":
    main()

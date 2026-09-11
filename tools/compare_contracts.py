from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.contract_tools import compare_recordings, load_recordings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare PHP/Python JSONL recordings, response headers, and database effects"
    )
    parser.add_argument("--php", required=True, type=Path)
    parser.add_argument("--python", dest="python_path", required=True, type=Path)
    parser.add_argument("--rules", type=Path)
    args = parser.parse_args()

    rules = {}
    if args.rules:
        rules = json.loads(args.rules.read_text(encoding="utf-8"))
    php = load_recordings(args.php)
    python = load_recordings(args.python_path)
    failures = []
    for request_id in sorted(set(php) | set(python)):
        if request_id not in php or request_id not in python:
            failures.append({"request_id": request_id, "kind": "missing_recording"})
            continue
        failures.extend(
            {
                "request_id": request_id,
                "kind": mismatch.kind,
                "expected": mismatch.expected,
                "actual": mismatch.actual,
            }
            for mismatch in compare_recordings(php[request_id], python[request_id], rules)
        )
    print(json.dumps(failures, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

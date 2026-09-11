from __future__ import annotations

import json
import sys
from pathlib import Path

from tools.baseline_checks import inspect_wwwroot_zip


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m tools.inspect_wwwroot PATH_TO_WWWROOT_ZIP", file=sys.stderr)
        return 2
    report = inspect_wwwroot_zip(Path(sys.argv[1]))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path


CONTRACT_MODULES = ("organization", "order", "finance")
_JSONL_FILES = ("cases.jsonl", "php.jsonl", "python.jsonl")
_JSON_FILES = ("normalization.json", "database-before.json", "database-after.json", "proof.json")
_DEFAULT_CONTENT = {
    "normalization.json": {"ignore_paths": [], "replace_paths": {}},
    "database-before.json": {},
    "database-after.json": {},
    "proof.json": {"routes": []},
}


def scaffold_fixture_directory(root: Path, module: str) -> list[Path]:
    """Create empty, safe contract inputs without inventing business evidence."""
    if module not in CONTRACT_MODULES:
        raise ValueError(f"unknown contract module: {module}")

    directory = root / module
    directory.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for name in (*_JSONL_FILES, *_JSON_FILES):
        path = directory / name
        if path.exists():
            continue
        if name in _JSONL_FILES:
            path.write_text("", encoding="utf-8")
        else:
            path.write_text(
                json.dumps(_DEFAULT_CONTENT[name], ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        created.append(path)
    return created


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create empty redacted contract fixture directories"
    )
    parser.add_argument("--root", type=Path, default=Path("contracts/fixtures"))
    parser.add_argument("--module", choices=CONTRACT_MODULES, action="append")
    args = parser.parse_args()

    modules = tuple(args.module or CONTRACT_MODULES)
    created = [
        path
        for module in modules
        for path in scaffold_fixture_directory(args.root, module)
    ]
    print(f"created={len(created)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

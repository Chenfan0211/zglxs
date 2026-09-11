from __future__ import annotations

import argparse
import shutil
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


FRONTEND_ROOT = "life.localhost.com"
CONFIG_PATH = Path("js/config.js")


def prepare_frontend(
    source_zip: Path,
    destination: Path,
    frontend_root: str = FRONTEND_ROOT,
) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    prefix = frontend_root.rstrip("/") + "/"
    with ZipFile(source_zip) as archive:
        for info in archive.infolist():
            if not info.filename.startswith(prefix) or info.is_dir():
                continue
            relative = PurePosixPath(info.filename[len(prefix) :])
            if _is_unsafe(relative):
                raise ValueError(f"unsafe archive path: {info.filename}")
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))

    config = destination / CONFIG_PATH
    if config.exists():
        config.write_text("var BASE_API_URI = '/apiv1';\n", encoding="utf-8")
    return destination


def _is_unsafe(path: PurePosixPath) -> bool:
    return path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract the life.localhost.com frontend")
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args(argv)

    prepare_frontend(args.source_zip, args.destination)
    print(args.destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

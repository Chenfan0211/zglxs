from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


FRONTEND_ROOT = "life.localhost.com"
CONFIG_PATH = Path("js/config.js")
LEGACY_ERROR_HANDLER = (
    'message:e.msg,type:"error",duration:1e4'
)
PATCHED_LEGACY_ERROR_HANDLER = (
    'message:e.msg||(e.response&&e.response.data&&e.response.data.msg)||'
    '"\\u8bf7\\u6c42\\u5931\\u8d25",type:"error",duration:1e4'
)


def prepare_frontend(
    source_zip: Path,
    destination: Path,
    frontend_root: str = FRONTEND_ROOT,
    *,
    demo_autofill: bool = False,
    demo_hostnames: tuple[str, ...] = (),
    demo_mobile: str | None = None,
    demo_password: str | None = None,
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

    _patch_legacy_error_handler(destination)
    config = destination / CONFIG_PATH
    if config.exists():
        config.write_text(
            render_frontend_config(
                demo_autofill=demo_autofill,
                demo_hostnames=demo_hostnames,
                demo_mobile=demo_mobile,
                demo_password=demo_password,
            ),
            encoding="utf-8",
        )
    return destination


def _patch_legacy_error_handler(destination: Path) -> None:
    for bundle in (destination / "static/js").glob("app.*.js"):
        content = bundle.read_text(encoding="utf-8")
        patched = content.replace(
            LEGACY_ERROR_HANDLER,
            PATCHED_LEGACY_ERROR_HANDLER,
        )
        if patched != content:
            bundle.write_text(patched, encoding="utf-8")


def render_frontend_config(
    *,
    demo_autofill: bool = False,
    demo_hostnames: tuple[str, ...] = (),
    demo_mobile: str | None = None,
    demo_password: str | None = None,
) -> str:
    config = "var BASE_API_URI = '/apiv1';\n"
    if not demo_autofill:
        return config
    if not demo_hostnames or not demo_mobile or not demo_password:
        raise ValueError(
            "demo autofill requires demo_hostnames, demo_mobile and demo_password"
        )

    hosts = json.dumps(list(demo_hostnames), ensure_ascii=True)
    mobile = json.dumps(demo_mobile, ensure_ascii=True)
    password = json.dumps(demo_password, ensure_ascii=True)
    return (
        config
        + "(function () {\n"
        + f"  var allowedHosts = {hosts};\n"
        + "  if (allowedHosts.indexOf(window.location.hostname) === -1) return;\n"
        + f"  window.localStorage.setItem('isRememberAccount', '1');\n"
        + f"  window.localStorage.setItem('mobile', {mobile});\n"
        + f"  window.localStorage.setItem('password', {password});\n"
        + "  var fillLoginForm = function () {\n"
        + "    var inputs = Array.prototype.slice.call(document.querySelectorAll('input'));\n"
        + "    var textInputs = inputs.filter(function (input) {\n"
        + "      return input.type === 'text' && input.autocomplete === 'on';\n"
        + "    });\n"
        + "    var passwordInput = inputs.filter(function (input) {\n"
        + "      return input.type === 'password' && input.autocomplete === 'on';\n"
        + "    })[0];\n"
        + "    if (!textInputs[0] || !passwordInput) {\n"
        + "      window.setTimeout(fillLoginForm, 50);\n"
        + "      return;\n"
        + "    }\n"
        + "    var setInputValue = function (input, value) {\n"
        + "      var setter = Object.getOwnPropertyDescriptor(\n"
        + "        HTMLInputElement.prototype, 'value'\n"
        + "      ).set;\n"
        + "      setter.call(input, value);\n"
        + "      input.dispatchEvent(new Event('input', { bubbles: true }));\n"
        + "      input.dispatchEvent(new Event('change', { bubbles: true }));\n"
        + "    };\n"
        + f"    setInputValue(textInputs[0], {mobile});\n"
        + f"    setInputValue(passwordInput, {password});\n"
        + "  };\n"
        + "  if (document.readyState === 'loading') {\n"
        + "    document.addEventListener('DOMContentLoaded', fillLoginForm);\n"
        + "  } else {\n"
        + "    fillLoginForm();\n"
        + "  }\n"
        + "})();\n"
    )


def _is_unsafe(path: PurePosixPath) -> bool:
    return path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract the life.localhost.com frontend")
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--demo-autofill", action="store_true")
    parser.add_argument("--demo-hostname", action="append", default=[])
    parser.add_argument("--demo-mobile")
    parser.add_argument("--demo-password")
    args = parser.parse_args(argv)

    prepare_frontend(
        args.source_zip,
        args.destination,
        demo_autofill=args.demo_autofill,
        demo_hostnames=tuple(args.demo_hostname),
        demo_mobile=args.demo_mobile,
        demo_password=args.demo_password,
    )
    print(args.destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

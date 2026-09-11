from pathlib import Path
from zipfile import ZipFile

import pytest

from tools.frontend_bundle import main, prepare_frontend


def test_prepare_frontend_extracts_life_assets_and_uses_relative_api(tmp_path: Path):
    source = tmp_path / "wwwroot.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr(
            "life.localhost.com/index.html",
            "<html><script src=/js/config.js></script></html>",
        )
        archive.writestr(
            "life.localhost.com/js/config.js",
            "var BASE_API_URI= '//111.230.104.153:8090/apiv1'",
        )
        archive.writestr("life.localhost.com/static/js/app.demo.js", "demo")
        archive.writestr("fendan.localhost.com/.env", "SECRET")

    destination = tmp_path / "frontend"
    result = prepare_frontend(source, destination)

    assert result == destination
    assert (destination / "index.html").read_text(encoding="utf-8").startswith("<html>")
    assert (destination / "js/config.js").read_text(encoding="utf-8") == (
        "var BASE_API_URI = '/apiv1';\n"
    )
    assert (destination / "static/js/app.demo.js").read_text() == "demo"
    assert not (destination / ".env").exists()


def test_prepare_frontend_rejects_zip_slip(tmp_path: Path):
    source = tmp_path / "unsafe.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr("life.localhost.com/../../outside.txt", "unsafe")

    with pytest.raises(ValueError, match="unsafe archive path"):
        prepare_frontend(source, tmp_path / "frontend")


def test_frontend_bundle_cli_prepares_destination(tmp_path: Path):
    source = tmp_path / "wwwroot.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr("life.localhost.com/index.html", "<html>DEMO</html>")

    destination = tmp_path / "frontend"

    assert main([str(source), str(destination)]) == 0
    assert (destination / "index.html").read_text(encoding="utf-8") == (
        "<html>DEMO</html>"
    )

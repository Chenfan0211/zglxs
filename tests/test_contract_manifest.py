import json
from collections import Counter
from pathlib import Path


def test_contract_manifest_tracks_frontend_routes_without_promoting_them():
    manifest = json.loads(
        (Path(__file__).parents[1] / "contracts/api-manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["version"] == 2
    assert manifest["fallback_enabled_by_default"] is False
    assert manifest["migrated_routes"] == []
    assert len(manifest["discovered_routes"]) == 166
    assert Counter(route["module"] for route in manifest["discovered_routes"]) == {
        "organization": 54,
        "order": 38,
        "finance": 2,
        "live": 39,
        "system": 33,
    }
    assert all(
        route["method"] == "UNKNOWN"
        and route["status"] == "discovered"
        and route["source"] == "frontend"
        for route in manifest["discovered_routes"]
    )

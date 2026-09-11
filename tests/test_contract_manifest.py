import json
from pathlib import Path


def test_initial_contract_manifest_is_explicitly_empty():
    manifest = json.loads(
        (Path(__file__).parents[1] / "contracts/api-manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["version"] == 1
    assert manifest["fallback_enabled_by_default"] is False
    assert manifest["migrated_routes"] == []
    assert manifest["discovered_routes"] == []

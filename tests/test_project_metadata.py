from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_project_metadata_has_safe_defaults_and_test_extra():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert 'python = ">=3.12,<3.13"' in pyproject
    assert "[project.optional-dependencies]" in pyproject
    assert 'DATABASE_URL=""' in env_example
    assert 'PHP_BASELINE_URL=""' not in env_example
    assert ".env" in gitignore
    assert "runtime/" in gitignore
    assert "uploads/" in gitignore

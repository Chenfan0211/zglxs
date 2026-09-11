from pathlib import Path


def test_alembic_baseline_revision_is_noop():
    revision = (
        Path(__file__).parents[1] / "alembic/versions/0001_baseline.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "0001_baseline"' in revision
    assert "def upgrade" in revision
    assert "def downgrade" in revision
    assert "pass" in revision

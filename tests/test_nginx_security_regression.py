from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_nginx_blocks_sensitive_file_suffixes_before_spa_fallback():
    nginx = (ROOT / "deploy/nginx/douyin-order-python.conf").read_text(
        encoding="utf-8"
    )

    assert r"location ~* \.(?:env|log|bak|sql)$" in nginx

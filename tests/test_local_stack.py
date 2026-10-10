from tools.local_stack import local_demo_environment


def test_local_demo_environment_reads_credentials_from_process_environment(monkeypatch):
    monkeypatch.setenv("LOCAL_DEMO_USERNAME", "local-demo")
    monkeypatch.setenv("LOCAL_DEMO_PASSWORD", "local-only-password")
    environment = local_demo_environment()

    assert environment == {
        "APP_ENV": "staging",
        "ENVIRONMENT": "staging",
        "DEMO_LOGIN_ENABLED": "true",
        "DEMO_LOGIN_USERNAME": "local-demo",
        "DEMO_LOGIN_PASSWORD": "local-only-password",
        "DEMO_CAPTCHA_CODE": "1111",
        "DEMO_CAPTCHA_KEY": "DEMO-CAPTCHA",
        "DATABASE_URL": "",
        "MIGRATION_ORGANIZATION_ENABLED": "false",
        "MIGRATION_LIVE_ENABLED": "false",
        "MIGRATION_ORDER_ENABLED": "false",
        "MIGRATION_FINANCE_ENABLED": "false",
        "MIGRATION_SYSTEM_ENABLED": "false",
    }


def test_local_demo_environment_generates_password_when_not_injected(monkeypatch):
    monkeypatch.delenv("LOCAL_DEMO_PASSWORD", raising=False)

    environment = local_demo_environment()

    assert environment["DEMO_LOGIN_USERNAME"] == "demo"
    assert environment["DEMO_LOGIN_PASSWORD"].startswith("LocalDemo-")

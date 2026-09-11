from alembic import context


def run_migrations_offline() -> None:
    context.configure(url=context.config.get_main_option("sqlalchemy.url"))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    return None


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

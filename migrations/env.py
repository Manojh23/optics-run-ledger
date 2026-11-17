from alembic import context

from ledger.db import DATABASE_URL, engine

if context.is_offline_mode():
    context.configure(url=DATABASE_URL)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()

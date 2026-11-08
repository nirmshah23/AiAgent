"""Run migrations against the explicit application database."""

from alembic import context
from voice_api.database import Base, make_engine
from voice_api.dialog.store import DialogPolicy  # noqa: F401 -- register Alembic metadata

if context.is_offline_mode():
    raise RuntimeError("Online migration required to verify the target database")
engine = make_engine()
with engine.connect() as connection:
    print("Migration target:", engine.url.render_as_string(hide_password=True))
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()

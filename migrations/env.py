import logging
from logging.config import fileConfig
from flask import current_app
from alembic import context
import os
import sys

sys.path.append(os.getcwd())

config = context.config

# Initialize Flask app before anything else
from app import create_app, db
app = create_app()
app.app_context().push()

fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

def get_engine():
    return current_app.extensions['migrate'].db.get_engine()

def get_metadata():
    return db.metadata

def run_migrations_offline():
    context.configure(
        url=app.config['SQLALCHEMY_DATABASE_URI'],
        target_metadata=get_metadata(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = get_engine()
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
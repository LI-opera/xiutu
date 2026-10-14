"""Create a NEW isolated test database; reject existing or unrelated targets."""

import argparse
import os
import re

import psycopg
from app.infrastructure.db_target import validate_target
from psycopg import sql

parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True)
args = parser.parse_args()
if not re.fullmatch(r"xiutu_test_[a-z0-9_]{1,40}", args.name):
    raise ValueError("Expected a unique xiutu_test_* name")
target = validate_target(os.environ["DATABASE_URL"], "development")
with psycopg.connect(**target.connect_kwargs(), autocommit=True) as conn:
    # CREATE DATABASE deliberately fails on collision; never drop or overwrite one.
    conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(args.name)))
print("Created isolated test database:", args.name)

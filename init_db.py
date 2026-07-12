"""
init_db.py  —  build the database from scratch.

    python init_db.py

Creates all tables from schema.sql and seeds the recipes. The users and
plan_entries tables start empty and fill up as people sign up and plan meals.
Re-running drops and rebuilds everything (you'll lose test accounts/plans).
"""

import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
DB_PATH = HERE / "pantry.db"

LIST_FIELDS = ["appliances", "diets", "allergens", "ingredients", "steps", "tips"]
COLUMNS = ["id", "name", "slug", "icon", "category", "time", "prep_time",
           "cook_time", "servings", "base_servings", "calories", "skill", "blurb", "description",
           "appliances", "diets", "allergens", "ingredients", "steps", "tips"]


def main():
    recipes = json.loads((HERE / "recipes.json").read_text())
    schema = (HERE / "schema.sql").read_text()

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(schema)

    placeholders = ", ".join(f":{c}" for c in COLUMNS)
    insert_sql = f"INSERT INTO recipes ({', '.join(COLUMNS)}) VALUES ({placeholders})"
    for r in recipes:
        row = dict(r)
        for field in LIST_FIELDS:
            row[field] = json.dumps(row[field])
        conn.execute(insert_sql, row)

    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    conn.close()
    print(f"Database ready: {DB_PATH}  ({count} recipes loaded)")


if __name__ == "__main__":
    main()

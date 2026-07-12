-- Pixel Pantry database schema.

DROP TABLE IF EXISTS recipes;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS plan_entries;
DROP TABLE IF EXISTS cooked_log;
DROP TABLE IF EXISTS groups;
DROP TABLE IF EXISTS group_members;

CREATE TABLE recipes (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE,
    icon TEXT NOT NULL, category TEXT NOT NULL, time INTEGER NOT NULL,
    prep_time INTEGER NOT NULL, cook_time INTEGER NOT NULL, servings TEXT NOT NULL,
    base_servings INTEGER NOT NULL,     -- numeric base, so portions can scale
    calories INTEGER NOT NULL, skill TEXT NOT NULL, blurb TEXT, description TEXT,
    appliances TEXT NOT NULL, diets TEXT NOT NULL, allergens TEXT NOT NULL,
    ingredients TEXT NOT NULL, steps TEXT NOT NULL, tips TEXT NOT NULL
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    -- meal-time preferences (for reminders); NULL until the user sets them
    breakfast_time  TEXT,
    lunch_time      TEXT,
    dinner_time     TEXT,
    reminder_minutes INTEGER DEFAULT 0   -- 0 = reminders off
);

CREATE TABLE plan_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day TEXT NOT NULL, meal TEXT NOT NULL,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    cooked INTEGER NOT NULL DEFAULT 0,
    cooked_at TEXT,
    for_group INTEGER NOT NULL DEFAULT 0   -- labeled as a group-rotation meal
);

CREATE TABLE cooked_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipe_id INTEGER NOT NULL, name TEXT NOT NULL, category TEXT NOT NULL,
    icon TEXT NOT NULL, calories INTEGER NOT NULL, points INTEGER NOT NULL,
    cooked_at TEXT NOT NULL
);

-- Cooking groups (dorm rotation). A user is in at most one group at a time.
CREATE TABLE groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);

CREATE TABLE group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    user_id  INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE
);

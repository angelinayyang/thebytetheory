"""
The Byte Theory — student recipe finder, meal planner, and cooking-group app.

Features: recipe gallery + filters, accounts, weekly meal planner, grocery list,
gamified profile (points/badges/streaks), cooking groups that scale portions,
and meal-time reminder preferences.

Run:  python init_db.py   then   flask --app app run --debug
"""
import os
import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (Flask, render_template, request, abort, session,
                   redirect, url_for, flash)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "thebytetheory711")
DB_PATH = Path(__file__).parent / "pantry.db"

LIST_FIELDS = ["appliances", "diets", "allergens", "ingredients", "steps", "tips"]
MEAL_SLOTS = ["breakfast", "lunch", "dinner", "snack"]
POINTS_PER_COOK = 10
REMINDER_OPTIONS = [0, 15, 30, 45, 60]
CATEGORY_TINT = {"breakfast": "#F6E7C1", "lunch": "#DCE7D0", "dinner": "#F1D9C6",
                 "dessert": "#F3D6DE", "snack": "#E3DCEF", "side": "#D6E6E6"}
CATEGORY_ORDER = ["breakfast", "lunch", "dinner", "side", "snack", "dessert"]


# ---------------------------------------------------------------- db helpers
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def parse(row):
    r = dict(row)
    for f in LIST_FIELDS:
        if f in r:
            r[f] = json.loads(r[f])
    r["tint"] = CATEGORY_TINT.get(r.get("category"), "#EDE6DA")
    return r


# ------------------------------------------------------------ portion scaling
_FRACTIONS = [(0.125, "1/8"), (0.25, "1/4"), (0.333, "1/3"), (0.375, "3/8"),
              (0.5, "1/2"), (0.625, "5/8"), (0.667, "2/3"), (0.75, "3/4"),
              (0.875, "7/8")]
_QTY_RE = re.compile(r"^(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"
                     r"(?:\s*[\u2013-]\s*(\d+(?:\.\d+)?))?")


def _parse_qty(tok):
    tok = tok.strip()
    if " " in tok and "/" in tok:
        whole, frac = tok.split(" ", 1)
        n, d = frac.split("/")
        return float(whole) + float(n) / float(d)
    if "/" in tok:
        n, d = tok.split("/")
        return float(n) / float(d)
    return float(tok)


def _fmt_qty(x):
    whole = int(round(x)) if abs(x - round(x)) < 0.001 else int(x)
    frac = x - int(x)
    for val, label in _FRACTIONS:
        if abs(frac - val) < 0.06:
            return f"{int(x)} {label}" if int(x) else label
    if frac < 0.06:
        return str(int(round(x)))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def scale_line(line, factor):
    """Scale the leading quantity in an ingredient line; leave 'Salt' etc alone."""
    if factor == 1:
        return line
    m = _QTY_RE.match(line)
    if not m:
        return line
    first = _fmt_qty(_parse_qty(m.group(1)) * factor)
    rest = line[m.end():]
    if m.group(2):
        second = _fmt_qty(float(m.group(2)) * factor)
        return f"{first}\u2013{second}{rest}"
    return f"{first}{rest}"


def scale_ingredients(lines, factor):
    return [scale_line(l, factor) for l in lines]


# ---------------------------------------------------------------- auth helpers
def current_user():
    uid = session.get("user_id")
    if uid is None:
        return None
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    return row


def login_required(view):
    @wraps(view)
    def wrapped(*a, **k):
        if session.get("user_id") is None:
            return redirect(url_for("login", next=request.path))
        return view(*a, **k)
    return wrapped


# ---------------------------------------------------------------- group helper
def user_group(uid):
    """Return {group, members, size, is_owner} for the user's group, or None."""
    conn = get_db()
    gm = conn.execute("SELECT group_id FROM group_members WHERE user_id = ?", (uid,)).fetchone()
    if gm is None:
        conn.close()
        return None
    g = conn.execute("SELECT * FROM groups WHERE id = ?", (gm["group_id"],)).fetchone()
    members = conn.execute(
        """SELECT u.id, u.username FROM group_members m JOIN users u ON u.id = m.user_id
           WHERE m.group_id = ? ORDER BY u.username""", (gm["group_id"],)).fetchall()
    conn.close()
    if g is None:
        return None
    return {"group": g, "members": members, "size": len(members),
            "is_owner": g["owner_id"] == uid}


@app.context_processor
def inject_globals():
    u = current_user()
    grp = user_group(u["id"]) if u else None
    prefs = None
    if u and u["reminder_minutes"]:
        prefs = {"breakfast": u["breakfast_time"], "lunch": u["lunch_time"],
                 "dinner": u["dinner_time"], "lead": u["reminder_minutes"]}
    return {"user": u, "group": grp, "prefs": prefs}


# ---------------------------------------------------------------- recipes
@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    diet = request.args.get("diet", "").strip()
    max_time = request.args.get("max_time", "").strip()
    have = request.args.getlist("appliance")
    avoid = request.args.getlist("avoid")

    conn = get_db()
    sql, params = "SELECT * FROM recipes WHERE 1=1", []
    if category:
        sql += " AND category = ?"; params.append(category)
    if q:
        sql += " AND (name LIKE ? OR description LIKE ?)"; params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY name"
    recipes = [parse(r) for r in conn.execute(sql, params).fetchall()]

    if have:
        hs = set(have); recipes = [r for r in recipes if set(r["appliances"]).issubset(hs)]
    if avoid:
        av = set(avoid); recipes = [r for r in recipes if not (set(r["allergens"]) & av)]
    if diet:
        recipes = [r for r in recipes if diet in r["diets"]]
    if max_time.isdigit():
        recipes = [r for r in recipes if r["time"] <= int(max_time)]

    everything = [parse(r) for r in conn.execute("SELECT * FROM recipes").fetchall()]
    conn.close()
    appliances = sorted({a for r in everything for a in r["appliances"]})
    diets = sorted({d for r in everything for d in r["diets"]})
    allergens = sorted({a for r in everything for a in r["allergens"]})
    categories = [c for c in CATEGORY_ORDER if any(r["category"] == c for r in everything)]
    active = {"q": q, "category": category, "diet": diet, "max_time": max_time,
              "appliance": have, "avoid": avoid}
    carry = {k: v for k, v in active.items() if k != "category" and v}
    return render_template("index.html", recipes=recipes, total=len(everything),
                           categories=categories, appliances=appliances, diets=diets,
                           allergens=allergens, active=active, carry=carry)


@app.route("/recipe/<int:recipe_id>")
def recipe(recipe_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    conn.close()
    if row is None:
        abort(404)
    r = parse(row)
    base = r["base_servings"] or 1
    # Default to the recipe's own serving size. The group multiplier is applied
    # per meal via the "for group" label on the planner, not on every view.
    serves = request.args.get("serves", type=int) or base
    serves = max(1, min(serves, 24))
    r["ingredients"] = scale_ingredients(r["ingredients"], serves / base)
    grp = user_group(session["user_id"]) if session.get("user_id") else None
    return render_template("recipe.html", r=r, meal_slots=MEAL_SLOTS,
                           today=date.today().isoformat(), serves=serves,
                           base_servings=base, group_default=(grp["size"] if grp else None))


# ---------------------------------------------------------------- accounts
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        error = None
        if len(username) < 3:
            error = "Username needs to be at least 3 characters."
        elif len(password) < 6:
            error = "Password needs to be at least 6 characters."
        if error is None:
            conn = get_db()
            if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
                error = "That username is taken."
            else:
                conn.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
                             (username, generate_password_hash(password), datetime.now().isoformat()))
                conn.commit()
                uid = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]
                conn.close()
                session.clear(); session["user_id"] = uid
                return redirect(url_for("welcome"))
            conn.close()
        flash(error, "error")
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        u = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if u is None or not check_password_hash(u["password_hash"], password):
            flash("Wrong username or password.", "error")
        else:
            session.clear(); session["user_id"] = u["id"]
            return redirect(request.args.get("next") or url_for("planner"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------- preferences
def _save_prefs(uid, form):
    def t(name, default):
        v = form.get(name, "").strip()
        return v if re.fullmatch(r"\d{2}:\d{2}", v or "") else default
    lead = form.get("reminder_minutes", type=int) or 0
    if lead not in REMINDER_OPTIONS:
        lead = 0
    conn = get_db()
    conn.execute("""UPDATE users SET breakfast_time=?, lunch_time=?, dinner_time=?,
                    reminder_minutes=? WHERE id=?""",
                 (t("breakfast_time", "08:00"), t("lunch_time", "12:30"),
                  t("dinner_time", "18:30"), lead, uid))
    conn.commit(); conn.close()


@app.route("/welcome", methods=["GET", "POST"])
@login_required
def welcome():
    if request.method == "POST":
        _save_prefs(session["user_id"], request.form)
        return redirect(url_for("planner"))
    return render_template("welcome.html", u=current_user(), options=REMINDER_OPTIONS)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        _save_prefs(session["user_id"], request.form)
        flash("Preferences saved.", "ok")
        return redirect(url_for("settings"))
    return render_template("settings.html", u=current_user(), options=REMINDER_OPTIONS)


# ---------------------------------------------------------------- planner
def monday_of(d):
    return d - timedelta(days=d.weekday())


def parse_week_start(arg):
    try:
        return monday_of(datetime.strptime(arg, "%Y-%m-%d").date())
    except (ValueError, TypeError):
        return monday_of(date.today())


@app.route("/planner")
@login_required
def planner():
    start = parse_week_start(request.args.get("start"))
    day_isos = [(start + timedelta(days=i)).isoformat() for i in range(7)]
    conn = get_db()
    rows = conn.execute(
        """SELECT p.id AS entry_id, p.day, p.meal, p.cooked, p.for_group, r.* FROM plan_entries p
           JOIN recipes r ON r.id = p.recipe_id
           WHERE p.user_id = ? AND p.day BETWEEN ? AND ?""",
        (session["user_id"], day_isos[0], day_isos[-1])).fetchall()
    all_recipes = [parse(r) for r in conn.execute(
        "SELECT id, name, category, calories FROM recipes ORDER BY name").fetchall()]
    conn.close()
    grid = {d: {m: [] for m in MEAL_SLOTS} for d in day_isos}
    totals = {d: 0 for d in day_isos}
    for row in rows:
        e = parse(row); grid[e["day"]][e["meal"]].append(e); totals[e["day"]] += e["calories"]
    return render_template("planner.html", day_isos=day_isos, grid=grid, totals=totals,
                           meal_slots=MEAL_SLOTS, all_recipes=all_recipes,
                           prev_week=(start - timedelta(days=7)).isoformat(),
                           next_week=(start + timedelta(days=7)).isoformat(),
                           start_iso=start.isoformat(), week_total=sum(totals.values()))


@app.route("/plan/add", methods=["POST"])
@login_required
def plan_add():
    recipe_id = request.form.get("recipe_id", type=int)
    day = request.form.get("day", "")
    meal = request.form.get("meal", "")
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        day = ""
    if recipe_id and day and meal in MEAL_SLOTS:
        conn = get_db()
        if conn.execute("SELECT 1 FROM recipes WHERE id = ?", (recipe_id,)).fetchone():
            conn.execute("INSERT INTO plan_entries (user_id, day, meal, recipe_id) VALUES (?,?,?,?)",
                         (session["user_id"], day, meal, recipe_id))
            conn.commit(); flash("Added to your plan.", "ok")
        conn.close()
    return redirect(request.form.get("next") or url_for("planner", start=day))


@app.route("/plan/remove", methods=["POST"])
@login_required
def plan_remove():
    conn = get_db()
    conn.execute("DELETE FROM plan_entries WHERE id = ? AND user_id = ?",
                 (request.form.get("entry_id", type=int), session["user_id"]))
    conn.commit(); conn.close()
    return redirect(request.form.get("next") or url_for("planner"))


@app.route("/plan/group_toggle", methods=["POST"])
@login_required
def plan_group_toggle():
    """Flag/unflag a planned meal as a group-rotation meal. Only meaningful if
    you're in a cooking group; group meals are the only ones scaled to group size."""
    entry_id = request.form.get("entry_id", type=int)
    if user_group(session["user_id"]):
        conn = get_db()
        conn.execute("""UPDATE plan_entries SET for_group = 1 - for_group
                        WHERE id = ? AND user_id = ?""", (entry_id, session["user_id"]))
        conn.commit(); conn.close()
    else:
        flash("Join a cooking group first to label group meals.", "error")
    return redirect(request.form.get("next") or url_for("planner"))


# ---------------------------------------------------------------- cooking / profile
@app.route("/plan/cook", methods=["POST"])
@login_required
def plan_cook():
    """Mark a planned entry as cooked: award points once and lock the entry."""
    entry_id = request.form.get("entry_id", type=int)
    conn = get_db()
    row = conn.execute(
        """SELECT p.id AS entry_id, p.cooked, r.id AS rid, r.name, r.category,
                  r.icon, r.calories
           FROM plan_entries p JOIN recipes r ON r.id = p.recipe_id
           WHERE p.id = ? AND p.user_id = ?""",
        (entry_id, session["user_id"])).fetchone()
    if row and not row["cooked"]:
        now = datetime.now().isoformat()
        conn.execute("UPDATE plan_entries SET cooked = 1, cooked_at = ? WHERE id = ?",
                     (now, entry_id))
        conn.execute("""INSERT INTO cooked_log
            (user_id, recipe_id, name, category, icon, calories, points, cooked_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (session["user_id"], row["rid"], row["name"], row["category"],
             row["icon"], row["calories"], POINTS_PER_COOK, now))
        conn.commit()
        flash(f"Nice! +{POINTS_PER_COOK} points for cooking {row['name']}.", "ok")
    conn.close()
    return redirect(request.form.get("next") or url_for("planner"))


def cooking_streak(dates):
    if not dates:
        return 0
    days = sorted(set(dates), reverse=True)
    if days[0] < date.today() - timedelta(days=1):
        return 0
    streak, cur, dayset = 0, days[0], set(days)
    while cur in dayset:
        streak += 1; cur -= timedelta(days=1)
    return streak


@app.route("/profile")
@login_required
def profile():
    conn = get_db()
    log = [dict(r) for r in conn.execute(
        "SELECT * FROM cooked_log WHERE user_id = ? ORDER BY cooked_at DESC",
        (session["user_id"],)).fetchall()]
    conn.close()
    meals = len(log)
    points = sum(c["points"] for c in log)
    total_cal = sum(c["calories"] for c in log)
    avg_cal = round(total_cal / meals) if meals else 0
    level, into = points // 50 + 1, points % 50
    dates = [datetime.fromisoformat(c["cooked_at"]).date() for c in log]
    streak = cooking_streak(dates)
    week_start = date.today() - timedelta(days=date.today().weekday())
    week_cal = sum(c["calories"] for c, d in zip(log, dates) if d >= week_start)
    cats = {}
    for c in log:
        cats[c["category"]] = cats.get(c["category"], 0) + 1
    cats = sorted(cats.items(), key=lambda kv: -kv[1])
    desserts = sum(1 for c in log if c["category"] == "dessert")
    badges = [
        {"name": "First Bite", "desc": "Cook your first meal", "icon": "39_friedegg_dish.png", "earned": meals >= 1},
        {"name": "Warmed Up", "desc": "Cook 5 meals", "icon": "87_ramen.png", "earned": meals >= 5},
        {"name": "Home Chef", "desc": "Cook 15 meals", "icon": "33_curry_dish.png", "earned": meals >= 15},
        {"name": "Iron Chef", "desc": "Cook 30 meals", "icon": "96_steak_dish.png", "earned": meals >= 30},
        {"name": "On a Roll", "desc": "3-day cooking streak", "icon": "98_sushi_dish.png", "earned": streak >= 3},
        {"name": "Week Warrior", "desc": "7-day cooking streak", "icon": "82_pizza_dish.png", "earned": streak >= 7},
        {"name": "Balanced Plate", "desc": "Cook 4 categories", "icon": "04_bowl.png", "earned": len(cats) >= 4},
        {"name": "Sweet Tooth", "desc": "Cook 3 desserts", "icon": "35_donut_dish.png", "earned": desserts >= 3},
    ]
    recent = []
    for c in log[:8]:
        c = dict(c); c["when"] = datetime.fromisoformat(c["cooked_at"]).strftime("%b %-d"); recent.append(c)
    stats = {"meals": meals, "points": points, "level": level, "to_next": 50 - into,
             "progress": round(into / 50 * 100), "streak": streak, "total_cal": total_cal,
             "avg_cal": avg_cal, "week_cal": week_cal,
             "earned": sum(1 for b in badges if b["earned"]), "total_badges": len(badges)}
    return render_template("profile.html", stats=stats, badges=badges, cats=cats,
                           recent=recent, tints=CATEGORY_TINT)


# ---------------------------------------------------------------- grocery list
_UNITS = {"cup", "cups", "tbsp", "tsp", "g", "kg", "ml", "l", "oz", "lb", "clove",
          "cloves", "can", "cans", "packet", "pack", "slice", "slices", "sheet",
          "sheets", "handful", "pinch", "stick", "sticks", "strip", "strips", "big"}
_STOP = _UNITS | {"of", "a", "an", "the", "or", "and", "to", "serve", "taste", "for",
                  "with", "optional", "other", "some", "few", "your", "plus"}
_DESCRIPTORS = {"large", "small", "medium", "ripe", "fresh", "whole", "plain", "soft",
                "thin", "thick", "grated", "chopped", "sliced", "diced", "cooked",
                "warm", "boiling", "toasted", "crisp", "runny"}


def grocery_key(line):
    """Reduce an ingredient line to a clean core item for the shopping list.
    '1 plain or sesame bagel, halved' -> 'sesame bagel'."""
    core = line.split(",")[0]
    core = re.sub(r"\([^)]*\)", "", core)
    core = re.sub(r"(?i)^optional:?\s*", "", core)
    words = []
    leading = True
    for tok in core.split():
        low = tok.lower().strip(".:")
        if leading and (re.fullmatch(r"[\d/\u2013.\-]+", tok) or low in _UNITS):
            continue
        leading = False
        if low in _STOP or low in _DESCRIPTORS or not low:
            continue
        words.append(low)
    if words:
        words[-1] = re.sub(r"s$", "", words[-1])
    return " ".join(words).strip()


@app.route("/grocery")
@login_required
def grocery():
    start = parse_week_start(request.args.get("start"))
    day_isos = [(start + timedelta(days=i)).isoformat() for i in range(7)]
    grp = user_group(session["user_id"])

    conn = get_db()
    rows = conn.execute(
        """SELECT DISTINCT r.name, r.ingredients, r.base_servings, p.for_group
           FROM plan_entries p JOIN recipes r ON r.id = p.recipe_id
           WHERE p.user_id = ? AND p.day BETWEEN ? AND ?""",
        (session["user_id"], day_isos[0], day_isos[-1])).fetchall()
    conn.close()

    groups = {}
    for row in rows:
        base = row["base_servings"] or 1
        # Only meals you labeled "for the group" get multiplied to group size.
        factor = (grp["size"] / base) if (grp and row["for_group"]) else 1
        for line in scale_ingredients(json.loads(row["ingredients"]), factor):
            key = grocery_key(line)
            if not key:
                continue
            g = groups.setdefault(key, {"display": key, "amounts": [], "recipes": set()})
            g["amounts"].append(line)
            g["recipes"].add(row["name"])
    items = sorted(({"display": g["display"], "amounts": g["amounts"],
                     "recipes": sorted(g["recipes"])} for g in groups.values()),
                   key=lambda x: x["display"])
    return render_template("grocery.html", items=items, start_iso=start.isoformat(),
                           prev_week=(start - timedelta(days=7)).isoformat(),
                           next_week=(start + timedelta(days=7)).isoformat(),
                           day_isos=day_isos, group=grp)


# ---------------------------------------------------------------- cooking groups
@app.route("/group")
@login_required
def group_page():
    g = user_group(session["user_id"])
    meals = []
    if g:
        member_ids = [m["id"] for m in g["members"]]
        placeholders = ",".join("?" * len(member_ids))
        conn = get_db()
        meals = [dict(row) for row in conn.execute(
            f"""SELECT p.day, p.meal, p.cooked, r.name, r.icon,
                       r.category, u.username
                FROM plan_entries p JOIN recipes r ON r.id = p.recipe_id
                JOIN users u ON u.id = p.user_id
                WHERE p.for_group = 1 AND p.user_id IN ({placeholders})
                ORDER BY p.day, p.meal""", member_ids).fetchall()]
        conn.close()
        for m in meals:
            m["tint"] = CATEGORY_TINT.get(m["category"], "#EDE6DA")
            m["daylabel"] = datetime.strptime(m["day"], "%Y-%m-%d").strftime("%a %b %-d")
    return render_template("group.html", g=g, meals=meals)


@app.route("/group/create", methods=["POST"])
@login_required
def group_create():
    name = request.form.get("name", "").strip() or "My cooking group"
    if user_group(session["user_id"]):
        flash("You're already in a group — leave it first.", "error")
        return redirect(url_for("group_page"))
    conn = get_db()
    cur = conn.execute("INSERT INTO groups (name, owner_id, created_at) VALUES (?,?,?)",
                       (name[:60], session["user_id"], datetime.now().isoformat()))
    conn.execute("INSERT INTO group_members (group_id, user_id) VALUES (?,?)",
                 (cur.lastrowid, session["user_id"]))
    conn.commit(); conn.close()
    flash("Group created — add your hall-mates by username.", "ok")
    return redirect(url_for("group_page"))


@app.route("/group/add", methods=["POST"])
@login_required
def group_add():
    grp = user_group(session["user_id"])
    if not grp or not grp["is_owner"]:
        flash("Only the group owner can add members.", "error")
        return redirect(url_for("group_page"))
    username = request.form.get("username", "").strip()
    conn = get_db()
    u = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if u is None:
        flash(f"No user called '{username}'.", "error")
    elif conn.execute("SELECT 1 FROM group_members WHERE user_id = ?", (u["id"],)).fetchone():
        flash(f"{username} is already in a cooking group.", "error")
    else:
        conn.execute("INSERT INTO group_members (group_id, user_id) VALUES (?,?)",
                     (grp["group"]["id"], u["id"]))
        conn.commit(); flash(f"Added {username} to the group.", "ok")
    conn.close()
    return redirect(url_for("group_page"))


@app.route("/group/remove", methods=["POST"])
@login_required
def group_remove():
    grp = user_group(session["user_id"])
    target = request.form.get("user_id", type=int)
    if grp and grp["is_owner"] and target and target != session["user_id"]:
        conn = get_db()
        conn.execute("UPDATE plan_entries SET for_group = 0 WHERE user_id = ?", (target,))
        conn.execute("DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
                     (grp["group"]["id"], target))
        conn.commit(); conn.close()
    return redirect(url_for("group_page"))


@app.route("/group/leave", methods=["POST"])
@login_required
def group_leave():
    grp = user_group(session["user_id"])
    if grp:
        conn = get_db()
        gid = grp["group"]["id"]
        if grp["is_owner"]:
            # Disbanding: clear the group label from every member's plan entries
            # so no orphaned "Group" tags are left behind.
            member_ids = [m["id"] for m in grp["members"]]
            ph = ",".join("?" * len(member_ids))
            conn.execute(f"UPDATE plan_entries SET for_group = 0 WHERE user_id IN ({ph})",
                         member_ids)
            conn.execute("DELETE FROM groups WHERE id = ?", (gid,))
            conn.execute("DELETE FROM group_members WHERE group_id = ?", (gid,))
            flash("Group disbanded.", "ok")
        else:
            conn.execute("UPDATE plan_entries SET for_group = 0 WHERE user_id = ?",
                         (session["user_id"],))
            conn.execute("DELETE FROM group_members WHERE user_id = ?", (session["user_id"],))
            flash("You left the group.", "ok")
        conn.commit(); conn.close()
    return redirect(url_for("group_page"))


# ---------------------------------------------------------------- filters
@app.template_filter("titlecase")
def titlecase(value):
    return value.replace("_", " ").capitalize()


@app.template_filter("wday")
def wday(iso):
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%a %-d")


if __name__ == "__main__":
    app.run(debug=True)

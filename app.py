from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import os
from datetime import datetime, date
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")
DB_PATH = os.path.join(BASE_DIR, "kakeibo.db")

CATEGORY_DATA = {
    "expense": [
        {"name": "食費", "icon": "🍴", "color": "#A7CF4A"},
        {"name": "交際費", "icon": "🎁", "color": "#E97B87"},
        {"name": "日用雑貨", "icon": "🪥", "color": "#6EC6D9"},
        {"name": "住まい", "icon": "🏠", "color": "#E78ACF"},
        {"name": "趣味", "icon": "🎵", "color": "#E39A27"},
        {"name": "水道・光熱費", "icon": "💡", "color": "#E6CF3A"},
        {"name": "通信", "icon": "📱", "color": "#6676D9"},
        {"name": "クルマ", "icon": "🚗", "color": "#F08A6B"},
        {"name": "交通", "icon": "🚃", "color": "#8E63D9"},
        {"name": "美容", "icon": "👕", "color": "#59BE7D"},
        {"name": "医療・保健", "icon": "🏥", "color": "#D4CF39"},
        {"name": "税金", "icon": "🧾", "color": "#8FA4B2"},
        {"name": "教育", "icon": "🎓", "color": "#B67852"},
        {"name": "大型出費", "icon": "✈️", "color": "#90A9B8"},
        {"name": "その他", "icon": "•••", "color": "#AFC1CF"}
    ],
    "income": [
        {"name": "給与所得", "icon": "💴", "color": "#2563EB"},
        {"name": "賞与", "icon": "💴", "color": "#0EA5E9"},
        {"name": "事業所得", "icon": "💴", "color": "#14B8A6"},
        {"name": "臨時収入", "icon": "💴", "color": "#22C55E"},
        {"name": "立替金返済", "icon": "💴", "color": "#06B6D4"},
        {"name": "その他", "icon": "💴", "color": "#64748B"}
    ]
}

SUBCATEGORY_DATA = {
    "食費": ["食料品", "カフェ", "朝ご飯", "昼ご飯", "晩ご飯", "その他"],
    "交際費": ["飲み会", "プレゼント", "ご祝儀・香典", "その他"],
    "日用雑貨": ["消耗品", "子ども関連", "ペット関連", "タバコ", "その他"],
    "住まい": ["家賃", "住宅ローン返済", "家具", "家電", "リフォーム", "住宅保険", "その他"],
    "趣味": ["レジャー", "イベント", "映画・動画", "音楽", "漫画", "書籍", "ゲーム", "その他"],
    "水道・光熱費": ["水道料金", "電気料金", "ガス料金", "その他"],
    "通信": ["携帯電話料金", "固定電話料金", "インターネット関連費", "放送サービス料金", "宅配便", "切手・はがき", "その他"],
    "クルマ": ["ガソリン", "駐車場", "自動車保険", "自動車税", "自動車ローン", "免許教習", "高速料金", "その他"],
    "交通": ["電車", "タクシー", "バス", "飛行機", "その他"],
    "美容": ["洋服", "アクセサリー・小物", "下着", "ジム・健康", "美容院", "コスメ", "エステ・ネイル", "クリーニング", "その他"],
    "医療・保健": ["病院代", "薬代", "生命保険", "医療保険", "その他"],
    "税金": ["年金", "所得税", "消費税", "住民税", "個人事業税", "その他"],
    "教育": ["習い事", "新聞", "参考書", "受験料", "学費", "学資保険", "塾", "その他"],
    "大型出費": ["旅行", "住宅", "自動車", "バイク", "結婚", "出産", "介護", "家具", "家電", "その他"],
    "その他": ["仕送り", "お小遣い", "使途不明金", "立替金", "未分類", "現金の引出", "その他", "カードの引落", "電子マネーにチャージ"]
}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tx_date TEXT NOT NULL,
            amount INTEGER NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            memo TEXT,
            type TEXT NOT NULL DEFAULT 'expense',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            amount INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, month, category),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)



    cur.execute("PRAGMA table_info(transactions)")
    existing_columns = {row["name"] for row in cur.fetchall()}

    if "subcategory" not in existing_columns:
        cur.execute("ALTER TABLE transactions ADD COLUMN subcategory TEXT")

    conn.commit()
    conn.close()


init_db()


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped


def get_month_range(month_str):
    start_dt = datetime.strptime(month_str, "%Y-%m")
    year = start_dt.year
    month = start_dt.month

    if month == 12:
        next_dt = datetime(year + 1, 1, 1)
    else:
        next_dt = datetime(year, month + 1, 1)

    return start_dt.date().isoformat(), next_dt.date().isoformat()


def build_category_totals(rows, category_definitions):
    existing_totals = {
        row["category"]: int(row["total"] or 0)
        for row in rows
    }

    categories = []
    for item in category_definitions:
        categories.append({
            "name": item["name"],
            "icon": item["icon"],
            "color": item["color"],
            "total": existing_totals.get(item["name"], 0)
        })
    return categories
def build_subcategory_totals(category_name, rows):
    existing_totals = {
        (row["subcategory"] or "その他"): int(row["total"] or 0)
        for row in rows
    }

    definitions = SUBCATEGORY_DATA.get(category_name, ["その他"])

    subcategories = []
    for index, name in enumerate(definitions):
        subcategories.append({
            "name": name,
            "total": existing_totals.get(name, 0),
            "order": index
        })

    return subcategories
def get_budget_amounts_for_month(conn, user_id, month):
    cur = conn.cursor()
    cur.execute("""
        SELECT category, amount
        FROM budgets
        WHERE user_id = ? AND month = ?
    """, (user_id, month))
    rows = cur.fetchall()
    return {
        row["category"]: int(row["amount"] or 0)
        for row in rows
    }


def build_budget_info(spent, budget_amount):
    spent = int(spent or 0)
    budget_amount = int(budget_amount or 0)

    if budget_amount > 0:
        remaining = budget_amount - spent
        ratio = round((spent / budget_amount) * 100, 1)
    else:
        remaining = 0
        ratio = 0

    return {
        "spent": spent,
        "budget_amount": budget_amount,
        "budget_remaining": remaining,
        "budget_ratio": ratio,
        "has_budget": budget_amount > 0,
        "is_over_budget": budget_amount > 0 and spent > budget_amount
    }


def get_expense_total_for_budget(conn, user_id, start_date, end_date, category=""):
    cur = conn.cursor()

    if category:
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE user_id = ?
              AND type = 'expense'
              AND category = ?
              AND tx_date >= ?
              AND tx_date < ?
        """, (user_id, category, start_date, end_date))
    else:
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE user_id = ?
              AND type = 'expense'
              AND tx_date >= ?
              AND tx_date < ?
        """, (user_id, start_date, end_date))

    row = cur.fetchone()
    return int(row["total"] or 0)

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("calendar"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            error = "ユーザー名とパスワードを入力してください。"
            return render_template("register.html", error=error)

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        existing = cur.fetchone()

        if existing:
            conn.close()
            error = "そのユーザー名はすでに使われています。"
            return render_template("register.html", error=error)

        password_hash = generate_password_hash(password)

        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        conn.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            error = "ユーザー名またはパスワードが違います。"
            return render_template("login.html", error=error)

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]

        return redirect(url_for("calendar"))

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/calendar")
@login_required
def calendar():
    today = date.today().isoformat()
    return render_template(
        "calendar.html",
        today=today,
        username=session.get("username"),
        active_page="calendar",
        categories=CATEGORY_DATA,
        subcategories=SUBCATEGORY_DATA
    )


@app.route("/graph")
@login_required
def graph():
    today = date.today()
    current_month = today.strftime("%Y-%m")
    return render_template(
        "graph.html",
        username=session.get("username"),
        active_page="graph",
        categories=CATEGORY_DATA,
        current_month=current_month
    )


@app.route("/analysis")
@login_required
def analysis():
    today = date.today()
    current_month = today.strftime("%Y-%m")
    return render_template(
        "analysis.html",
        username=session.get("username"),
        active_page="analysis",
        current_month=current_month
    )


@app.route("/api/events")
@login_required
def api_events():
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return jsonify([])

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT tx_date, type, SUM(amount) AS total
        FROM transactions
        WHERE user_id = ? AND tx_date >= ? AND tx_date < ?
        GROUP BY tx_date, type
        ORDER BY tx_date, type
    """, (session["user_id"], start[:10], end[:10]))
    rows = cur.fetchall()
    conn.close()

    events = []
    for r in rows:
        total = int(r["total"]) if r["total"] is not None else 0
        tx_type = r["type"]

        if tx_type == "income":
            events.append({
                "title": f"{total:,}円",
                "start": r["tx_date"],
                "allDay": True,
                "textColor": "#2563eb",
                "backgroundColor": "transparent",
                "borderColor": "transparent"
            })
        else:
            events.append({
                "title": f"{total:,}円",
                "start": r["tx_date"],
                "allDay": True,
                "textColor": "#dc2626",
                "backgroundColor": "transparent",
                "borderColor": "transparent"
            })

    return jsonify(events)


@app.route("/api/day")
@login_required
def api_day():
    tx_date = request.args.get("date")
    if not tx_date:
        return jsonify([])

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, tx_date, amount, category, subcategory, memo, type
        FROM transactions
        WHERE user_id = ? AND tx_date = ?
        ORDER BY id DESC
    """, (session["user_id"], tx_date[:10]))
    rows = cur.fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])


@app.route("/api/graph_month")
@login_required
def api_graph_month():
    month = request.args.get("month")

    try:
        start_date, end_date = get_month_range(month)
    except Exception:
        return jsonify({"ok": False, "error": "month is invalid"}), 400

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT type, COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE user_id = ? AND tx_date >= ? AND tx_date < ?
        GROUP BY type
    """, (session["user_id"], start_date, end_date))
    totals_rows = cur.fetchall()

    income_total = 0
    expense_total = 0

    for row in totals_rows:
        if row["type"] == "income":
            income_total = int(row["total"] or 0)
        elif row["type"] == "expense":
            expense_total = int(row["total"] or 0)

    cur.execute("""
        SELECT category, SUM(amount) AS total
        FROM transactions
        WHERE user_id = ? AND type = 'expense' AND tx_date >= ? AND tx_date < ?
        GROUP BY category
        ORDER BY total DESC, category
    """, (session["user_id"], start_date, end_date))
    expense_rows = cur.fetchall()

    cur.execute("""
        SELECT category, SUM(amount) AS total
        FROM transactions
        WHERE user_id = ? AND type = 'income' AND tx_date >= ? AND tx_date < ?
        GROUP BY category
        ORDER BY total DESC, category
    """, (session["user_id"], start_date, end_date))
    income_rows = cur.fetchall()

    budget_map = get_budget_amounts_for_month(conn, session["user_id"], month)

    conn.close()

    expense_categories = build_category_totals(expense_rows, CATEGORY_DATA["expense"])
    income_categories = build_category_totals(income_rows, CATEGORY_DATA["income"])

    for item in expense_categories:
        item.update(build_budget_info(
            spent=item["total"],
            budget_amount=budget_map.get(item["name"], 0)
        ))

    expense_chart_categories = [c for c in expense_categories if c["total"] > 0]
    income_chart_categories = [c for c in income_categories if c["total"] > 0]

    net = income_total - expense_total
    expense_budget = build_budget_info(
        spent=expense_total,
        budget_amount=budget_map.get("", 0)
    )

    return jsonify({
        "ok": True,
        "month": month,
        "income_total": income_total,
        "expense_total": expense_total,
        "net": net,
        "expense_categories": expense_categories,
        "income_categories": income_categories,
        "expense_chart_categories": expense_chart_categories,
        "income_chart_categories": income_chart_categories,
        "expense_budget": expense_budget
    })

@app.route("/api/graph_subcategory_month")
@login_required
def api_graph_subcategory_month():
    month = request.args.get("month")
    category = request.args.get("category", "").strip()

    if not category:
        return jsonify({"ok": False, "error": "category is required"}), 400

    try:
        start_date, end_date = get_month_range(month)
    except Exception:
        return jsonify({"ok": False, "error": "month is invalid"}), 400

    if category not in SUBCATEGORY_DATA:
        return jsonify({"ok": False, "error": "category is invalid"}), 400

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT COALESCE(subcategory, 'その他') AS subcategory, SUM(amount) AS total
        FROM transactions
        WHERE user_id = ?
          AND type = 'expense'
          AND category = ?
          AND tx_date >= ?
          AND tx_date < ?
        GROUP BY COALESCE(subcategory, 'その他')
        ORDER BY total DESC, subcategory
    """, (session["user_id"], category, start_date, end_date))
    rows = cur.fetchall()

    cur.execute("""
        SELECT amount
        FROM budgets
        WHERE user_id = ? AND month = ? AND category = ?
    """, (session["user_id"], month, category))
    budget_row = cur.fetchone()

    conn.close()

    subcategories = build_subcategory_totals(category, rows)
    chart_subcategories = [item for item in subcategories if item["total"] > 0]
    total = sum(item["total"] for item in subcategories)

    budget_amount = int(budget_row["amount"] or 0) if budget_row else 0
    budget_info = build_budget_info(total, budget_amount)

    return jsonify({
        "ok": True,
        "month": month,
        "category": category,
        "total": total,
        "subcategories": subcategories,
        "chart_subcategories": chart_subcategories,
        **budget_info
    })
@app.route("/api/budget", methods=["GET", "POST"])
@login_required
def api_budget():
    if request.method == "GET":
        month = request.args.get("month", "").strip()
        category = request.args.get("category", "").strip()
    else:
        data = request.get_json(silent=True) or {}
        month = str(data.get("month", "")).strip()
        category = str(data.get("category", "")).strip()

    if not month:
        return jsonify({"ok": False, "error": "month is required"}), 400

    if category and category not in [item["name"] for item in CATEGORY_DATA["expense"]]:
        return jsonify({"ok": False, "error": "category is invalid"}), 400

    try:
        start_date, end_date = get_month_range(month)
    except Exception:
        return jsonify({"ok": False, "error": "month is invalid"}), 400

    conn = get_conn()
    cur = conn.cursor()

    if request.method == "GET":
        cur.execute("""
            SELECT amount
            FROM budgets
            WHERE user_id = ? AND month = ? AND category = ?
        """, (session["user_id"], month, category))
        row = cur.fetchone()

        budget_amount = int(row["amount"] or 0) if row else 0
        spent = get_expense_total_for_budget(conn, session["user_id"], start_date, end_date, category)
        conn.close()

        return jsonify({
            "ok": True,
            "month": month,
            "category": category,
            **build_budget_info(spent, budget_amount)
        })

    data = request.get_json(silent=True) or {}
    amount = data.get("amount", 0)

    try:
        amount = int(amount)
        if amount < 0:
            raise ValueError
    except Exception:
        conn.close()
        return jsonify({"ok": False, "error": "amount must be a non-negative integer"}), 400

    cur.execute("""
        INSERT INTO budgets (user_id, month, category, amount)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, month, category)
        DO UPDATE SET amount = excluded.amount
    """, (session["user_id"], month, category, amount))

    conn.commit()

    spent = get_expense_total_for_budget(conn, session["user_id"], start_date, end_date, category)
    conn.close()

    return jsonify({
        "ok": True,
        "month": month,
        "category": category,
        **build_budget_info(spent, amount)
    })
@app.route("/api/savings_history")
@login_required
def api_savings_history():
    months = request.args.get("months", "12")

    try:
        months = int(months)
    except Exception:
        months = 12

    months = max(1, min(months, 24))

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT substr(tx_date, 1, 7) AS ym, type, SUM(amount) AS total
        FROM transactions
        WHERE user_id = ?
        GROUP BY ym, type
        ORDER BY ym ASC
    """, (session["user_id"],))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return jsonify({
            "ok": True,
            "history": [],
            "chart": []
        })

    month_map = {}
    for row in rows:
        ym = row["ym"]
        if ym not in month_map:
            month_map[ym] = {"income": 0, "expense": 0}
        if row["type"] == "income":
            month_map[ym]["income"] = int(row["total"] or 0)
        elif row["type"] == "expense":
            month_map[ym]["expense"] = int(row["total"] or 0)

    all_months = sorted(month_map.keys())

    cumulative_by_month = {}
    running_total = 0

    for ym in all_months:
        income_total = month_map[ym]["income"]
        expense_total = month_map[ym]["expense"]
        monthly_net = income_total - expense_total
        running_total += monthly_net

        cumulative_by_month[ym] = {
            "month": ym,
            "income_total": income_total,
            "expense_total": expense_total,
            "monthly_net": monthly_net,
            "net": running_total
        }

    selected_months = all_months[-months:]

    history_chronological = [cumulative_by_month[ym] for ym in selected_months]

    for i, item in enumerate(history_chronological):
        if i == 0:
            prev_month_index = all_months.index(item["month"]) - 1
            if prev_month_index >= 0:
                prev_month = all_months[prev_month_index]
                item["diff_from_prev"] = item["net"] - cumulative_by_month[prev_month]["net"]
            else:
                item["diff_from_prev"] = None
        else:
            item["diff_from_prev"] = item["net"] - history_chronological[i - 1]["net"]

    history = list(reversed(history_chronological))

    chart = []
    for ym in selected_months:
        chart.append({
            "month": ym,
            "net": cumulative_by_month[ym]["net"]
        })

    return jsonify({
        "ok": True,
        "history": history,
        "chart": chart
    })


@app.route("/api/add", methods=["POST"])
@login_required
def api_add():
    data = request.get_json(force=True)

    tx_date = (data.get("date") or "")[:10]
    amount = data.get("amount")
    category = data.get("category") or "その他"
    subcategory = (data.get("subcategory") or "").strip()
    memo = data.get("memo") or ""
    tx_type = data.get("type") or "expense"

    if tx_type not in ["expense", "income"]:
        return jsonify({"ok": False, "error": "type is invalid"}), 400

    try:
        datetime.strptime(tx_date, "%Y-%m-%d")
    except Exception:
        return jsonify({"ok": False, "error": "date is invalid"}), 400

    try:
        amount = int(amount)
        if amount <= 0:
            raise ValueError()
    except Exception:
        return jsonify({"ok": False, "error": "amount must be positive integer"}), 400

    if tx_type == "expense":
        valid_subcategories = SUBCATEGORY_DATA.get(category, [])
        if valid_subcategories:
            if not subcategory:
                subcategory = valid_subcategories[0]
            elif subcategory not in valid_subcategories:
                return jsonify({"ok": False, "error": "subcategory is invalid"}), 400
        else:
            subcategory = ""
    else:
        subcategory = ""

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO transactions (user_id, tx_date, amount, category, subcategory, memo, type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session["user_id"], tx_date, amount, category, subcategory, memo, tx_type))
    conn.commit()
    conn.close()

    return jsonify({"ok": True})


@app.route("/api/delete", methods=["POST"])
@login_required
def api_delete():
    data = request.get_json(force=True)
    tx_id = data.get("id")

    try:
        tx_id = int(tx_id)
    except Exception:
        return jsonify({"ok": False, "error": "id invalid"}), 400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM transactions
        WHERE id = ? AND user_id = ?
    """, (tx_id, session["user_id"]))
    conn.commit()
    conn.close()

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)
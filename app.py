from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import os
import secrets
import hmac
from datetime import datetime, date, timedelta
from functools import wraps

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "kakeibo.db")
SECRET_FILE_PATH = os.path.join(BASE_DIR, ".secret_key")


def load_secret_key():
    env_key = os.environ.get("SECRET_KEY", "").strip()
    if env_key:
        return env_key

    if os.path.exists(SECRET_FILE_PATH):
        with open(SECRET_FILE_PATH, "r", encoding="utf-8") as f:
            saved = f.read().strip()
            if saved:
                return saved

    generated = secrets.token_hex(32)
    with open(SECRET_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(generated)
    return generated


def normalize_database_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return f"sqlite:///{DB_PATH}"
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = normalize_database_url(os.environ.get("DATABASE_URL", ""))
IS_SQLITE = DATABASE_URL.startswith("sqlite:")
IS_POSTGRES = DATABASE_URL.startswith("postgresql+psycopg:")

if IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        future=True,
        connect_args={
            "check_same_thread": False,
            "timeout": 10
        }
    )
else:
    engine = create_engine(
        DATABASE_URL,
        future=True,
        pool_pre_ping=True
    )

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = load_secret_key()

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "1") == "1"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

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

EXPENSE_CATEGORY_NAMES = {item["name"] for item in CATEGORY_DATA["expense"]}
INCOME_CATEGORY_NAMES = {item["name"] for item in CATEGORY_DATA["income"]}

LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_ATTEMPTS = 8


def get_conn():
    return engine.connect()


def init_db():
    with engine.begin() as conn:
        if IS_SQLITE:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """))

            conn.execute(text("""
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
            """))

            conn.execute(text("""
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
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    attempted_at TEXT NOT NULL
                )
            """))

            rows = conn.execute(text("PRAGMA table_info(transactions)")).mappings().all()
            existing_columns = {row["name"] for row in rows}
            if "subcategory" not in existing_columns:
                conn.execute(text("ALTER TABLE transactions ADD COLUMN subcategory TEXT"))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id),
                    tx_date TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT,
                    memo TEXT,
                    type TEXT NOT NULL DEFAULT 'expense',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS budgets (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id),
                    month TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    amount INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, month, category)
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    attempted_at TEXT NOT NULL
                )
            """))


init_db()


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped


def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()[:100]
    return (request.remote_addr or "unknown")[:100]


def cleanup_old_login_attempts(conn):
    cutoff = (datetime.utcnow() - timedelta(seconds=LOGIN_WINDOW_SECONDS)).isoformat(timespec="seconds")
    conn.execute(
        text("DELETE FROM login_attempts WHERE attempted_at < :cutoff"),
        {"cutoff": cutoff}
    )


def count_recent_login_attempts(conn, username, ip_address):
    cleanup_old_login_attempts(conn)
    cutoff = (datetime.utcnow() - timedelta(seconds=LOGIN_WINDOW_SECONDS)).isoformat(timespec="seconds")
    row = conn.execute(text("""
        SELECT COUNT(*) AS cnt
        FROM login_attempts
        WHERE username = :username AND ip_address = :ip_address AND attempted_at >= :cutoff
    """), {
        "username": username,
        "ip_address": ip_address,
        "cutoff": cutoff
    }).mappings().fetchone()
    return int(row["cnt"] or 0)


def record_failed_login(conn, username, ip_address):
    conn.execute(text("""
        INSERT INTO login_attempts (username, ip_address, attempted_at)
        VALUES (:username, :ip_address, :attempted_at)
    """), {
        "username": username,
        "ip_address": ip_address,
        "attempted_at": datetime.utcnow().isoformat(timespec="seconds")
    })


def clear_login_attempts(conn, username, ip_address):
    conn.execute(text("""
        DELETE FROM login_attempts
        WHERE username = :username AND ip_address = :ip_address
    """), {
        "username": username,
        "ip_address": ip_address
    })


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
    rows = conn.execute(text("""
        SELECT category, amount
        FROM budgets
        WHERE user_id = :user_id AND month = :month
    """), {
        "user_id": user_id,
        "month": month
    }).mappings().fetchall()

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
    if category:
        row = conn.execute(text("""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE user_id = :user_id
              AND type = 'expense'
              AND category = :category
              AND tx_date >= :start_date
              AND tx_date < :end_date
        """), {
            "user_id": user_id,
            "category": category,
            "start_date": start_date,
            "end_date": end_date
        }).mappings().fetchone()
    else:
        row = conn.execute(text("""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE user_id = :user_id
              AND type = 'expense'
              AND tx_date >= :start_date
              AND tx_date < :end_date
        """), {
            "user_id": user_id,
            "start_date": start_date,
            "end_date": end_date
        }).mappings().fetchone()

    return int(row["total"] or 0)


def validate_iso_date(value):
    datetime.strptime(value, "%Y-%m-%d")
    return value


def validate_month_str(value):
    datetime.strptime(value, "%Y-%m")
    return value


def get_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def validate_csrf_or_abort(api_mode=False):
    session_token = session.get("_csrf_token", "")
    request_token = request.headers.get("X-CSRF-Token", "").strip()

    if not request_token and request.form:
        request_token = request.form.get("csrf_token", "").strip()

    if not session_token or not request_token or not hmac.compare_digest(session_token, request_token):
        if api_mode:
            return jsonify({"ok": False, "error": "不正なリクエストです。"}), 400
        return render_template("login.html", error="不正なリクエストです。"), 400

    return None


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": get_csrf_token}


@app.after_request
def add_security_headers(response):
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "font-src 'self' https://cdn.jsdelivr.net data:; "
        "connect-src 'self'; "
        "frame-ancestors 'self'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    return response


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""

    if request.method == "POST":
        csrf_error = validate_csrf_or_abort(api_mode=False)
        if csrf_error:
            return csrf_error

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            error = "ユーザー名とパスワードを入力してください。"
            return render_template("register.html", error=error)

        if len(username) > 50:
            error = "ユーザー名は50文字以内で入力してください。"
            return render_template("register.html", error=error)

        if len(password) < 8:
            error = "パスワードは8文字以上で入力してください。"
            return render_template("register.html", error=error)

        password_hash = generate_password_hash(password)

        try:
            with engine.begin() as conn:
                existing = conn.execute(
                    text("SELECT id FROM users WHERE username = :username"),
                    {"username": username}
                ).mappings().fetchone()

                if existing:
                    error = "そのユーザー名はすでに使われています。"
                    return render_template("register.html", error=error)

                conn.execute(
                    text("INSERT INTO users (username, password_hash) VALUES (:username, :password_hash)"),
                    {"username": username, "password_hash": password_hash}
                )
        except IntegrityError:
            error = "そのユーザー名はすでに使われています。"
            return render_template("register.html", error=error)

        return redirect(url_for("login"))

    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        csrf_error = validate_csrf_or_abort(api_mode=False)
        if csrf_error:
            return csrf_error

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        ip_address = get_client_ip()

        with engine.begin() as conn:
            if count_recent_login_attempts(conn, username, ip_address) >= LOGIN_MAX_ATTEMPTS:
                error = "試行回数が多すぎます。しばらく待ってから再度お試しください。"
                return render_template("login.html", error=error)

            user = conn.execute(
                text("SELECT id, username, password_hash FROM users WHERE username = :username"),
                {"username": username}
            ).mappings().fetchone()

            if user is None or not check_password_hash(user["password_hash"], password):
                record_failed_login(conn, username, ip_address)
                error = "ユーザー名またはパスワードが違います。"
                return render_template("login.html", error=error)

            clear_login_attempts(conn, username, ip_address)

        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["_csrf_token"] = secrets.token_urlsafe(32)

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
    start = request.args.get("start", "").strip()
    end = request.args.get("end", "").strip()
    if not start or not end:
        return jsonify([])

    with get_conn() as conn:
        rows = conn.execute(text("""
            SELECT tx_date, type, SUM(amount) AS total
            FROM transactions
            WHERE user_id = :user_id AND tx_date >= :start_date AND tx_date < :end_date
            GROUP BY tx_date, type
            ORDER BY tx_date, type
        """), {
            "user_id": session["user_id"],
            "start_date": start[:10],
            "end_date": end[:10]
        }).mappings().fetchall()

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
    tx_date = request.args.get("date", "").strip()
    if not tx_date:
        return jsonify([])

    try:
        tx_date = validate_iso_date(tx_date[:10])
    except Exception:
        return jsonify([])

    with get_conn() as conn:
        rows = conn.execute(text("""
            SELECT id, tx_date, amount, category, subcategory, memo, type
            FROM transactions
            WHERE user_id = :user_id AND tx_date = :tx_date
            ORDER BY id DESC
        """), {
            "user_id": session["user_id"],
            "tx_date": tx_date
        }).mappings().fetchall()

    return jsonify([dict(r) for r in rows])


@app.route("/api/graph_month")
@login_required
def api_graph_month():
    month = (request.args.get("month") or "").strip()

    try:
        month = validate_month_str(month)
        start_date, end_date = get_month_range(month)
    except Exception:
        return jsonify({"ok": False, "error": "month is invalid"}), 400

    with get_conn() as conn:
        totals_rows = conn.execute(text("""
            SELECT type, COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE user_id = :user_id AND tx_date >= :start_date AND tx_date < :end_date
            GROUP BY type
        """), {
            "user_id": session["user_id"],
            "start_date": start_date,
            "end_date": end_date
        }).mappings().fetchall()

        income_total = 0
        expense_total = 0

        for row in totals_rows:
            if row["type"] == "income":
                income_total = int(row["total"] or 0)
            elif row["type"] == "expense":
                expense_total = int(row["total"] or 0)

        expense_rows = conn.execute(text("""
            SELECT category, SUM(amount) AS total
            FROM transactions
            WHERE user_id = :user_id AND type = 'expense' AND tx_date >= :start_date AND tx_date < :end_date
            GROUP BY category
            ORDER BY total DESC, category
        """), {
            "user_id": session["user_id"],
            "start_date": start_date,
            "end_date": end_date
        }).mappings().fetchall()

        income_rows = conn.execute(text("""
            SELECT category, SUM(amount) AS total
            FROM transactions
            WHERE user_id = :user_id AND type = 'income' AND tx_date >= :start_date AND tx_date < :end_date
            GROUP BY category
            ORDER BY total DESC, category
        """), {
            "user_id": session["user_id"],
            "start_date": start_date,
            "end_date": end_date
        }).mappings().fetchall()

        budget_map = get_budget_amounts_for_month(conn, session["user_id"], month)

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
    month = (request.args.get("month") or "").strip()
    category = (request.args.get("category") or "").strip()

    if not category:
        return jsonify({"ok": False, "error": "category is required"}), 400

    try:
        month = validate_month_str(month)
        start_date, end_date = get_month_range(month)
    except Exception:
        return jsonify({"ok": False, "error": "month is invalid"}), 400

    if category not in SUBCATEGORY_DATA:
        return jsonify({"ok": False, "error": "category is invalid"}), 400

    with get_conn() as conn:
        rows = conn.execute(text("""
            SELECT COALESCE(subcategory, 'その他') AS subcategory, SUM(amount) AS total
            FROM transactions
            WHERE user_id = :user_id
              AND type = 'expense'
              AND category = :category
              AND tx_date >= :start_date
              AND tx_date < :end_date
            GROUP BY COALESCE(subcategory, 'その他')
            ORDER BY total DESC, subcategory
        """), {
            "user_id": session["user_id"],
            "category": category,
            "start_date": start_date,
            "end_date": end_date
        }).mappings().fetchall()

        budget_row = conn.execute(text("""
            SELECT amount
            FROM budgets
            WHERE user_id = :user_id AND month = :month AND category = :category
        """), {
            "user_id": session["user_id"],
            "month": month,
            "category": category
        }).mappings().fetchone()

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
        month = (request.args.get("month") or "").strip()
        category = (request.args.get("category") or "").strip()
    else:
        csrf_error = validate_csrf_or_abort(api_mode=True)
        if csrf_error:
            return csrf_error

        data = request.get_json(silent=True) or {}
        month = str(data.get("month", "")).strip()
        category = str(data.get("category", "")).strip()

    if not month:
        return jsonify({"ok": False, "error": "month is required"}), 400

    try:
        month = validate_month_str(month)
        start_date, end_date = get_month_range(month)
    except Exception:
        return jsonify({"ok": False, "error": "month is invalid"}), 400

    if category and category not in EXPENSE_CATEGORY_NAMES:
        return jsonify({"ok": False, "error": "category is invalid"}), 400

    if request.method == "GET":
        with get_conn() as conn:
            row = conn.execute(text("""
                SELECT amount
                FROM budgets
                WHERE user_id = :user_id AND month = :month AND category = :category
            """), {
                "user_id": session["user_id"],
                "month": month,
                "category": category
            }).mappings().fetchone()

            budget_amount = int(row["amount"] or 0) if row else 0
            spent = get_expense_total_for_budget(conn, session["user_id"], start_date, end_date, category)

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
        return jsonify({"ok": False, "error": "amount must be a non-negative integer"}), 400

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO budgets (user_id, month, category, amount)
            VALUES (:user_id, :month, :category, :amount)
            ON CONFLICT(user_id, month, category)
            DO UPDATE SET amount = EXCLUDED.amount
        """), {
            "user_id": session["user_id"],
            "month": month,
            "category": category,
            "amount": amount
        })

        spent = get_expense_total_for_budget(conn, session["user_id"], start_date, end_date, category)

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

    if IS_SQLITE:
        history_sql = text("""
            SELECT substr(tx_date, 1, 7) AS ym, type, SUM(amount) AS total
            FROM transactions
            WHERE user_id = :user_id
            GROUP BY ym, type
            ORDER BY ym ASC
        """)
    else:
        history_sql = text("""
            SELECT substring(tx_date from 1 for 7) AS ym, type, SUM(amount) AS total
            FROM transactions
            WHERE user_id = :user_id
            GROUP BY ym, type
            ORDER BY ym ASC
        """)

    with get_conn() as conn:
        rows = conn.execute(history_sql, {
            "user_id": session["user_id"]
        }).mappings().fetchall()

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
    chart = [{"month": ym, "net": cumulative_by_month[ym]["net"]} for ym in selected_months]

    return jsonify({
        "ok": True,
        "history": history,
        "chart": chart
    })


@app.route("/api/add", methods=["POST"])
@login_required
def api_add():
    csrf_error = validate_csrf_or_abort(api_mode=True)
    if csrf_error:
        return csrf_error

    data = request.get_json(silent=True) or {}

    tx_date = str(data.get("date", "")).strip()[:10]
    amount = data.get("amount")
    category = str(data.get("category", "")).strip()
    subcategory = str(data.get("subcategory", "")).strip()
    memo = str(data.get("memo", "")).strip()
    tx_type = str(data.get("type", "expense")).strip()

    if tx_type not in ("expense", "income"):
        return jsonify({"ok": False, "error": "type is invalid"}), 400

    try:
        tx_date = validate_iso_date(tx_date)
    except Exception:
        return jsonify({"ok": False, "error": "date is invalid"}), 400

    try:
        amount = int(amount)
        if amount <= 0:
            raise ValueError
    except Exception:
        return jsonify({"ok": False, "error": "amount is invalid"}), 400

    if len(memo) > 200:
        return jsonify({"ok": False, "error": "memo is too long"}), 400

    if tx_type == "expense":
        if category not in EXPENSE_CATEGORY_NAMES:
            return jsonify({"ok": False, "error": "category is invalid"}), 400
        valid_subcategories = SUBCATEGORY_DATA.get(category, [])
        if subcategory and subcategory not in valid_subcategories:
            return jsonify({"ok": False, "error": "subcategory is invalid"}), 400
        if not subcategory and valid_subcategories:
            subcategory = valid_subcategories[0]
    else:
        if category not in INCOME_CATEGORY_NAMES:
            return jsonify({"ok": False, "error": "category is invalid"}), 400
        subcategory = ""

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO transactions (user_id, tx_date, amount, category, subcategory, memo, type)
            VALUES (:user_id, :tx_date, :amount, :category, :subcategory, :memo, :tx_type)
        """), {
            "user_id": session["user_id"],
            "tx_date": tx_date,
            "amount": amount,
            "category": category,
            "subcategory": subcategory if tx_type == "expense" else None,
            "memo": memo,
            "tx_type": tx_type
        })

    return jsonify({"ok": True})


@app.route("/api/delete", methods=["POST"])
@login_required
def api_delete():
    csrf_error = validate_csrf_or_abort(api_mode=True)
    if csrf_error:
        return csrf_error

    data = request.get_json(silent=True) or {}
    tx_id = data.get("id")

    try:
        tx_id = int(tx_id)
    except Exception:
        return jsonify({"ok": False, "error": "id is invalid"}), 400

    with engine.begin() as conn:
        result = conn.execute(text("""
            DELETE FROM transactions
            WHERE id = :tx_id AND user_id = :user_id
        """), {
            "tx_id": tx_id,
            "user_id": session["user_id"]
        })
        deleted = result.rowcount

    if deleted == 0:
        return jsonify({"ok": False, "error": "transaction not found"}), 404

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=False)
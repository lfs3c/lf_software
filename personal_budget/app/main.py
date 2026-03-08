from collections import defaultdict
import calendar
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import secrets

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import get_db
from app.models import (
    AccountCard,
    Bill,
    Category,
    CategoryColorPreference,
    InvestmentOverride,
    InvestmentPlatformOverride,
    Month,
    MonthSnapshot,
    PlanningGoal,
    Transaction,
    User,
)
from app.security import hash_password, verify_password

app = FastAPI(title=settings.app_name)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, https_only=False)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
PROFILE_UPLOAD_DIR = Path("app/static/uploads/profiles")
PROFILE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


EXPENSE = "expense"
INCOME = "income"
INVESTMENT = "investment"
GOAL_TRANSFER = "goal_transfer"


def month_label(dt: date) -> str:
    return dt.strftime("%Y-%m")


def parse_month_label(label: str) -> tuple[int, int]:
    year, month = label.split("-")
    return int(year), int(month)


def next_month(label: str) -> str:
    year, month = parse_month_label(label)
    if month == 12:
        return f"{year + 1:04d}-01"
    return f"{year:04d}-{month + 1:02d}"


def format_month_label_en(label: str) -> str:
    year, month = parse_month_label(label)
    months = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    if 1 <= month <= 12:
        return f"{months[month - 1]} {year}"
    return label


def parse_optional_int(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None
    value = raw_value.strip()
    if value == "":
        return None
    if not value.isdigit():
        raise HTTPException(status_code=400, detail="Invalid integer value")
    return int(value)


def parse_optional_date(raw_value: str | None) -> date | None:
    if raw_value is None:
        return None
    value = raw_value.strip()
    if value == "":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date") from exc


def normalize_email(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    email = raw_value.strip().lower()
    return email or None


def derive_default_initials(username: str) -> str:
    cleaned = "".join(ch for ch in username.upper() if ch.isalnum())
    return (cleaned[:3] or "USR")


def normalize_initials(raw_value: str | None, fallback_username: str) -> str:
    value = (raw_value or "").strip().upper()
    cleaned = "".join(ch for ch in value if ch.isalnum())
    if 1 <= len(cleaned) <= 8:
        return cleaned
    return derive_default_initials(fallback_username)


def normalize_color_hex(raw_value: str) -> str:
    value = (raw_value or "").strip()
    if len(value) == 7 and value.startswith("#"):
        hex_part = value[1:]
        if all(ch in "0123456789abcdefABCDEF" for ch in hex_part):
            return f"#{hex_part.lower()}"
    raise HTTPException(status_code=400, detail="Invalid color. Use #RRGGBB format.")


class CategoryColorPayload(BaseModel):
    colors: dict[str, str]


def resolve_return_to(raw_value: str | None, fallback: str = "/app") -> str:
    if raw_value in {"/app", "/profile"}:
        return raw_value
    return fallback


def save_profile_image_file(image: UploadFile | None, *, user_id: int) -> str | None:
    if image is None or not image.filename:
        return None
    content_type = image.content_type or ""
    if content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=400, detail="Invalid image format (use PNG, JPEG, or WEBP)")
    ext = Path(image.filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        ext = ".png"
    filename = f"user_{user_id}_{secrets.token_hex(8)}{ext}"
    target_path = PROFILE_UPLOAD_DIR / filename
    data = image.file.read()
    if len(data) > 3 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 3MB)")
    target_path.write_bytes(data)
    return f"/static/uploads/profiles/{filename}"


def next_occurrence_for_day(day: int, base_date: date) -> date:
    current_last_day = calendar.monthrange(base_date.year, base_date.month)[1]
    current_day = min(day, current_last_day)
    candidate = date(base_date.year, base_date.month, current_day)
    if candidate >= base_date:
        return candidate

    if base_date.month == 12:
        next_year = base_date.year + 1
        next_month_number = 1
    else:
        next_year = base_date.year
        next_month_number = base_date.month + 1
    next_last_day = calendar.monthrange(next_year, next_month_number)[1]
    next_day = min(day, next_last_day)
    return date(next_year, next_month_number, next_day)


def require_user(request: Request, db: Session) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user = db.get(User, user_id)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if user.is_blocked:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is blocked")
    return user


def require_admin(request: Request, db: Session) -> User:
    user = require_user(request, db)
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator permission required")
    return user


def months_until_target(today: date, target: date) -> int:
    if target < today:
        return 0
    return ((target.year - today.year) * 12) + (target.month - today.month) + 1


def parse_money_amount(raw_value: str, *, label: str, allow_zero: bool = False) -> Decimal:
    value = (raw_value or "").strip().replace(" ", "")
    if not value:
        raise HTTPException(status_code=400, detail=f"{label} required")

    normalized = value
    has_dot = "." in normalized
    has_comma = "," in normalized

    if has_dot and has_comma:
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
    elif has_comma:
        if normalized.count(",") == 1 and len(normalized.rsplit(",", 1)[1]) <= 2:
            normalized = normalized.replace(",", ".")
        else:
            normalized = normalized.replace(",", "")

    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise HTTPException(status_code=400, detail=f"{label} invalid") from exc

    if allow_zero:
        if amount < 0:
            raise HTTPException(status_code=400, detail=f"{label} must be zero or positive")
    elif amount <= 0:
        raise HTTPException(status_code=400, detail=f"{label} must be greater than zero")
    return amount


def parse_planning_amount(raw_value: str) -> Decimal:
    return parse_money_amount(raw_value, label="Target amount", allow_zero=False)


def parse_planning_target_date(raw_value: str) -> date:
    value = (raw_value or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="Target date is required")

    try:
        return date.fromisoformat(value)
    except ValueError:
        pass

    for pattern in ("%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue

    raise HTTPException(status_code=400, detail="Invalid target date")


def derive_goal_alias(objective: str, max_len: int = 48) -> str:
    normalized = " ".join((objective or "").strip().split())
    if not normalized:
        return "Goal"
    return normalized[:max_len]


def build_goal_code(seed_number: int) -> str:
    return f"OBJ-{seed_number:04d}"


def format_decimal_us(value: Decimal | float | int | None) -> str:
    if value is None:
        return ""
    decimal_value = Decimal(str(value)).quantize(Decimal("0.01"))
    return f"{decimal_value:,.2f}"


def format_usd(value: Decimal | float | int | None) -> str:
    return f"USD {format_decimal_us(value)}"


templates.env.filters["decimal_br"] = format_decimal_us
templates.env.filters["usd"] = format_usd


def get_or_create_open_month(db: Session, user_id: int) -> Month:
    open_month = db.execute(
        select(Month).where(and_(Month.user_id == user_id, Month.is_closed.is_(False))).order_by(Month.id.desc())
    ).scalars().first()
    if open_month:
        return open_month

    label = month_label(date.today())
    month = Month(user_id=user_id, label=label, is_closed=False)
    db.add(month)
    db.commit()
    db.refresh(month)
    return month


def compute_month_stats(db: Session, user_id: int, month_id: int) -> dict:
    rows = db.execute(
        select(Transaction.kind, Transaction.category, func.sum(Transaction.amount))
        .where(and_(Transaction.user_id == user_id, Transaction.month_id == month_id))
        .group_by(Transaction.kind, Transaction.category)
    ).all()

    total_expenses = Decimal("0")
    total_income = Decimal("0")
    total_investments = Decimal("0")
    category_outflows: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for kind, category, amount in rows:
        amount = amount or Decimal("0")
        if kind == EXPENSE:
            total_expenses += amount
            category_outflows[category] += amount
        elif kind == INCOME:
            total_income += amount
        elif kind == INVESTMENT:
            total_investments += amount
            category_outflows[category] += amount

    color_pref_rows = db.execute(
        select(CategoryColorPreference.category_name, CategoryColorPreference.color_hex).where(
            CategoryColorPreference.user_id == user_id
        )
    ).all()
    colors_by_category = {category_name: color_hex for category_name, color_hex in color_pref_rows}

    categories = []
    total_outflows = total_expenses + total_investments
    for category, amount in sorted(category_outflows.items()):
        pct = float((amount / total_outflows * 100) if total_outflows > 0 else Decimal("0"))
        categories.append(
            {
                "category": category,
                "amount": float(amount),
                "percent": round(pct, 2),
                "color": colors_by_category.get(category),
            }
        )

    return {
        "totals": {
            "expenses": float(total_expenses),
            "income": float(total_income),
            "investments": float(total_investments),
        },
        "categories": categories,
    }


def compute_annual_stats(db: Session, user_id: int, year: int) -> dict:
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    income_by_month = [0.0] * 12
    expenses_by_month = [0.0] * 12

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    rows = db.execute(
        select(
            func.extract("month", Transaction.tx_date).label("month_num"),
            Transaction.kind,
            func.sum(Transaction.amount),
        )
        .where(
            and_(
                Transaction.user_id == user_id,
                Transaction.tx_date >= year_start,
                Transaction.tx_date <= year_end,
            )
        )
        .group_by("month_num", Transaction.kind)
    ).all()

    for month_num, kind, amount in rows:
        month_index = int(month_num) - 1
        if month_index < 0 or month_index > 11:
            continue
        parsed_amount = float(amount or 0)
        if kind == INCOME:
            income_by_month[month_index] += parsed_amount
        elif kind in {EXPENSE, INVESTMENT}:
            expenses_by_month[month_index] += parsed_amount

    balance_by_month = [round(income_by_month[i] - expenses_by_month[i], 2) for i in range(12)]
    return {
        "year": year,
        "labels": month_labels,
        "income": [round(v, 2) for v in income_by_month],
        "expenses": [round(v, 2) for v in expenses_by_month],
        "balance": balance_by_month,
    }


def compute_investment_chart_data(db: Session, user_id: int, current_month_label: str) -> dict:
    year, current_month_num = parse_month_label(current_month_label)
    month_labels_short = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    acorns_month_values = [0.0] * 12
    webull_month_values = [0.0] * 12

    def platform_from_category(category: str | None) -> str | None:
        normalized = (category or "").strip().lower()
        if normalized == "acorns":
            return "acorns"
        if normalized == "webull":
            return "webull"
        return None

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    tx_rows = db.execute(
        select(
            func.extract("month", Transaction.tx_date).label("month_num"),
            Transaction.category,
            func.sum(Transaction.amount),
        )
        .where(
            and_(
                Transaction.user_id == user_id,
                Transaction.kind == INVESTMENT,
                Transaction.tx_date >= year_start,
                Transaction.tx_date <= year_end,
            )
        )
        .group_by("month_num", Transaction.category)
    ).all()

    for month_num, category, amount in tx_rows:
        index = int(month_num) - 1
        if not (0 <= index <= 11):
            continue
        platform = platform_from_category(category)
        if platform == "acorns":
            acorns_month_values[index] = round(float(amount or 0), 2)
        elif platform == "webull":
            webull_month_values[index] = round(float(amount or 0), 2)

    override_rows = db.execute(
        select(
            InvestmentPlatformOverride.month_label,
            InvestmentPlatformOverride.platform,
            InvestmentPlatformOverride.manual_value,
        )
        .where(
            and_(
                InvestmentPlatformOverride.user_id == user_id,
                InvestmentPlatformOverride.month_label >= f"{year:04d}-01",
                InvestmentPlatformOverride.month_label <= f"{year:04d}-12",
            )
        )
    ).all()
    manual_by_label: dict[str, dict[str, float]] = {}
    for month_label, platform, manual_value in override_rows:
        normalized_platform = platform_from_category(platform)
        if normalized_platform is None:
            continue
        entry = manual_by_label.setdefault(month_label, {})
        entry[normalized_platform] = round(float(manual_value), 2)

    month_values = [round(acorns_month_values[i] + webull_month_values[i], 2) for i in range(12)]
    for idx in range(12):
        label = f"{year:04d}-{idx + 1:02d}"
        manual_entry = manual_by_label.get(label, {})
        if "acorns" in manual_entry:
            acorns_month_values[idx] = manual_entry["acorns"]
        if "webull" in manual_entry:
            webull_month_values[idx] = manual_entry["webull"]
        month_values[idx] = round(acorns_month_values[idx] + webull_month_values[idx], 2)

    current_index = current_month_num - 1
    current_month_value = month_values[current_index] if 0 <= current_index <= 11 else 0.0

    # Daily view for current month (left-to-right progression over day numbers).
    month_days = calendar.monthrange(year, current_month_num)[1]
    acorns_day_values = [0.0] * month_days
    webull_day_values = [0.0] * month_days
    month_start = date(year, current_month_num, 1)
    month_end = date(year, current_month_num, month_days)
    day_rows = db.execute(
        select(
            func.extract("day", Transaction.tx_date).label("day_num"),
            Transaction.category,
            func.sum(Transaction.amount),
        )
        .where(
            and_(
                Transaction.user_id == user_id,
                Transaction.kind == INVESTMENT,
                Transaction.tx_date >= month_start,
                Transaction.tx_date <= month_end,
            )
        )
        .group_by("day_num", Transaction.category)
    ).all()
    for day_num, category, amount in day_rows:
        idx = int(day_num) - 1
        if not (0 <= idx < month_days):
            continue
        platform = platform_from_category(category)
        if platform == "acorns":
            acorns_day_values[idx] = round(float(amount or 0), 2)
        elif platform == "webull":
            webull_day_values[idx] = round(float(amount or 0), 2)

    # If there is a manual override for current month, align today's point by delta.
    manual_current_month = manual_by_label.get(current_month_label, {})
    today = date.today()
    if today.year == year and today.month == current_month_num:
        target_day = today.day
    else:
        target_day = month_days

    if "acorns" in manual_current_month:
        acorns_delta = round(manual_current_month["acorns"] - round(sum(acorns_day_values), 2), 2)
        acorns_day_values[target_day - 1] = round(acorns_day_values[target_day - 1] + acorns_delta, 2)
    if "webull" in manual_current_month:
        webull_delta = round(manual_current_month["webull"] - round(sum(webull_day_values), 2), 2)
        webull_day_values[target_day - 1] = round(webull_day_values[target_day - 1] + webull_delta, 2)

    # Build a continuous running-total curve for daily month view.
    acorns_cumulative_day_values: list[float] = []
    webull_cumulative_day_values: list[float] = []
    acorns_running_total = 0.0
    webull_running_total = 0.0
    for index in range(month_days):
        acorns_running_total = round(acorns_running_total + acorns_day_values[index], 2)
        webull_running_total = round(webull_running_total + webull_day_values[index], 2)
        acorns_cumulative_day_values.append(acorns_running_total)
        webull_cumulative_day_values.append(webull_running_total)

    today = date.today()
    if today.year == year and today.month == current_month_num:
        visible_days = today.day
    else:
        visible_days = month_days
    day_labels = [str(day).zfill(2) for day in range(1, visible_days + 1)]
    acorns_day_values = acorns_cumulative_day_values[:visible_days]
    webull_day_values = webull_cumulative_day_values[:visible_days]
    day_values = [round(acorns_day_values[i] + webull_day_values[i], 2) for i in range(visible_days)]

    values_by_month = {f"{year:04d}-{i + 1:02d}": month_values[i] for i in range(12)}
    return {
        "year": year,
        "labels": month_labels_short,
        "values": month_values,
        "acorns_month_values": acorns_month_values,
        "webull_month_values": webull_month_values,
        "values_by_month": values_by_month,
        "current_month": current_month_label,
        "current_month_value": current_month_value,
        "manual_by_month": manual_by_label,
        "current_manual_acorns": acorns_month_values[current_index] if 0 <= current_index <= 11 else 0.0,
        "current_manual_webull": webull_month_values[current_index] if 0 <= current_index <= 11 else 0.0,
        "month_day_labels": day_labels,
        "month_day_values": day_values,
        "acorns_day_values": acorns_day_values,
        "webull_day_values": webull_day_values,
    }


@app.get("/")
def index(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/app", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login")
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/app", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "auth_mode": None})


@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    username = username.strip().lower()
    normalized_email = normalize_email(email)
    if len(username) < 3 or len(password) < 8:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Username must be at least 3 chars and password at least 8 chars.", "auth_mode": "register"},
            status_code=400,
        )
    if not normalized_email or "@" not in normalized_email:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Email invalid.", "auth_mode": "register"},
            status_code=400,
        )

    existing = db.execute(select(User).where(User.username == username)).scalars().first()
    if existing:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "User already exists.", "auth_mode": "register"},
            status_code=400,
        )
    duplicate_email = db.execute(select(User).where(User.email == normalized_email)).scalars().first()
    if duplicate_email:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Email already registered.", "auth_mode": "register"},
            status_code=400,
        )

    admin_count = db.execute(select(func.count(User.id)).where(User.is_admin.is_(True))).scalar_one()
    user = User(
        username=username,
        email=normalized_email,
        initials=derive_default_initials(username),
        password_hash=hash_password(password),
        is_admin=(admin_count == 0),
        is_blocked=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    get_or_create_open_month(db, user.id)

    request.session["user_id"] = user.id
    return RedirectResponse(url="/app", status_code=303)


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    username = username.strip().lower()
    user = db.execute(select(User).where(User.username == username)).scalars().first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid credentials.", "auth_mode": "login"},
            status_code=401,
        )
    if user.is_blocked:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "User is blocked. Contact the administrator.", "auth_mode": "login"},
            status_code=403,
        )

    request.session["user_id"] = user.id
    get_or_create_open_month(db, user.id)
    return RedirectResponse(url="/app", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/app")
def app_home(request: Request, db: Session = Depends(get_db)):
    try:
        user = require_user(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)

    current_month = get_or_create_open_month(db, user.id)

    accounts = db.execute(select(AccountCard).where(AccountCard.user_id == user.id).order_by(AccountCard.id.desc())).scalars().all()
    recent_transactions = db.execute(
        select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.tx_date.desc(), Transaction.id.desc())
        .limit(6)
    ).scalars().all()
    expense_categories = db.execute(
        select(Category.name)
        .where(and_(Category.user_id == user.id, Category.kind == EXPENSE))
        .order_by(Category.name.asc())
    ).scalars().all()
    income_categories = db.execute(
        select(Category.name)
        .where(and_(Category.user_id == user.id, Category.kind == INCOME))
        .order_by(Category.name.asc())
    ).scalars().all()
    investment_categories = db.execute(
        select(Category.name)
        .where(and_(Category.user_id == user.id, Category.kind == INVESTMENT))
        .order_by(Category.name.asc())
    ).scalars().all()
    bills = db.execute(select(Bill).where(Bill.user_id == user.id).order_by(Bill.due_date.asc())).scalars().all()
    cards = db.execute(
        select(AccountCard).where(
            and_(
                AccountCard.user_id == user.id,
                AccountCard.type == "card",
                AccountCard.payment_date.is_not(None),
            )
        )
    ).scalars().all()
    planning_goals = db.execute(
        select(PlanningGoal)
        .where(PlanningGoal.user_id == user.id)
        .order_by(PlanningGoal.updated_at.desc(), PlanningGoal.id.desc())
    ).scalars().all()
    planning_goals_progress = []
    for goal in planning_goals:
        total_saved = db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                and_(
                    Transaction.user_id == user.id,
                    Transaction.kind.in_([INVESTMENT, GOAL_TRANSFER]),
                    Transaction.category == goal.category_name,
                )
            )
        ).scalar_one()
        total_saved = total_saved or Decimal("0")
        percent = Decimal("0")
        if goal.target_amount > 0:
            percent = (Decimal(total_saved) / Decimal(goal.target_amount) * Decimal("100")).quantize(Decimal("0.01"))
        planning_goals_progress.append(
            {
                "goal": goal,
                "saved_amount": Decimal(total_saved).quantize(Decimal("0.01")),
                "percent": percent,
            }
        )
    planning_feedback = request.session.pop("planning_feedback", None)

    managed_users = []
    if user.is_admin:
        managed_users = db.execute(
            select(User).where(User.id != user.id).order_by(User.created_at.asc(), User.id.asc())
        ).scalars().all()

    upcoming_count = db.execute(
        select(func.count(Bill.id)).where(
            and_(
                Bill.user_id == user.id,
                Bill.paid.is_(False),
                Bill.due_date <= (date.today().fromordinal(date.today().toordinal() + 7)),
            )
        )
    ).scalar_one()

    card_totals_rows = db.execute(
        select(Transaction.account_id, func.sum(Transaction.amount))
        .where(
            and_(
                Transaction.user_id == user.id,
                Transaction.month_id == current_month.id,
                Transaction.kind == EXPENSE,
                Transaction.account_id.is_not(None),
            )
        )
        .group_by(Transaction.account_id)
    ).all()
    card_totals: dict[int, Decimal] = {
        account_id: total or Decimal("0") for account_id, total in card_totals_rows if account_id is not None
    }

    today = date.today()
    in_one_week = date.fromordinal(today.toordinal() + 7)
    card_payment_alerts = []
    for card in cards:
        if card.payment_date is None:
            continue
        payment_day = card.payment_date.day
        next_payment_date = next_occurrence_for_day(payment_day, today)
        if today <= next_payment_date <= in_one_week:
            days_remaining = (next_payment_date - today).days
            if days_remaining == 0:
                level = "danger"
            elif days_remaining <= 3:
                level = "warn"
            else:
                level = "info"
            current_value = card_totals.get(card.id, Decimal("0"))
            card_payment_alerts.append(
                {
                    "nickname": card.nickname,
                    "payment_date": next_payment_date.isoformat(),
                    "days_remaining": days_remaining,
                    "level": level,
                    "current_value": float(current_value),
                }
            )

    return templates.TemplateResponse(
        "app.html",
        {
            "request": request,
            "user": user,
            "current_month": current_month,
            "current_month_display": format_month_label_en(current_month.label),
            "accounts": accounts,
            "transactions": recent_transactions,
            "expense_categories": expense_categories,
            "income_categories": income_categories,
            "investment_categories": investment_categories,
            "bills": bills,
            "upcoming_count": upcoming_count,
            "card_payment_alerts": card_payment_alerts,
            "today": date.today(),
            "planning_goals_progress": planning_goals_progress,
            "planning_feedback": planning_feedback,
            "managed_users": managed_users,
        },
    )


@app.get("/transactions/history")
def transactions_history(request: Request, db: Session = Depends(get_db)):
    try:
        user = require_user(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)

    query_params = request.query_params
    selected_account_ids: list[int] = []
    for raw_account_id in query_params.getlist("account_id"):
        cleaned = (raw_account_id or "").strip()
        if cleaned.isdigit():
            selected_account_ids.append(int(cleaned))

    allowed_types = {EXPENSE, INCOME, INVESTMENT, GOAL_TRANSFER}
    selected_types = [
        value.strip().lower()
        for value in query_params.getlist("kind")
        if value and value.strip().lower() in allowed_types
    ]

    category_filter = (query_params.get("category") or "").strip()
    month_filter = (query_params.get("month") or "").strip()
    exact_date_raw = (query_params.get("tx_date") or "").strip()
    date_from_raw = (query_params.get("date_from") or "").strip()
    date_to_raw = (query_params.get("date_to") or "").strip()

    filters = [Transaction.user_id == user.id]

    if selected_account_ids:
        filters.append(Transaction.account_id.in_(selected_account_ids))
    if selected_types:
        filters.append(Transaction.kind.in_(selected_types))
    if category_filter:
        filters.append(Transaction.category.ilike(f"%{category_filter}%"))

    parsed_exact_date = None
    if exact_date_raw:
        try:
            parsed_exact_date = date.fromisoformat(exact_date_raw)
            filters.append(Transaction.tx_date == parsed_exact_date)
        except ValueError:
            parsed_exact_date = None

    if parsed_exact_date is None and month_filter:
        try:
            parsed_year, parsed_month = parse_month_label(month_filter)
            month_start = date(parsed_year, parsed_month, 1)
            month_end = date(parsed_year, parsed_month, calendar.monthrange(parsed_year, parsed_month)[1])
            filters.append(Transaction.tx_date >= month_start)
            filters.append(Transaction.tx_date <= month_end)
        except Exception:
            pass

    if date_from_raw:
        try:
            filters.append(Transaction.tx_date >= date.fromisoformat(date_from_raw))
        except ValueError:
            pass
    if date_to_raw:
        try:
            filters.append(Transaction.tx_date <= date.fromisoformat(date_to_raw))
        except ValueError:
            pass

    rows = db.execute(
        select(Transaction, AccountCard.nickname)
        .outerjoin(AccountCard, AccountCard.id == Transaction.account_id)
        .where(and_(*filters))
        .order_by(Transaction.tx_date.desc(), Transaction.id.desc())
    ).all()

    accounts = db.execute(
        select(AccountCard).where(AccountCard.user_id == user.id).order_by(AccountCard.nickname.asc())
    ).scalars().all()
    categories = db.execute(
        select(Transaction.category)
        .where(Transaction.user_id == user.id)
        .group_by(Transaction.category)
        .order_by(Transaction.category.asc())
    ).scalars().all()

    return templates.TemplateResponse(
        "transactions_history.html",
        {
            "request": request,
            "user": user,
            "rows": rows,
            "accounts": accounts,
            "categories": categories,
            "selected_account_ids": selected_account_ids,
            "selected_types": selected_types,
            "category_filter": category_filter,
            "month_filter": month_filter,
            "tx_date_filter": exact_date_raw,
            "date_from_filter": date_from_raw,
            "date_to_filter": date_to_raw,
        },
    )


@app.get("/profile")
def profile_page(request: Request, db: Session = Depends(get_db)):
    try:
        user = require_user(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)

    profile_feedback = request.session.pop("profile_feedback", None)
    users = db.execute(select(User).order_by(User.created_at.asc(), User.id.asc())).scalars().all()
    account_counts_rows = db.execute(
        select(AccountCard.user_id, func.count(AccountCard.id)).group_by(AccountCard.user_id)
    ).all()
    account_counts = {user_id: count for user_id, count in account_counts_rows}

    user_cards = []
    for listed_user in users:
        user_cards.append(
            {
                "id": listed_user.id,
                "username": listed_user.username,
                "initials": listed_user.initials,
                "email": listed_user.email or "",
                "profile_image": listed_user.profile_image,
                "created_at": listed_user.created_at.strftime("%Y-%m-%d %H:%M"),
                "accounts_count": int(account_counts.get(listed_user.id, 0)),
                "is_admin": listed_user.is_admin,
                "is_blocked": listed_user.is_blocked,
                "is_self": listed_user.id == user.id,
            }
        )

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "users": user_cards,
            "profile_feedback": profile_feedback,
        },
    )


@app.get("/api/dashboard")
def dashboard_data(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    current_month = get_or_create_open_month(db, user.id)
    stats = compute_month_stats(db, user.id, current_month.id)
    user_initials = normalize_initials(user.initials, user.username)
    return JSONResponse({"month": current_month.label, "user_initials": user_initials, **stats})


@app.get("/api/annual-current")
def annual_current_data(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    current_year = date.today().year
    payload = compute_annual_stats(db, user.id, current_year)
    payload["user_initials"] = normalize_initials(user.initials, user.username)
    return JSONResponse(payload)


@app.get("/api/investments/current")
def investments_current_data(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    current_month = get_or_create_open_month(db, user.id)
    payload = compute_investment_chart_data(db, user.id, current_month.label)
    payload["user_initials"] = normalize_initials(user.initials, user.username)
    return JSONResponse(payload)


@app.post("/api/investments/manual")
def save_manual_investment_value(
    request: Request,
    month_label: str = Form(...),
    acorns_value: str = Form(...),
    webull_value: str = Form(...),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    label = month_label.strip()
    try:
        parse_month_label(label)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid month. Use YYYY-MM format.") from exc

    parsed_acorns = parse_money_amount(acorns_value, label="Manual Acorns value", allow_zero=True)
    parsed_webull = parse_money_amount(webull_value, label="Manual Webull value", allow_zero=True)

    def upsert_platform(platform: str, value: Decimal) -> None:
        existing = db.execute(
            select(InvestmentPlatformOverride).where(
                and_(
                    InvestmentPlatformOverride.user_id == user.id,
                    InvestmentPlatformOverride.month_label == label,
                    InvestmentPlatformOverride.platform == platform,
                )
            )
        ).scalars().first()
        if existing:
            existing.manual_value = value
        else:
            db.add(
                InvestmentPlatformOverride(
                    user_id=user.id,
                    month_label=label,
                    platform=platform,
                    manual_value=value,
                )
            )

    upsert_platform("acorns", parsed_acorns)
    upsert_platform("webull", parsed_webull)
    db.commit()
    return JSONResponse(
        {
            "message": "Manual values saved",
            "month_label": label,
            "acorns_value": float(parsed_acorns),
            "webull_value": float(parsed_webull),
        }
    )


@app.post("/api/category-colors")
def save_category_colors(
    request: Request,
    payload: CategoryColorPayload,
    db: Session = Depends(get_db),
):
    user = require_user(request, db)

    for raw_category, raw_color in payload.colors.items():
        category_name = " ".join((raw_category or "").strip().split())
        if not category_name:
            continue
        color_hex = normalize_color_hex(raw_color)

        existing = db.execute(
            select(CategoryColorPreference).where(
                and_(
                    CategoryColorPreference.user_id == user.id,
                    CategoryColorPreference.category_name == category_name,
                )
            )
        ).scalars().first()
        if existing:
            existing.color_hex = color_hex
        else:
            db.add(
                CategoryColorPreference(
                    user_id=user.id,
                    category_name=category_name,
                    color_hex=color_hex,
                )
            )

    db.commit()
    return JSONResponse({"message": "Colors saved"})


@app.get("/api/snapshot/{month_id}")
def snapshot_data(month_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    snapshot = db.execute(
        select(MonthSnapshot, Month)
        .join(Month, Month.id == MonthSnapshot.month_id)
        .where(and_(MonthSnapshot.user_id == user.id, Month.id == month_id))
    ).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    snap, month = snapshot
    return JSONResponse(
        {
            "month": month.label,
            "user_initials": normalize_initials(user.initials, user.username),
            "totals": snap.totals_json,
            "categories": snap.categories_json.get("categories", []),
        }
    )


@app.post("/accounts/save")
def save_account(
    request: Request,
    id: str | None = Form(default=None),
    nickname: str = Form(...),
    type: str = Form(...),
    last4: str | None = Form(default=None),
    closing_date: str | None = Form(default=None),
    payment_date: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    account_id = parse_optional_int(id)
    nickname = nickname.strip()
    type = type.strip().lower()
    last4 = (last4 or "").strip() or None
    parsed_closing_date = parse_optional_date(closing_date)
    parsed_payment_date = parse_optional_date(payment_date)

    if type not in {"account", "card"}:
        raise HTTPException(status_code=400, detail="Tipo invalid")
    if last4 and (len(last4) != 4 or not last4.isdigit()):
        raise HTTPException(status_code=400, detail="Ultimos 4 digitos invalids")
    if type == "account":
        parsed_closing_date = None
        parsed_payment_date = None

    if account_id:
        account = db.execute(
            select(AccountCard).where(and_(AccountCard.id == account_id, AccountCard.user_id == user.id))
        ).scalars().first()
        if not account:
            raise HTTPException(status_code=404, detail="Account/card not found")
        account.nickname = nickname
        account.type = type
        account.last4 = last4
        account.closing_date = parsed_closing_date
        account.payment_date = parsed_payment_date
    else:
        account = AccountCard(
            user_id=user.id,
            nickname=nickname,
            type=type,
            last4=last4,
            closing_date=parsed_closing_date,
            payment_date=parsed_payment_date,
        )
        db.add(account)

    db.commit()
    return RedirectResponse(url="/app", status_code=303)


@app.post("/accounts/delete")
def delete_account(
    request: Request,
    id: int = Form(...),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    account = db.execute(
        select(AccountCard).where(and_(AccountCard.id == id, AccountCard.user_id == user.id))
    ).scalars().first()
    if account:
        db.delete(account)
        db.commit()
    return RedirectResponse(url="/app", status_code=303)


@app.post("/transactions/save")
def save_transaction(
    request: Request,
    id: str | None = Form(default=None),
    kind: str = Form(...),
    category: str = Form(...),
    amount: str = Form(...),
    tx_date: date = Form(...),
    description: str | None = Form(default=None),
    account_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    current_month = get_or_create_open_month(db, user.id)
    tx_id = parse_optional_int(id)
    parsed_account_id = parse_optional_int(account_id)
    kind = kind.strip().lower()
    parsed_amount = parse_money_amount(amount, label="Amount", allow_zero=True)

    selected_goal = None
    if kind.startswith("goal_transfer:"):
        goal_code = kind.split(":", 1)[1].strip().upper()
        if not goal_code:
            raise HTTPException(status_code=400, detail="Goal invalid para transferencia")
        selected_goal = db.execute(
            select(PlanningGoal).where(and_(PlanningGoal.user_id == user.id, PlanningGoal.goal_code == goal_code))
        ).scalars().first()
        if not selected_goal:
            raise HTTPException(status_code=400, detail="Goal not found for transfer")
        kind = GOAL_TRANSFER
        normalized_category = selected_goal.category_name
    elif kind in {EXPENSE, INCOME, INVESTMENT}:
        normalized_category = " ".join(category.strip().split())
    else:
        raise HTTPException(status_code=400, detail="Tipo de transacao invalid")

    if not normalized_category:
        raise HTTPException(status_code=400, detail="Category is required")

    existing_category = db.execute(
        select(Category).where(
            and_(
                Category.user_id == user.id,
                Category.kind == kind,
                Category.name == normalized_category,
            )
        )
    ).scalars().first()
    if not existing_category:
        db.add(Category(user_id=user.id, kind=kind, name=normalized_category))

    if tx_id:
        tx = db.execute(
            select(Transaction).where(and_(Transaction.id == tx_id, Transaction.user_id == user.id))
        ).scalars().first()
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        tx.kind = kind
        tx.category = normalized_category
        tx.amount = parsed_amount
        tx.tx_date = tx_date
        tx.description = description
        tx.account_id = parsed_account_id
    else:
        tx = Transaction(
            user_id=user.id,
            month_id=current_month.id,
            account_id=parsed_account_id,
            kind=kind,
            category=normalized_category,
            amount=parsed_amount,
            tx_date=tx_date,
            description=description,
        )
        db.add(tx)

    db.commit()
    return RedirectResponse(url="/app", status_code=303)


@app.post("/transactions/delete")
def delete_transaction(
    request: Request,
    id: int = Form(...),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    tx = db.execute(select(Transaction).where(and_(Transaction.id == id, Transaction.user_id == user.id))).scalars().first()
    if tx:
        db.delete(tx)
        db.commit()
    return RedirectResponse(url="/app", status_code=303)


@app.post("/bills/save")
def save_bill(
    request: Request,
    id: str | None = Form(default=None),
    title: str = Form(...),
    amount: str = Form(...),
    due_date: date = Form(...),
    paid: str | None = Form(default=None),
    account_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    bill_id = parse_optional_int(id)
    parsed_account_id = parse_optional_int(account_id)
    is_paid = paid == "on"
    parsed_amount = parse_money_amount(amount, label="Amount", allow_zero=True)

    if bill_id:
        bill = db.execute(select(Bill).where(and_(Bill.id == bill_id, Bill.user_id == user.id))).scalars().first()
        if not bill:
            raise HTTPException(status_code=404, detail="Bill not found")
        bill.title = title.strip()
        bill.amount = parsed_amount
        bill.due_date = due_date
        bill.paid = is_paid
        bill.account_id = parsed_account_id
    else:
        bill = Bill(
            user_id=user.id,
            title=title.strip(),
            amount=parsed_amount,
            due_date=due_date,
            paid=is_paid,
            account_id=parsed_account_id,
        )
        db.add(bill)

    db.commit()
    return RedirectResponse(url="/app", status_code=303)


@app.post("/bills/delete")
def delete_bill(request: Request, id: int = Form(...), db: Session = Depends(get_db)):
    user = require_user(request, db)
    bill = db.execute(select(Bill).where(and_(Bill.id == id, Bill.user_id == user.id))).scalars().first()
    if bill:
        db.delete(bill)
        db.commit()
    return RedirectResponse(url="/app", status_code=303)


@app.post("/month/close")
def close_month(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    current_month = get_or_create_open_month(db, user.id)

    stats = compute_month_stats(db, user.id, current_month.id)
    current_month.is_closed = True
    current_month.closed_at = datetime.utcnow()

    snapshot = MonthSnapshot(
        user_id=user.id,
        month_id=current_month.id,
        totals_json=stats["totals"],
        categories_json={"categories": stats["categories"]},
    )
    db.add(snapshot)

    new_month = Month(user_id=user.id, label=next_month(current_month.label), is_closed=False)
    db.add(new_month)

    db.commit()
    return RedirectResponse(url="/app", status_code=303)


@app.post("/admin/users/update")
def admin_update_user(
    request: Request,
    id: int = Form(...),
    username: str = Form(...),
    initials: str | None = Form(default=None),
    email: str | None = Form(default=None),
    password: str | None = Form(default=None),
    return_to: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(request, db)
    target = db.get(User, id)
    if not target or target.id == admin.id:
        raise HTTPException(status_code=404, detail="Target user not found")
    redirect_url = resolve_return_to(return_to, fallback="/profile")

    normalized_username = username.strip().lower()
    if len(normalized_username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    duplicate = db.execute(
        select(User).where(and_(User.username == normalized_username, User.id != target.id))
    ).scalars().first()
    if duplicate:
        raise HTTPException(status_code=400, detail="Username already exists")
    target.username = normalized_username
    target.initials = normalize_initials(initials, normalized_username)

    normalized_email = normalize_email(email)
    if not normalized_email or "@" not in normalized_email:
        raise HTTPException(status_code=400, detail="Email invalid")
    duplicate_email = db.execute(
        select(User).where(and_(User.email == normalized_email, User.id != target.id))
    ).scalars().first()
    if duplicate_email:
        raise HTTPException(status_code=400, detail="Email already exists")
    target.email = normalized_email

    cleaned_password = (password or "").strip()
    if cleaned_password:
        if len(cleaned_password) < 8:
            raise HTTPException(status_code=400, detail="Minimum password length is 8 characters")
        target.password_hash = hash_password(cleaned_password)

    db.commit()
    request.session["profile_feedback"] = {"level": "info", "message": f"User {target.username} updated"}
    return RedirectResponse(url=redirect_url, status_code=303)


@app.post("/admin/users/block")
def admin_toggle_user_block(
    request: Request,
    id: int = Form(...),
    action: str = Form(...),
    return_to: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(request, db)
    target = db.get(User, id)
    if not target or target.id == admin.id:
        raise HTTPException(status_code=404, detail="Target user not found")
    if action not in {"block", "unblock"}:
        raise HTTPException(status_code=400, detail="Invalid action")
    redirect_url = resolve_return_to(return_to, fallback="/profile")
    target.is_blocked = action == "block"
    db.commit()
    request.session["profile_feedback"] = {
        "level": "info",
        "message": f"User {target.username} {'blocked' if target.is_blocked else 'unblocked'}",
    }
    return RedirectResponse(url=redirect_url, status_code=303)


@app.post("/admin/users/delete")
def admin_delete_user(
    request: Request,
    id: int = Form(...),
    return_to: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(request, db)
    target = db.get(User, id)
    if not target or target.id == admin.id:
        raise HTTPException(status_code=404, detail="Target user not found")
    redirect_url = resolve_return_to(return_to, fallback="/profile")
    username = target.username
    db.delete(target)
    db.commit()
    request.session["profile_feedback"] = {"level": "info", "message": f"User {username} removed"}
    return RedirectResponse(url=redirect_url, status_code=303)


@app.post("/admin/users/delete-selected")
def admin_delete_selected_users(
    request: Request,
    user_ids: list[int] = Form(default=[]),
    return_to: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(request, db)
    redirect_url = resolve_return_to(return_to, fallback="/profile")
    selected_ids = sorted({int(user_id) for user_id in user_ids if int(user_id) != admin.id})
    if not selected_ids:
        request.session["profile_feedback"] = {"level": "warn", "message": "No user selected"}
        return RedirectResponse(url=redirect_url, status_code=303)

    targets = db.execute(select(User).where(User.id.in_(selected_ids))).scalars().all()
    if not targets:
        request.session["profile_feedback"] = {"level": "warn", "message": "No valid user selected for deletion"}
        return RedirectResponse(url=redirect_url, status_code=303)

    deleted_count = 0
    for target in targets:
        if target.id == admin.id:
            continue
        db.delete(target)
        deleted_count += 1
    db.commit()
    request.session["profile_feedback"] = {"level": "info", "message": f"{deleted_count} user(s) removed"}
    return RedirectResponse(url=redirect_url, status_code=303)


@app.post("/admin/users/role-selected")
def admin_update_selected_roles(
    request: Request,
    user_ids: list[int] = Form(default=[]),
    role_action: str = Form(...),
    return_to: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    admin = require_admin(request, db)
    redirect_url = resolve_return_to(return_to, fallback="/profile")
    if role_action not in {"make_admin", "remove_admin"}:
        request.session["profile_feedback"] = {"level": "danger", "message": "Invalid profile action"}
        return RedirectResponse(url=redirect_url, status_code=303)

    selected_ids = sorted({int(user_id) for user_id in user_ids if int(user_id) != admin.id})
    if not selected_ids:
        request.session["profile_feedback"] = {"level": "warn", "message": "No user selected"}
        return RedirectResponse(url=redirect_url, status_code=303)

    targets = db.execute(select(User).where(User.id.in_(selected_ids))).scalars().all()
    if not targets:
        request.session["profile_feedback"] = {"level": "warn", "message": "No valid user selected for update"}
        return RedirectResponse(url=redirect_url, status_code=303)

    updated_count = 0
    make_admin = role_action == "make_admin"
    for target in targets:
        if target.id == admin.id:
            continue
        if target.is_admin != make_admin:
            target.is_admin = make_admin
            updated_count += 1
    db.commit()

    action_text = "promoted to admin" if make_admin else "removed from admin"
    request.session["profile_feedback"] = {
        "level": "info",
        "message": f"{updated_count} user(s) {action_text}",
    }
    return RedirectResponse(url=redirect_url, status_code=303)


@app.post("/admin/users/create")
def admin_create_user(
    request: Request,
    username: str = Form(...),
    initials: str | None = Form(default=None),
    email: str = Form(...),
    password: str = Form(...),
    is_admin: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    normalized_username = username.strip().lower()
    normalized_email = normalize_email(email)
    cleaned_password = (password or "").strip()

    if len(normalized_username) < 3:
        request.session["profile_feedback"] = {"level": "danger", "message": "Username must be at least 3 characters"}
        return RedirectResponse(url="/profile", status_code=303)
    if not normalized_email or "@" not in normalized_email:
        request.session["profile_feedback"] = {"level": "danger", "message": "Email invalid"}
        return RedirectResponse(url="/profile", status_code=303)
    if len(cleaned_password) < 8:
        request.session["profile_feedback"] = {"level": "danger", "message": "Minimum password length is 8 characters"}
        return RedirectResponse(url="/profile", status_code=303)

    duplicate_user = db.execute(select(User).where(User.username == normalized_username)).scalars().first()
    if duplicate_user:
        request.session["profile_feedback"] = {"level": "danger", "message": "Username already exists"}
        return RedirectResponse(url="/profile", status_code=303)

    duplicate_email = db.execute(select(User).where(User.email == normalized_email)).scalars().first()
    if duplicate_email:
        request.session["profile_feedback"] = {"level": "danger", "message": "Email already registered"}
        return RedirectResponse(url="/profile", status_code=303)

    new_user = User(
        username=normalized_username,
        email=normalized_email,
        initials=normalize_initials(initials, normalized_username),
        password_hash=hash_password(cleaned_password),
        is_admin=is_admin == "on",
        is_blocked=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    get_or_create_open_month(db, new_user.id)
    request.session["profile_feedback"] = {"level": "info", "message": f"User {new_user.username} created"}
    return RedirectResponse(url="/profile", status_code=303)


@app.post("/profile/update")
def update_profile(
    request: Request,
    username: str = Form(...),
    initials: str | None = Form(default=None),
    email: str = Form(...),
    password: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    normalized_username = username.strip().lower()
    normalized_email = normalize_email(email)

    if len(normalized_username) < 3:
        request.session["profile_feedback"] = {"level": "danger", "message": "Username must be at least 3 characters"}
        return RedirectResponse(url="/profile", status_code=303)
    if not normalized_email or "@" not in normalized_email:
        request.session["profile_feedback"] = {"level": "danger", "message": "Email invalid"}
        return RedirectResponse(url="/profile", status_code=303)

    duplicate_username = db.execute(
        select(User).where(and_(User.username == normalized_username, User.id != user.id))
    ).scalars().first()
    if duplicate_username:
        request.session["profile_feedback"] = {"level": "danger", "message": "Username already exists"}
        return RedirectResponse(url="/profile", status_code=303)

    duplicate_email = db.execute(
        select(User).where(and_(User.email == normalized_email, User.id != user.id))
    ).scalars().first()
    if duplicate_email:
        request.session["profile_feedback"] = {"level": "danger", "message": "Email already registered"}
        return RedirectResponse(url="/profile", status_code=303)

    user.username = normalized_username
    user.initials = normalize_initials(initials, normalized_username)
    user.email = normalized_email

    cleaned_password = (password or "").strip()
    if cleaned_password:
        if len(cleaned_password) < 8:
            request.session["profile_feedback"] = {"level": "danger", "message": "Minimum password length is 8 characters"}
            return RedirectResponse(url="/profile", status_code=303)
        user.password_hash = hash_password(cleaned_password)

    if image is not None and image.filename:
        user.profile_image = save_profile_image_file(image, user_id=user.id)

    db.commit()
    request.session["profile_feedback"] = {"level": "info", "message": "Profile updated successfully"}
    return RedirectResponse(url="/profile", status_code=303)


@app.post("/planning/save")
def save_planning_goal(
    request: Request,
    objective: str = Form(...),
    target_amount: str = Form(...),
    target_date: str = Form(...),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)

    try:
        normalized_objective = " ".join(objective.strip().split())
        if not normalized_objective:
            raise HTTPException(status_code=400, detail="Goal required")
        parsed_target_amount = parse_planning_amount(target_amount)
        parsed_target_date = parse_planning_target_date(target_date)
    except HTTPException as exc:
        request.session["planning_feedback"] = {"level": "danger", "message": exc.detail}
        return RedirectResponse(url="/app#planning", status_code=303)

    months_count = months_until_target(date.today(), parsed_target_date)
    if months_count <= 0:
        request.session["planning_feedback"] = {
            "level": "danger",
            "message": "Target date must be today or later",
        }
        return RedirectResponse(url="/app#planning", status_code=303)

    monthly_saving = (parsed_target_amount / Decimal(months_count)).quantize(Decimal("0.01"))

    max_goal_id = db.execute(
        select(func.coalesce(func.max(PlanningGoal.id), 0)).where(PlanningGoal.user_id == user.id)
    ).scalar_one()
    next_seq = int(max_goal_id) + 1
    goal_code = build_goal_code(int(next_seq))
    goal_alias = derive_goal_alias(normalized_objective)
    category_name = f"Goal {goal_code} - {goal_alias}"[:120]

    goal = PlanningGoal(
        user_id=user.id,
        goal_code=goal_code,
        goal_alias=goal_alias,
        category_name=category_name,
        objective=normalized_objective,
        target_amount=parsed_target_amount,
        target_date=parsed_target_date,
        monthly_saving=monthly_saving,
    )
    db.add(goal)

    existing_category = db.execute(
        select(Category).where(
            and_(
                Category.user_id == user.id,
                Category.kind == INVESTMENT,
                Category.name == category_name,
            )
        )
    ).scalars().first()
    if not existing_category:
        db.add(Category(user_id=user.id, kind=INVESTMENT, name=category_name))

    db.commit()
    request.session["planning_feedback"] = {
        "level": "info",
        "message": f"Goal created ({goal_code}) with investment category: {category_name}",
    }
    return RedirectResponse(url="/app#planning", status_code=303)


@app.post("/planning/delete")
def delete_planning_goal(
    request: Request,
    id: int = Form(...),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    goal = db.execute(
        select(PlanningGoal).where(and_(PlanningGoal.id == id, PlanningGoal.user_id == user.id))
    ).scalars().first()
    if goal:
        db.delete(goal)
        db.commit()
        request.session["planning_feedback"] = {
            "level": "info",
            "message": f"Goal {goal.goal_code} removed",
        }
    else:
        request.session["planning_feedback"] = {"level": "warn", "message": "Goal not found"}
    return RedirectResponse(url="/app#planning", status_code=303)


@app.get("/health")
def health():
    return {"status": "ok"}

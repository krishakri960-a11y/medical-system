from datetime import date, datetime
from decimal import Decimal

from urllib.parse import urlencode

from flask import flash, redirect, request, url_for
from flask_login import current_user
from functools import wraps

from app.models import Bill


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("main.login", next=request.url))
        if current_user.role != "admin":
            flash("You do not have permission to access that page.", "danger")
            return redirect(url_for("staff.dashboard"))
        return view(*args, **kwargs)

    return wrapped


def staff_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("main.login", next=request.url))
        if current_user.role != "staff":
            flash("Staff area only.", "danger")
            return redirect(url_for("admin.dashboard"))
        return view(*args, **kwargs)

    return wrapped


def next_bill_number():
    prefix = date.today().strftime("BILL-%Y%m%d")
    last = (
        Bill.query.filter(Bill.bill_number.like(f"{prefix}-%"))
        .order_by(Bill.id.desc())
        .first()
    )
    n = 1
    if last:
        try:
            n = int(last.bill_number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            n = 1
    return f"{prefix}-{n:04d}"


def dec(val):
    if val is None or val == "":
        return Decimal("0")
    return Decimal(str(val))


def paginate_url(page: int) -> str:
    """Build same URL as current request with a different page (preserves query string)."""
    pairs = []
    for k in request.args:
        if k == "page":
            continue
        for v in request.args.getlist(k):
            pairs.append((k, v))
    pairs.append(("page", str(page)))
    qs = urlencode(pairs)
    base = url_for(request.endpoint, **request.view_args)
    return f"{base}?{qs}" if qs else base

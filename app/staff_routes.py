from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from app import db
from app.models import (
    Bill,
    BillItem,
    Brand,
    Category,
    Customer,
    Medicine,
    MedicineReturn,
    today_bounds,
)
from app.utils import dec, next_bill_number, staff_required

staff_bp = Blueprint("staff", __name__)

PER_PAGE = 15
RECENT_BILLS_DROPDOWN = 100


def _staff_bills_today():
    start, end = today_bounds()
    return Bill.query.filter(
        Bill.created_at >= start,
        Bill.created_at <= end,
        Bill.staff_id == current_user.id,
    )


@staff_bp.route("/dashboard")
@login_required
@staff_required
def dashboard():
    start, end = today_bounds()
    meds_avail = Medicine.query.filter(Medicine.quantity > 0).count()
    low = (
        Medicine.query.filter(Medicine.quantity <= Medicine.min_stock_level)
        .filter(Medicine.quantity > 0)
        .order_by(Medicine.quantity)
        .limit(10)
        .all()
    )
    today_bills = _staff_bills_today().count()
    today_sales = (
        db.session.query(func.coalesce(func.sum(Bill.grand_total), 0))
        .filter(
            Bill.created_at >= start,
            Bill.created_at <= end,
            Bill.staff_id == current_user.id,
        )
        .scalar()
        or 0
    )
    recent_bills = (
        Bill.query.filter(Bill.staff_id == current_user.id)
        .order_by(Bill.created_at.desc())
        .limit(8)
        .all()
    )
    return render_template(
        "staff/dashboard.html",
        meds_avail=meds_avail,
        low=low,
        today_bills=today_bills,
        today_sales=today_sales,
        recent_bills=recent_bills,
    )


@staff_bp.route("/medicines")
@login_required
@staff_required
def medicines():
    page = request.args.get("page", 1, type=int)
    q = (request.args.get("q") or "").strip()
    brand_id = request.args.get("brand_id", type=int)
    cat_id = request.args.get("category_id", type=int)
    query = Medicine.query
    if q:
        query = query.filter(
            or_(
                Medicine.name.ilike(f"%{q}%"),
                Medicine.batch_number.ilike(f"%{q}%"),
            )
        )
    if brand_id:
        query = query.filter_by(brand_id=brand_id)
    if cat_id:
        query = query.filter_by(category_id=cat_id)
    pagination = (
        query.order_by(Medicine.name)
        .paginate(page=page, per_page=PER_PAGE, error_out=False)
    )
    return render_template(
        "staff/medicines.html",
        pagination=pagination,
        medicines=pagination.items,
        brands=Brand.query.order_by(Brand.name).all(),
        categories=Category.query.order_by(Category.name).all(),
        q=q,
        brand_id=brand_id,
        category_id=cat_id,
    )


@staff_bp.route("/medicines/<int:mid>")
@login_required
@staff_required
def medicine_detail(mid):
    med = Medicine.query.get_or_404(mid)
    return render_template("staff/medicine_detail.html", medicine=med)


@staff_bp.route("/customers")
@login_required
@staff_required
def customers():
    page = request.args.get("page", 1, type=int)
    q = (request.args.get("q") or "").strip()
    query = Customer.query
    if q:
        query = query.filter(
            or_(
                Customer.name.ilike(f"%{q}%"),
                Customer.contact_number.ilike(f"%{q}%"),
                Customer.email.ilike(f"%{q}%"),
            )
        )
    pagination = query.order_by(Customer.name).paginate(
        page=page, per_page=PER_PAGE, error_out=False
    )
    return render_template(
        "staff/customers.html",
        pagination=pagination,
        customers=pagination.items,
        q=q,
    )


@staff_bp.route("/customers/new", methods=["GET", "POST"])
@login_required
@staff_required
def customer_new():
    if request.method == "POST":
        c = Customer(
            name=(request.form.get("name") or "").strip() or "Customer",
            contact_number=(request.form.get("contact_number") or "").strip(),
            email=(request.form.get("email") or "").strip(),
            address=(request.form.get("address") or "").strip(),
        )
        db.session.add(c)
        db.session.commit()
        flash("Customer created.", "success")
        return redirect(url_for("staff.customer_detail", cid=c.id))
    return render_template("staff/customer_form.html", customer=None)


@staff_bp.route("/customers/<int:cid>")
@login_required
@staff_required
def customer_detail(cid):
    c = Customer.query.get_or_404(cid)
    bills = (
        c.bills.filter(Bill.staff_id == current_user.id)
        .order_by(Bill.created_at.desc())
        .limit(50)
        .all()
    )
    bill_count = c.bills.filter(Bill.staff_id == current_user.id).count()
    total_spend = (
        db.session.query(func.coalesce(func.sum(Bill.grand_total), 0))
        .filter(Bill.customer_id == cid, Bill.staff_id == current_user.id)
        .scalar()
        or 0
    )
    return render_template(
        "staff/customer_detail.html",
        customer=c,
        bills=bills,
        bill_count=bill_count,
        total_spend=total_spend,
    )


@staff_bp.route("/customers/<int:cid>/edit", methods=["GET", "POST"])
@login_required
@staff_required
def customer_edit(cid):
    c = Customer.query.get_or_404(cid)
    if request.method == "POST":
        c.name = (request.form.get("name") or "").strip() or c.name
        c.contact_number = (request.form.get("contact_number") or "").strip()
        c.email = (request.form.get("email") or "").strip()
        c.address = (request.form.get("address") or "").strip()
        db.session.commit()
        flash("Customer updated.", "success")
        return redirect(url_for("staff.customer_detail", cid=c.id))
    return render_template("staff/customer_form.html", customer=c)


def _staff_build_bill():
    customer_id = int(request.form.get("customer_id"))
    discount_p = dec(request.form.get("discount_percent"))
    tax_p = dec(request.form.get("tax_percent"))
    notes = request.form.get("notes") or ""
    med_ids = request.form.getlist("medicine_id")
    qtys = request.form.getlist("qty")
    if not med_ids or not qtys or len(med_ids) != len(qtys):
        return None, "Add at least one line with medicine and quantity."
    subtotal = Decimal("0")
    lines = []
    for mid_s, q_s in zip(med_ids, qtys):
        if not mid_s:
            continue
        mid = int(mid_s)
        q = int(q_s or 0)
        if q <= 0:
            continue
        med = Medicine.query.get(mid)
        if not med or med.quantity < q:
            return None, f"Insufficient stock for {med.name if med else 'item'}."
        line = q * med.selling_price
        subtotal += line
        lines.append((med, q, med.selling_price, med.purchase_price))
    if not lines:
        return None, "No valid lines."
    disc_amt = (subtotal * discount_p / Decimal("100")).quantize(Decimal("0.01"))
    after_disc = subtotal - disc_amt
    tax_amt = (after_disc * tax_p / Decimal("100")).quantize(Decimal("0.01"))
    grand = (after_disc + tax_amt).quantize(Decimal("0.01"))
    return {
        "customer_id": customer_id,
        "discount_percent": discount_p,
        "tax_percent": tax_p,
        "notes": notes,
        "subtotal": subtotal,
        "discount_amount": disc_amt,
        "tax_amount": tax_amt,
        "grand_total": grand,
        "lines": lines,
    }, None


@staff_bp.route("/billing", methods=["GET", "POST"])
@login_required
@staff_required
def billing():
    if request.method == "POST":
        data, err = _staff_build_bill()
        if err:
            flash(err, "danger")
            return redirect(url_for("staff.billing"))
        bill = Bill(
            bill_number=next_bill_number(),
            customer_id=data["customer_id"],
            staff_id=current_user.id,
            discount_percent=data["discount_percent"],
            tax_percent=data["tax_percent"],
            subtotal=data["subtotal"],
            discount_amount=data["discount_amount"],
            tax_amount=data["tax_amount"],
            grand_total=data["grand_total"],
            notes=data["notes"],
        )
        db.session.add(bill)
        db.session.flush()
        for med, q, price, cost in data["lines"]:
            db.session.add(
                BillItem(
                    bill_id=bill.id,
                    medicine_id=med.id,
                    quantity=q,
                    unit_price=price,
                    unit_cost=cost,
                    line_total=(q * price).quantize(Decimal("0.01")),
                )
            )
            med.quantity -= q
        db.session.commit()
        flash("Bill saved. You can print the receipt or return to sales.", "success")
        return redirect(url_for("staff.bill_detail", bid=bill.id))
    return render_template(
        "staff/billing.html",
        customers=Customer.query.order_by(Customer.name).all(),
        medicines=Medicine.query.filter(Medicine.quantity > 0).order_by(Medicine.name).all(),
    )


@staff_bp.route("/billing/<int:bid>")
@login_required
@staff_required
def bill_detail(bid):
    bill = Bill.query.get_or_404(bid)
    if bill.staff_id != current_user.id:
        flash("You can only view your own bills.", "danger")
        return redirect(url_for("staff.sales"))
    return render_template("staff/bill_detail.html", bill=bill)


@staff_bp.route("/billing/<int:bid>/print")
@login_required
@staff_required
def bill_print(bid):
    bill = Bill.query.get_or_404(bid)
    if bill.staff_id != current_user.id:
        flash("Not your bill.", "danger")
        return redirect(url_for("staff.sales"))
    return render_template("staff/bill_print.html", bill=bill)


@staff_bp.route("/sales")
@login_required
@staff_required
def sales():
    page = request.args.get("page", 1, type=int)
    bill_q = (request.args.get("bill") or "").strip()
    cust_q = (request.args.get("customer") or "").strip()
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    qry = Bill.query.filter(Bill.staff_id == current_user.id)
    if bill_q:
        qry = qry.filter(Bill.bill_number.ilike(f"%{bill_q}%"))
    if cust_q:
        qry = qry.join(Customer).filter(Customer.name.ilike(f"%{cust_q}%"))
    if date_from:
        qry = qry.filter(Bill.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
    if date_to:
        end_d = datetime.strptime(date_to, "%Y-%m-%d").date() + timedelta(days=1)
        qry = qry.filter(Bill.created_at < datetime.combine(end_d, datetime.min.time()))
    pagination = qry.order_by(Bill.created_at.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False
    )
    return render_template(
        "staff/sales.html",
        pagination=pagination,
        bills=pagination.items,
        bill_q=bill_q,
        cust_q=cust_q,
        date_from=date_from,
        date_to=date_to,
    )


@staff_bp.route("/stock")
@login_required
@staff_required
def stock():
    view = request.args.get("view", "all")
    q = (request.args.get("q") or "").strip()
    if view == "low":
        rows = (
            Medicine.query.filter(Medicine.quantity <= Medicine.min_stock_level)
            .filter(Medicine.quantity > 0)
            .order_by(Medicine.quantity)
            .all()
        )
    elif view == "expired":
        rows = (
            Medicine.query.filter(Medicine.expiry_date < date.today())
            .order_by(Medicine.expiry_date)
            .all()
        )
    elif view == "soon":
        soon = date.today() + timedelta(days=60)
        rows = (
            Medicine.query.filter(
                Medicine.expiry_date >= date.today(),
                Medicine.expiry_date <= soon,
            )
            .order_by(Medicine.expiry_date)
            .all()
        )
    else:
        query = Medicine.query
        if q:
            query = query.filter(
                or_(
                    Medicine.name.ilike(f"%{q}%"),
                    Medicine.batch_number.ilike(f"%{q}%"),
                )
            )
        rows = query.order_by(Medicine.name).all()
    return render_template("staff/stock.html", medicines=rows, view=view, q=q)


@staff_bp.route("/returns")
@login_required
@staff_required
def returns_list():
    page = request.args.get("page", 1, type=int)
    bill_q = (request.args.get("bill") or "").strip()
    qry = MedicineReturn.query.filter(MedicineReturn.staff_id == current_user.id)
    if bill_q:
        qry = qry.join(Bill).filter(Bill.bill_number.ilike(f"%{bill_q}%"))
    pagination = qry.order_by(MedicineReturn.return_date.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False
    )
    return render_template(
        "staff/returns_list.html",
        pagination=pagination,
        returns=pagination.items,
        bill_q=bill_q,
    )


@staff_bp.route("/returns/new", methods=["GET", "POST"])
@login_required
@staff_required
def returns_new():
    if request.method == "POST":
        try:
            bid = int(request.form.get("bill_id"))
            mid = int(request.form.get("medicine_id"))
            qty = int(request.form.get("quantity") or 0)
        except (ValueError, TypeError):
            flash("Invalid return.", "danger")
            return redirect(url_for("staff.returns_new"))
        bill = Bill.query.get_or_404(bid)
        if bill.staff_id != current_user.id:
            flash("You can only process returns for your own bills.", "danger")
            return redirect(url_for("staff.returns_new"))
        item = BillItem.query.filter_by(bill_id=bid, medicine_id=mid).first()
        if not item or qty <= 0 or qty > item.quantity:
            flash("Invalid quantity for this bill line.", "danger")
            return redirect(url_for("staff.returns_new"))
        unit = item.unit_price
        refund = (unit * qty).quantize(Decimal("0.01"))
        med = Medicine.query.get(mid)
        if med:
            med.quantity += qty
        db.session.add(
            MedicineReturn(
                bill_id=bid,
                medicine_id=mid,
                quantity=qty,
                refund_amount=refund,
                staff_id=current_user.id,
                reason=request.form.get("reason") or "",
            )
        )
        db.session.commit()
        flash(f"Return recorded. Refund: ₹ {refund}.", "success")
        return redirect(url_for("staff.returns_list"))
    bills = (
        Bill.query.filter(Bill.staff_id == current_user.id)
        .order_by(Bill.created_at.desc())
        .limit(RECENT_BILLS_DROPDOWN)
        .all()
    )
    return render_template("staff/returns_new.html", bills=bills)


@staff_bp.route("/api/bill/<int:bid>/lines")
@login_required
@staff_required
def api_bill_lines(bid):
    bill = Bill.query.get_or_404(bid)
    if bill.staff_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403
    items = BillItem.query.filter_by(bill_id=bid).all()
    return jsonify(
        [
            {
                "medicine_id": i.medicine_id,
                "name": i.medicine.name,
                "max_qty": i.quantity,
            }
            for i in items
        ]
    )


@staff_bp.route("/profile", methods=["GET", "POST"])
@login_required
@staff_required
def profile():
    if request.method == "POST":
        current_user.full_name = (request.form.get("full_name") or "").strip() or current_user.full_name
        current_user.email = request.form.get("email") or ""
        current_user.phone = request.form.get("phone") or ""
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("staff.profile"))
    return render_template("staff/profile.html")


@staff_bp.route("/password", methods=["GET", "POST"])
@login_required
@staff_required
def change_password():
    if request.method == "POST":
        cur = request.form.get("current") or ""
        new = request.form.get("new") or ""
        conf = request.form.get("confirm") or ""
        if not current_user.check_password(cur):
            flash("Current password incorrect.", "danger")
        elif len(new) < 6:
            flash("New password must be at least 6 characters.", "danger")
        elif new != conf:
            flash("Confirmation does not match.", "danger")
        else:
            current_user.set_password(new)
            db.session.commit()
            flash("Password updated.", "success")
            return redirect(url_for("staff.dashboard"))
    return render_template("staff/change_password.html")

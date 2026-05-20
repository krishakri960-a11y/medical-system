from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import extract, func, or_

from app import db
from app.models import (
    Bill,
    BillItem,
    Brand,
    Category,
    Customer,
    Medicine,
    MedicineReturn,
    Purchase,
    Supplier,
    User,
    today_bounds,
)
from app.utils import admin_required, dec, next_bill_number

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    low_stock = (
        Medicine.query.filter(Medicine.quantity <= Medicine.min_stock_level)
        .filter(Medicine.quantity > 0)
        .count()
    )
    expired = Medicine.query.filter(Medicine.expiry_date < date.today()).count()
    start, end = today_bounds()
    today_sales = (
        db.session.query(func.coalesce(func.sum(Bill.grand_total), 0))
        .filter(Bill.created_at >= start, Bill.created_at <= end)
        .scalar()
    )
    total_stock_value = db.session.query(
        func.coalesce(func.sum(Medicine.quantity * Medicine.purchase_price), 0)
    ).scalar()
    ctx = {
        "totals": {
            "medicines": Medicine.query.count(),
            "brands": Brand.query.count(),
            "categories": Category.query.count(),
            "suppliers": Supplier.query.count(),
            "customers": Customer.query.count(),
            "sales_count": Bill.query.count(),
            "stock_value": total_stock_value or 0,
            "low_stock": low_stock,
            "expired": expired,
            "today_sales": today_sales or 0,
        },
        "recent_bills": Bill.query.order_by(Bill.created_at.desc()).limit(8).all(),
    }
    return render_template("admin/dashboard.html", **ctx)


# --- Brands ---
@admin_bp.route("/brands")
@login_required
@admin_required
def brands():
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int) or 1
    query = Brand.query
    if q:
        query = query.filter(Brand.name.ilike(f"%{q}%"))
    query = query.order_by(Brand.name)
    pagination = query.paginate(page=page, per_page=15, error_out=False)
    return render_template(
        "admin/brands_list.html",
        brands=pagination.items,
        pagination=pagination,
        q=q,
    )


@admin_bp.route("/brands/new", methods=["GET", "POST"])
@login_required
@admin_required
def brand_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        desc = request.form.get("description") or ""
        if not name:
            flash("Brand name is required.", "danger")
            return redirect(url_for("admin.brand_new"))
        if Brand.query.filter_by(name=name).first():
            flash("A brand with this name already exists.", "warning")
            return redirect(url_for("admin.brand_new"))
        b = Brand(name=name, description=desc)
        db.session.add(b)
        db.session.commit()
        flash("Brand created successfully.", "success")
        return redirect(url_for("admin.brand_detail", bid=b.id))
    return render_template("admin/brand_form.html", brand=None)


@admin_bp.route("/brands/<int:bid>")
@login_required
@admin_required
def brand_detail(bid):
    b = Brand.query.get_or_404(bid)
    med_query = b.medicines.order_by(Medicine.name, Medicine.batch_number)
    med_count = med_query.count()
    medicines = med_query.limit(50).all()
    return render_template(
        "admin/brand_detail.html",
        brand=b,
        medicines=medicines,
        med_count=med_count,
    )


@admin_bp.route("/brands/<int:bid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def brand_edit(bid):
    b = Brand.query.get_or_404(bid)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Brand name is required.", "danger")
            return redirect(url_for("admin.brand_edit", bid=bid))
        other = Brand.query.filter(Brand.name == name, Brand.id != bid).first()
        if other:
            flash("Another brand already uses this name.", "warning")
            return redirect(url_for("admin.brand_edit", bid=bid))
        b.name = name
        b.description = request.form.get("description") or ""
        db.session.commit()
        flash("Brand updated.", "success")
        return redirect(url_for("admin.brand_detail", bid=b.id))
    return render_template("admin/brand_form.html", brand=b)


@admin_bp.route("/brands/<int:bid>/delete", methods=["POST"])
@login_required
@admin_required
def brand_delete(bid):
    b = Brand.query.get_or_404(bid)
    if b.medicines.count():
        flash("Cannot delete: medicines are still assigned to this brand.", "danger")
        return redirect(url_for("admin.brand_detail", bid=bid))
    db.session.delete(b)
    db.session.commit()
    flash("Brand removed.", "info")
    return redirect(url_for("admin.brands"))


# --- Categories ---
@admin_bp.route("/categories")
@login_required
@admin_required
def categories():
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int) or 1
    query = Category.query
    if q:
        query = query.filter(Category.name.ilike(f"%{q}%"))
    query = query.order_by(Category.name)
    pagination = query.paginate(page=page, per_page=15, error_out=False)
    return render_template(
        "admin/categories_list.html",
        categories=pagination.items,
        pagination=pagination,
        q=q,
    )


@admin_bp.route("/categories/new", methods=["GET", "POST"])
@login_required
@admin_required
def category_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Category name is required.", "danger")
            return redirect(url_for("admin.category_new"))
        if Category.query.filter_by(name=name).first():
            flash("This category already exists.", "warning")
            return redirect(url_for("admin.category_new"))
        c = Category(name=name, description=request.form.get("description") or "")
        db.session.add(c)
        db.session.commit()
        flash("Category created.", "success")
        return redirect(url_for("admin.category_detail", cid=c.id))
    return render_template("admin/category_form.html", category=None)


@admin_bp.route("/categories/<int:cid>")
@login_required
@admin_required
def category_detail(cid):
    c = Category.query.get_or_404(cid)
    med_query = c.medicines.order_by(Medicine.name, Medicine.batch_number)
    med_count = med_query.count()
    medicines = med_query.limit(50).all()
    return render_template(
        "admin/category_detail.html",
        category=c,
        medicines=medicines,
        med_count=med_count,
    )


@admin_bp.route("/categories/<int:cid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def category_edit(cid):
    c = Category.query.get_or_404(cid)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Name is required.", "danger")
            return redirect(url_for("admin.category_edit", cid=cid))
        if Category.query.filter(Category.name == name, Category.id != cid).first():
            flash("Another category uses this name.", "warning")
            return redirect(url_for("admin.category_edit", cid=cid))
        c.name = name
        c.description = request.form.get("description") or ""
        db.session.commit()
        flash("Category updated.", "success")
        return redirect(url_for("admin.category_detail", cid=c.id))
    return render_template("admin/category_form.html", category=c)


@admin_bp.route("/categories/<int:cid>/delete", methods=["POST"])
@login_required
@admin_required
def category_delete(cid):
    c = Category.query.get_or_404(cid)
    if c.medicines.count():
        flash("Cannot delete: medicines use this category.", "danger")
        return redirect(url_for("admin.category_detail", cid=cid))
    db.session.delete(c)
    db.session.commit()
    flash("Category deleted.", "info")
    return redirect(url_for("admin.categories"))


# --- Suppliers ---
@admin_bp.route("/suppliers")
@login_required
@admin_required
def suppliers():
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int) or 1
    query = Supplier.query
    if q:
        query = query.filter(
            or_(
                Supplier.name.ilike(f"%{q}%"),
                Supplier.company_name.ilike(f"%{q}%"),
                Supplier.email.ilike(f"%{q}%"),
            )
        )
    query = query.order_by(Supplier.name)
    pagination = query.paginate(page=page, per_page=12, error_out=False)
    return render_template(
        "admin/suppliers_list.html",
        suppliers=pagination.items,
        pagination=pagination,
        q=q,
    )


@admin_bp.route("/suppliers/new", methods=["GET", "POST"])
@login_required
@admin_required
def supplier_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Supplier name is required.", "danger")
            return redirect(url_for("admin.supplier_new"))
        s = Supplier(
            name=name,
            contact_number=request.form.get("contact_number") or "",
            email=request.form.get("email") or "",
            address=request.form.get("address") or "",
            company_name=request.form.get("company_name") or "",
        )
        db.session.add(s)
        db.session.commit()
        flash("Supplier added.", "success")
        return redirect(url_for("admin.supplier_detail", sid=s.id))
    return render_template("admin/supplier_form.html", supplier=None)


@admin_bp.route("/suppliers/<int:sid>")
@login_required
@admin_required
def supplier_detail(sid):
    s = Supplier.query.get_or_404(sid)
    medicines = s.medicines.order_by(Medicine.name).limit(40).all()
    purchases = (
        s.purchases.order_by(Purchase.purchase_date.desc()).limit(30).all()
    )
    return render_template(
        "admin/supplier_detail.html",
        supplier=s,
        medicines=medicines,
        purchases=purchases,
        med_count=s.medicines.count(),
        purchase_count=s.purchases.count(),
    )


@admin_bp.route("/suppliers/<int:sid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def supplier_edit(sid):
    s = Supplier.query.get_or_404(sid)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Name is required.", "danger")
            return redirect(url_for("admin.supplier_edit", sid=sid))
        s.name = name
        s.contact_number = request.form.get("contact_number") or ""
        s.email = request.form.get("email") or ""
        s.address = request.form.get("address") or ""
        s.company_name = request.form.get("company_name") or ""
        db.session.commit()
        flash("Supplier updated.", "success")
        return redirect(url_for("admin.supplier_detail", sid=s.id))
    return render_template("admin/supplier_form.html", supplier=s)


@admin_bp.route("/suppliers/<int:sid>/delete", methods=["POST"])
@login_required
@admin_required
def supplier_delete(sid):
    s = Supplier.query.get_or_404(sid)
    if s.medicines.count():
        flash("Cannot delete: inventory references this supplier.", "danger")
        return redirect(url_for("admin.supplier_detail", sid=sid))
    db.session.delete(s)
    db.session.commit()
    flash("Supplier deleted.", "info")
    return redirect(url_for("admin.suppliers"))


# --- Medicines ---
@admin_bp.route("/medicines")
@login_required
@admin_required
def medicines():
    q = (request.args.get("q") or "").strip()
    brand_id = request.args.get("brand_id", type=int)
    cat_id = request.args.get("category_id", type=int)
    page = request.args.get("page", 1, type=int) or 1
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
    query = query.order_by(Medicine.name, Medicine.batch_number)
    pagination = query.paginate(page=page, per_page=12, error_out=False)
    return render_template(
        "admin/medicines_list.html",
        medicines=pagination.items,
        pagination=pagination,
        brands=Brand.query.order_by(Brand.name).all(),
        categories=Category.query.order_by(Category.name).all(),
        suppliers=Supplier.query.order_by(Supplier.name).all(),
        q=q,
        brand_id=brand_id,
        category_id=cat_id,
    )


@admin_bp.route("/medicines/new", methods=["GET", "POST"])
@login_required
@admin_required
def medicine_new():
    if request.method == "POST":
        try:
            m = Medicine(
                name=(request.form.get("name") or "").strip() or "Medicine",
                brand_id=int(request.form.get("brand_id")),
                category_id=int(request.form.get("category_id")),
                supplier_id=int(request.form.get("supplier_id")),
                batch_number=(request.form.get("batch_number") or "").strip() or "BATCH",
                manufacturing_date=datetime.strptime(
                    request.form.get("manufacturing_date"), "%Y-%m-%d"
                ).date(),
                expiry_date=datetime.strptime(
                    request.form.get("expiry_date"), "%Y-%m-%d"
                ).date(),
                purchase_price=dec(request.form.get("purchase_price")),
                selling_price=dec(request.form.get("selling_price")),
                quantity=int(request.form.get("quantity") or 0),
                min_stock_level=int(request.form.get("min_stock_level") or 10),
                description=request.form.get("description") or "",
            )
        except (ValueError, TypeError) as e:
            flash(f"Check all fields: {e}", "danger")
            return redirect(url_for("admin.medicine_new"))
        db.session.add(m)
        db.session.commit()
        flash("Medicine / batch line created.", "success")
        return redirect(url_for("admin.medicine_detail", mid=m.id))
    prefill = {
        "brand_id": request.args.get("brand_id", type=int),
        "category_id": request.args.get("category_id", type=int),
        "supplier_id": request.args.get("supplier_id", type=int),
    }
    return render_template(
        "admin/medicine_form.html",
        medicine=None,
        brands=Brand.query.order_by(Brand.name).all(),
        categories=Category.query.order_by(Category.name).all(),
        suppliers=Supplier.query.order_by(Supplier.name).all(),
        prefill=prefill,
    )


@admin_bp.route("/medicines/<int:mid>")
@login_required
@admin_required
def medicine_detail(mid):
    m = Medicine.query.get_or_404(mid)
    units_sold = (
        db.session.query(func.coalesce(func.sum(BillItem.quantity), 0))
        .filter(BillItem.medicine_id == m.id)
        .scalar()
        or 0
    )
    revenue = (
        db.session.query(func.coalesce(func.sum(BillItem.line_total), 0))
        .filter(BillItem.medicine_id == m.id)
        .scalar()
        or 0
    )
    recent_items = (
        BillItem.query.filter_by(medicine_id=m.id)
        .join(Bill)
        .order_by(Bill.created_at.desc())
        .limit(15)
        .all()
    )
    purchase_rows = (
        m.purchase_lines.order_by(Purchase.purchase_date.desc()).limit(20).all()
    )
    stock_value = (m.quantity or 0) * (m.purchase_price or 0)
    return render_template(
        "admin/medicine_detail.html",
        medicine=m,
        units_sold=units_sold,
        revenue=revenue,
        stock_value=stock_value,
        recent_items=recent_items,
        purchase_rows=purchase_rows,
    )


@admin_bp.route("/medicines/<int:mid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def medicine_edit(mid):
    m = Medicine.query.get_or_404(mid)
    if request.method == "POST":
        try:
            m.name = (request.form.get("name") or "").strip() or m.name
            m.brand_id = int(request.form.get("brand_id"))
            m.category_id = int(request.form.get("category_id"))
            m.supplier_id = int(request.form.get("supplier_id"))
            m.batch_number = (request.form.get("batch_number") or "").strip() or m.batch_number
            m.manufacturing_date = datetime.strptime(
                request.form.get("manufacturing_date"), "%Y-%m-%d"
            ).date()
            m.expiry_date = datetime.strptime(
                request.form.get("expiry_date"), "%Y-%m-%d"
            ).date()
            m.purchase_price = dec(request.form.get("purchase_price"))
            m.selling_price = dec(request.form.get("selling_price"))
            m.quantity = int(request.form.get("quantity") or 0)
            m.min_stock_level = int(request.form.get("min_stock_level") or 10)
            m.description = request.form.get("description") or ""
        except (ValueError, TypeError) as e:
            flash(f"Invalid data: {e}", "danger")
            return redirect(url_for("admin.medicine_edit", mid=mid))
        db.session.commit()
        flash("Medicine updated.", "success")
        return redirect(url_for("admin.medicine_detail", mid=m.id))
    return render_template(
        "admin/medicine_form.html",
        medicine=m,
        brands=Brand.query.order_by(Brand.name).all(),
        categories=Category.query.order_by(Category.name).all(),
        suppliers=Supplier.query.order_by(Supplier.name).all(),
        prefill={},
    )


@admin_bp.route("/medicines/<int:mid>/delete", methods=["POST"])
@login_required
@admin_required
def medicine_delete(mid):
    m = Medicine.query.get_or_404(mid)
    if m.bill_items.count():
        flash("Cannot delete: this batch appears on historical bills.", "danger")
        return redirect(url_for("admin.medicine_detail", mid=mid))
    db.session.delete(m)
    db.session.commit()
    flash("Medicine line deleted.", "info")
    return redirect(url_for("admin.medicines"))


# --- Stock ---
@admin_bp.route("/stock")
@login_required
@admin_required
def stock_index():
    q = (request.args.get("q") or "").strip()
    query = Medicine.query
    if q:
        query = query.filter(Medicine.name.ilike(f"%{q}%"))
    rows = query.order_by(Medicine.name).all()
    return render_template("admin/stock.html", medicines=rows, q=q, view="all")


@admin_bp.route("/stock/low")
@login_required
@admin_required
def stock_low():
    rows = (
        Medicine.query.filter(Medicine.quantity <= Medicine.min_stock_level)
        .filter(Medicine.quantity > 0)
        .order_by(Medicine.quantity)
        .all()
    )
    return render_template("admin/stock.html", medicines=rows, q="", view="low")


@admin_bp.route("/stock/out")
@login_required
@admin_required
def stock_out():
    rows = Medicine.query.filter(Medicine.quantity == 0).order_by(Medicine.name).all()
    return render_template("admin/stock.html", medicines=rows, q="", view="out")


@admin_bp.route("/stock/expired")
@login_required
@admin_required
def stock_expired():
    rows = (
        Medicine.query.filter(Medicine.expiry_date < date.today())
        .order_by(Medicine.expiry_date)
        .all()
    )
    return render_template("admin/stock.html", medicines=rows, q="", view="expired")


@admin_bp.route("/stock/add", methods=["POST"])
@login_required
@admin_required
def stock_add():
    mid = int(request.form.get("medicine_id"))
    add_qty = int(request.form.get("quantity") or 0)
    m = Medicine.query.get_or_404(mid)
    if add_qty <= 0:
        flash("Quantity must be positive.", "danger")
        return redirect(url_for("admin.stock_index"))
    m.quantity += add_qty
    db.session.commit()
    flash("Stock added.", "success")
    return redirect(url_for("admin.stock_index"))


@admin_bp.route("/stock/update", methods=["POST"])
@login_required
@admin_required
def stock_update():
    mid = int(request.form.get("medicine_id"))
    m = Medicine.query.get_or_404(mid)
    m.quantity = max(0, int(request.form.get("quantity") or 0))
    db.session.commit()
    flash("Stock quantity updated.", "success")
    return redirect(url_for("admin.stock_index"))


@admin_bp.route("/stock/remove-expired", methods=["POST"])
@login_required
@admin_required
def stock_remove_expired():
    ids = request.form.getlist("medicine_ids")
    removed = 0
    for i in ids:
        m = Medicine.query.get(int(i))
        if m and m.expiry_date < date.today():
            if m.bill_items.count():
                m.quantity = 0
            else:
                db.session.delete(m)
            removed += 1
    db.session.commit()
    flash(f"Processed {removed} expired line(s).", "success")
    return redirect(url_for("admin.stock_expired"))


# --- Purchases ---
@admin_bp.route("/purchases")
@login_required
@admin_required
def purchases():
    supplier_id = request.args.get("supplier_id", type=int)
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    page = request.args.get("page", 1, type=int) or 1
    query = Purchase.query
    if supplier_id:
        query = query.filter_by(supplier_id=supplier_id)
    if date_from:
        query = query.filter(Purchase.purchase_date >= datetime.strptime(date_from, "%Y-%m-%d").date())
    if date_to:
        query = query.filter(Purchase.purchase_date <= datetime.strptime(date_to, "%Y-%m-%d").date())
    query = query.order_by(Purchase.purchase_date.desc())
    pagination = query.paginate(page=page, per_page=15, error_out=False)
    return render_template(
        "admin/purchases_list.html",
        purchases=pagination.items,
        pagination=pagination,
        suppliers=Supplier.query.order_by(Supplier.name).all(),
        medicines=Medicine.query.order_by(Medicine.name).all(),
        supplier_id=supplier_id,
        date_from=date_from,
        date_to=date_to,
    )


@admin_bp.route("/purchases/new", methods=["GET", "POST"])
@login_required
@admin_required
def purchase_new():
    if request.method == "POST":
        try:
            sup_id = int(request.form.get("supplier_id"))
            mid = int(request.form.get("medicine_id"))
            qty = int(request.form.get("quantity") or 0)
            price = dec(request.form.get("purchase_price"))
            pdate = datetime.strptime(request.form.get("purchase_date"), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            flash("Invalid purchase data.", "danger")
            return redirect(url_for("admin.purchase_new"))
        if qty <= 0:
            flash("Quantity must be greater than zero.", "danger")
            return redirect(url_for("admin.purchase_new"))
        m = Medicine.query.get_or_404(mid)
        total = (price * qty).quantize(Decimal("0.01"))
        p = Purchase(
            supplier_id=sup_id,
            medicine_id=mid,
            medicine_name=m.name,
            batch_number=m.batch_number,
            quantity=qty,
            purchase_price=price,
            purchase_date=pdate,
            total_amount=total,
        )
        m.quantity += qty
        m.purchase_price = price
        db.session.add(p)
        db.session.commit()
        flash("Purchase recorded and stock increased.", "success")
        return redirect(url_for("admin.purchase_detail", pid=p.id))
    return render_template(
        "admin/purchase_form.html",
        purchase=None,
        suppliers=Supplier.query.order_by(Supplier.name).all(),
        medicines=Medicine.query.order_by(Medicine.name).all(),
    )


@admin_bp.route("/purchases/<int:pid>")
@login_required
@admin_required
def purchase_detail(pid):
    p = Purchase.query.get_or_404(pid)
    return render_template("admin/purchase_detail.html", purchase=p)


@admin_bp.route("/purchases/<int:pid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def purchase_edit(pid):
    p = Purchase.query.get_or_404(pid)
    m_old = Medicine.query.get_or_404(p.medicine_id)
    if request.method == "POST":
        try:
            old_qty = p.quantity
            new_qty = int(request.form.get("quantity") or 0)
            diff = new_qty - old_qty
            price = dec(request.form.get("purchase_price"))
            pdate = datetime.strptime(request.form.get("purchase_date"), "%Y-%m-%d").date()
            sup_id = int(request.form.get("supplier_id"))
        except (ValueError, TypeError):
            flash("Invalid data.", "danger")
            return redirect(url_for("admin.purchase_edit", pid=pid))
        if m_old.quantity + diff < 0:
            flash("Adjustment would make stock negative.", "danger")
            return redirect(url_for("admin.purchase_edit", pid=pid))
        m_old.quantity += diff
        p.supplier_id = sup_id
        p.quantity = new_qty
        p.purchase_price = price
        p.purchase_date = pdate
        p.total_amount = (price * new_qty).quantize(Decimal("0.01"))
        p.medicine_name = m_old.name
        p.batch_number = m_old.batch_number
        db.session.commit()
        flash("Purchase updated.", "success")
        return redirect(url_for("admin.purchase_detail", pid=p.id))
    return render_template(
        "admin/purchase_form.html",
        purchase=p,
        suppliers=Supplier.query.order_by(Supplier.name).all(),
        medicines=Medicine.query.order_by(Medicine.name).all(),
    )


@admin_bp.route("/purchases/<int:pid>/delete", methods=["POST"])
@login_required
@admin_required
def purchase_delete(pid):
    p = Purchase.query.get_or_404(pid)
    m = Medicine.query.get(p.medicine_id)
    if m:
        m.quantity = max(0, m.quantity - p.quantity)
    db.session.delete(p)
    db.session.commit()
    flash("Purchase removed; stock reduced accordingly.", "info")
    return redirect(url_for("admin.purchases"))


# --- Customers ---
@admin_bp.route("/customers")
@login_required
@admin_required
def customers():
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int) or 1
    query = Customer.query
    if q:
        query = query.filter(
            or_(
                Customer.name.ilike(f"%{q}%"),
                Customer.email.ilike(f"%{q}%"),
                Customer.contact_number.ilike(f"%{q}%"),
            )
        )
    query = query.order_by(Customer.name)
    pagination = query.paginate(page=page, per_page=12, error_out=False)
    return render_template(
        "admin/customers_list.html",
        customers=pagination.items,
        pagination=pagination,
        q=q,
    )


@admin_bp.route("/customers/new", methods=["GET", "POST"])
@login_required
@admin_required
def customer_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Customer name is required.", "danger")
            return redirect(url_for("admin.customer_new"))
        c = Customer(
            name=name,
            contact_number=request.form.get("contact_number") or "",
            email=request.form.get("email") or "",
            address=request.form.get("address") or "",
        )
        db.session.add(c)
        db.session.commit()
        flash("Customer created.", "success")
        return redirect(url_for("admin.customer_detail", cid=c.id))
    return render_template("admin/customer_form.html", customer=None)


@admin_bp.route("/customers/<int:cid>")
@login_required
@admin_required
def customer_detail(cid):
    c = Customer.query.get_or_404(cid)
    bills = c.bills.order_by(Bill.created_at.desc()).limit(40).all()
    total_spend = (
        db.session.query(func.coalesce(func.sum(Bill.grand_total), 0))
        .filter(Bill.customer_id == c.id)
        .scalar()
        or 0
    )
    return render_template(
        "admin/customer_detail.html",
        customer=c,
        bills=bills,
        bill_count=c.bills.count(),
        total_spend=total_spend,
    )


@admin_bp.route("/customers/<int:cid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def customer_edit(cid):
    c = Customer.query.get_or_404(cid)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Name is required.", "danger")
            return redirect(url_for("admin.customer_edit", cid=cid))
        c.name = name
        c.contact_number = request.form.get("contact_number") or ""
        c.email = request.form.get("email") or ""
        c.address = request.form.get("address") or ""
        db.session.commit()
        flash("Customer updated.", "success")
        return redirect(url_for("admin.customer_detail", cid=c.id))
    return render_template("admin/customer_form.html", customer=c)


@admin_bp.route("/customers/<int:cid>/delete", methods=["POST"])
@login_required
@admin_required
def customer_delete(cid):
    c = Customer.query.get_or_404(cid)
    if c.bills.count():
        flash("Cannot delete: customer has billing history.", "danger")
        return redirect(url_for("admin.customer_detail", cid=cid))
    db.session.delete(c)
    db.session.commit()
    flash("Customer removed.", "info")
    return redirect(url_for("admin.customers"))


def _build_bill_from_form():
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


@admin_bp.route("/billing")
@login_required
@admin_required
def billing_list():
    q_bill = (request.args.get("bill") or "").strip()
    page = request.args.get("page", 1, type=int) or 1
    qry = Bill.query
    if q_bill:
        qry = qry.filter(Bill.bill_number.ilike(f"%{q_bill}%"))
    qry = qry.order_by(Bill.created_at.desc())
    pagination = qry.paginate(page=page, per_page=15, error_out=False)
    return render_template(
        "admin/billing_list.html",
        bills=pagination.items,
        pagination=pagination,
        q_bill=q_bill,
    )


@admin_bp.route("/billing/new", methods=["GET", "POST"])
@login_required
@admin_required
def billing_new():
    if request.method == "POST":
        data, err = _build_bill_from_form()
        if err:
            flash(err, "danger")
            return redirect(url_for("admin.billing_new"))
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
        flash("Bill saved.", "success")
        return redirect(url_for("admin.bill_print", bid=bill.id))
    return render_template(
        "admin/billing_form.html",
        customers=Customer.query.order_by(Customer.name).all(),
        medicines=Medicine.query.filter(Medicine.quantity > 0).order_by(Medicine.name).all(),
    )


@admin_bp.route("/billing/<int:bid>")
@login_required
@admin_required
def bill_detail(bid):
    bill = Bill.query.get_or_404(bid)
    return render_template("admin/bill_detail.html", bill=bill)


@admin_bp.route("/billing/<int:bid>/print")
@login_required
@admin_required
def bill_print(bid):
    bill = Bill.query.get_or_404(bid)
    return render_template("admin/bill_print.html", bill=bill)


# --- Sales ---
@admin_bp.route("/sales")
@login_required
@admin_required
def sales():
    bill_q = (request.args.get("bill") or "").strip()
    cust_q = (request.args.get("customer") or "").strip()
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    qry = Bill.query
    if bill_q:
        qry = qry.filter(Bill.bill_number.ilike(f"%{bill_q}%"))
    if cust_q:
        qry = qry.join(Customer).filter(Customer.name.ilike(f"%{cust_q}%"))
    if date_from:
        qry = qry.filter(Bill.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
    if date_to:
        end_d = datetime.strptime(date_to, "%Y-%m-%d").date() + timedelta(days=1)
        qry = qry.filter(Bill.created_at < datetime.combine(end_d, datetime.min.time()))
    bills = qry.order_by(Bill.created_at.desc()).limit(500).all()
    return render_template(
        "admin/sales.html",
        bills=bills,
        bill_q=bill_q,
        cust_q=cust_q,
        date_from=date_from,
        date_to=date_to,
        mode="list",
    )


@admin_bp.route("/sales/medicine-wise")
@login_required
@admin_required
def sales_medicine_wise():
    rows = (
        db.session.query(
            Medicine.name,
            func.sum(BillItem.quantity).label("qty"),
            func.sum(BillItem.line_total).label("amt"),
        )
        .join(BillItem, BillItem.medicine_id == Medicine.id)
        .group_by(Medicine.id)
        .order_by(func.sum(BillItem.quantity).desc())
        .all()
    )
    return render_template("admin/sales_medicine.html", rows=rows)


@admin_bp.route("/sales/daily")
@login_required
@admin_required
def sales_daily():
    day = request.args.get("day") or date.today().isoformat()
    d = datetime.strptime(day, "%Y-%m-%d").date()
    start = datetime.combine(d, datetime.min.time())
    end = datetime.combine(d, datetime.max.time())
    rows = (
        db.session.query(func.coalesce(func.sum(Bill.grand_total), 0))
        .filter(Bill.created_at >= start, Bill.created_at <= end)
        .scalar()
    )
    bills = Bill.query.filter(Bill.created_at >= start, Bill.created_at <= end).all()
    return render_template("admin/sales_daily.html", total=rows or 0, bills=bills, day=day)


@admin_bp.route("/sales/monthly")
@login_required
@admin_required
def sales_monthly():
    y = request.args.get("year", type=int) or date.today().year
    m = request.args.get("month", type=int) or date.today().month
    _, last = monthrange(y, m)
    start = date(y, m, 1)
    end = date(y, m, last)
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    total = (
        db.session.query(func.coalesce(func.sum(Bill.grand_total), 0))
        .filter(Bill.created_at >= start_dt, Bill.created_at <= end_dt)
        .scalar()
    )
    bills = Bill.query.filter(Bill.created_at >= start_dt, Bill.created_at <= end_dt).all()
    return render_template(
        "admin/sales_monthly.html", total=total or 0, bills=bills, year=y, month=m
    )


# --- Returns ---
@admin_bp.route("/returns")
@login_required
@admin_required
def returns_list():
    q_bill = (request.args.get("bill") or "").strip()
    qry = MedicineReturn.query
    if q_bill:
        qry = qry.join(Bill).filter(Bill.bill_number.ilike(f"%{q_bill}%"))
    rows = qry.order_by(MedicineReturn.return_date.desc()).all()
    return render_template("admin/returns.html", returns=rows, q_bill=q_bill)


@admin_bp.route("/returns/new", methods=["GET", "POST"])
@login_required
@admin_required
def returns_new():
    if request.method == "POST":
        try:
            bid = int(request.form.get("bill_id"))
            mid = int(request.form.get("medicine_id"))
            qty = int(request.form.get("quantity") or 0)
        except (ValueError, TypeError):
            flash("Invalid return.", "danger")
            return redirect(url_for("admin.returns_new"))
        bill = Bill.query.get_or_404(bid)
        item = BillItem.query.filter_by(bill_id=bid, medicine_id=mid).first()
        if not item or qty <= 0 or qty > item.quantity:
            flash("Invalid quantity for this bill line.", "danger")
            return redirect(url_for("admin.returns_new"))
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
        flash(
            f"Return recorded. Refund: {refund}. Stock has been updated.",
            "success",
        )
        return redirect(url_for("admin.returns_list"))
    bills = Bill.query.order_by(Bill.created_at.desc()).limit(100).all()
    return render_template("admin/returns_form.html", bills=bills)


# --- Expiry ---
@admin_bp.route("/expiry")
@login_required
@admin_required
def expiry_index():
    expired = (
        Medicine.query.filter(Medicine.expiry_date < date.today())
        .order_by(Medicine.expiry_date)
        .all()
    )
    soon_days = int(request.args.get("soon", 90))
    soon_date = date.today() + timedelta(days=soon_days)
    soon = (
        Medicine.query.filter(
            Medicine.expiry_date >= date.today(),
            Medicine.expiry_date <= soon_date,
        )
        .order_by(Medicine.expiry_date)
        .all()
    )
    search_date = request.args.get("on")
    searched = []
    if search_date:
        try:
            d = datetime.strptime(search_date, "%Y-%m-%d").date()
            searched = Medicine.query.filter(Medicine.expiry_date == d).all()
        except ValueError:
            pass
    return render_template(
        "admin/expiry.html",
        expired=expired,
        soon=soon,
        searched=searched,
        search_date=search_date,
        soon_days=soon_days,
    )


# --- Reports ---
@admin_bp.route("/reports/<string:name>")
@login_required
@admin_required
def reports(name):
    today = date.today()
    if name == "stock":
        rows = Medicine.query.order_by(Medicine.name).all()
        return render_template("admin/report_stock.html", rows=rows)
    if name == "low":
        rows = (
            Medicine.query.filter(Medicine.quantity <= Medicine.min_stock_level)
            .order_by(Medicine.quantity)
            .all()
        )
        return render_template("admin/report_low.html", rows=rows)
    if name == "expired":
        rows = Medicine.query.filter(Medicine.expiry_date < today).order_by(
            Medicine.expiry_date
        ).all()
        return render_template("admin/report_expired.html", rows=rows)
    if name == "purchase":
        rows = Purchase.query.order_by(Purchase.purchase_date.desc()).limit(500).all()
        return render_template("admin/report_purchase.html", rows=rows)
    if name == "sales":
        rows = Bill.query.order_by(Bill.created_at.desc()).limit(500).all()
        return render_template("admin/report_sales.html", rows=rows)
    if name == "customers":
        rows = Customer.query.order_by(Customer.name).all()
        return render_template("admin/report_customers.html", rows=rows)
    if name == "suppliers":
        rows = Supplier.query.order_by(Supplier.name).all()
        return render_template("admin/report_suppliers.html", rows=rows)
    if name == "profit":
        profit_expr = func.sum(
            (BillItem.unit_price - BillItem.unit_cost) * BillItem.quantity
        )
        total = db.session.query(profit_expr).scalar() or 0
        lines = (
            db.session.query(
                Medicine.name,
                func.sum(
                    (BillItem.unit_price - BillItem.unit_cost) * BillItem.quantity
                ).label("p"),
            )
            .select_from(Medicine)
            .join(BillItem, BillItem.medicine_id == Medicine.id)
            .group_by(Medicine.id)
            .order_by(
                func.sum(
                    (BillItem.unit_price - BillItem.unit_cost) * BillItem.quantity
                ).desc()
            )
            .limit(100)
            .all()
        )
        return render_template(
            "admin/report_profit.html", total=total, lines=lines
        )
    if name == "billing-daily":
        day = request.args.get("day") or today.isoformat()
        d = datetime.strptime(day, "%Y-%m-%d").date()
        start = datetime.combine(d, datetime.min.time())
        end = datetime.combine(d, datetime.max.time())
        rows = Bill.query.filter(Bill.created_at >= start, Bill.created_at <= end).all()
        return render_template(
            "admin/report_billing_daily.html", rows=rows, day=day
        )
    if name == "billing-monthly":
        y = request.args.get("year", type=int) or today.year
        m = request.args.get("month", type=int) or today.month
        _, last = monthrange(y, m)
        start = datetime.combine(date(y, m, 1), datetime.min.time())
        end = datetime.combine(date(y, m, last), datetime.max.time())
        rows = Bill.query.filter(Bill.created_at >= start, Bill.created_at <= end).all()
        return render_template(
            "admin/report_billing_monthly.html", rows=rows, year=y, month=m
        )
    flash("Unknown report.", "warning")
    return redirect(url_for("admin.dashboard"))


# --- Analytics ---
@admin_bp.route("/analytics")
@login_required
@admin_required
def analytics():
    revenue = db.session.query(func.coalesce(func.sum(Bill.grand_total), 0)).scalar() or 0
    profit = (
        db.session.query(
            func.coalesce(
                func.sum((BillItem.unit_price - BillItem.unit_cost) * BillItem.quantity),
                0,
            )
        ).scalar()
        or 0
    )

    best = (
        db.session.query(
            Medicine.name,
            func.sum(BillItem.quantity).label("qty"),
        )
        .join(BillItem, BillItem.medicine_id == Medicine.id)
        .group_by(Medicine.id)
        .order_by(func.sum(BillItem.quantity).desc())
        .limit(8)
        .all()
    )
    low_sell = (
        db.session.query(
            Medicine.name,
            func.coalesce(func.sum(BillItem.quantity), 0).label("qty"),
        )
        .outerjoin(BillItem, BillItem.medicine_id == Medicine.id)
        .group_by(Medicine.id)
        .order_by(func.coalesce(func.sum(BillItem.quantity), 0))
        .limit(8)
        .all()
    )

    cat_sales = (
        db.session.query(
            Category.name,
            func.coalesce(func.sum(BillItem.line_total), 0).label("amt"),
        )
        .join(Medicine, Medicine.category_id == Category.id)
        .join(BillItem, BillItem.medicine_id == Medicine.id)
        .group_by(Category.id)
        .all()
    )
    brand_sales = (
        db.session.query(
            Brand.name,
            func.coalesce(func.sum(BillItem.line_total), 0).label("amt"),
        )
        .join(Medicine, Medicine.brand_id == Brand.id)
        .join(BillItem, BillItem.medicine_id == Medicine.id)
        .group_by(Brand.id)
        .all()
    )

    monthly = (
        db.session.query(
            extract("year", Bill.created_at).label("y"),
            extract("month", Bill.created_at).label("m"),
            func.coalesce(func.sum(Bill.grand_total), 0).label("amt"),
        )
        .group_by(
            extract("year", Bill.created_at),
            extract("month", Bill.created_at),
        )
        .order_by(
            extract("year", Bill.created_at),
            extract("month", Bill.created_at),
        )
        .limit(24)
        .all()
    )

    daily = (
        db.session.query(
            func.date(Bill.created_at).label("d"),
            func.coalesce(func.sum(Bill.grand_total), 0).label("amt"),
        )
        .filter(Bill.created_at >= datetime.utcnow() - timedelta(days=14))
        .group_by(func.date(Bill.created_at))
        .order_by(func.date(Bill.created_at))
        .all()
    )

    stock_value = (
        db.session.query(func.coalesce(func.sum(Medicine.quantity * Medicine.purchase_price), 0)).scalar()
        or 0
    )
    expiry_loss = (
        db.session.query(
            func.coalesce(
                func.sum(Medicine.quantity * Medicine.purchase_price),
                0,
            )
        )
        .filter(Medicine.expiry_date < date.today(), Medicine.quantity > 0)
        .scalar()
        or 0
    )

    chart = {
        "monthly_labels": [f"{int(r.y)}-{int(r.m):02d}" for r in monthly],
        "monthly_data": [float(r.amt or 0) for r in monthly],
        "daily_labels": [r.d.isoformat() if hasattr(r.d, "isoformat") else str(r.d) for r in daily],
        "daily_data": [float(r.amt or 0) for r in daily],
        "cat_labels": [r.name for r in cat_sales],
        "cat_data": [float(r.amt or 0) for r in cat_sales],
        "brand_labels": [r.name for r in brand_sales],
        "brand_data": [float(r.amt or 0) for r in brand_sales],
    }

    return render_template(
        "admin/analytics.html",
        revenue=revenue,
        profit=profit,
        best=best,
        low_sell=low_sell,
        cat_sales=cat_sales,
        brand_sales=brand_sales,
        stock_value=stock_value,
        expiry_loss=expiry_loss,
        chart=chart,
    )


# --- Staff ---
@admin_bp.route("/staff-users")
@login_required
@admin_required
def staff_users():
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int) or 1
    query = User.query.filter(User.role == "staff")
    if q:
        query = query.filter(
            or_(
                User.username.ilike(f"%{q}%"),
                User.full_name.ilike(f"%{q}%"),
                User.email.ilike(f"%{q}%"),
            )
        )
    query = query.order_by(User.username)
    pagination = query.paginate(page=page, per_page=12, error_out=False)
    return render_template(
        "admin/staff_list.html",
        staff_rows=pagination.items,
        pagination=pagination,
        q=q,
    )


@admin_bp.route("/staff-users/new", methods=["GET", "POST"])
@login_required
@admin_required
def staff_new():
    if request.method == "POST":
        un = (request.form.get("username") or "").strip()
        pw = request.form.get("password") or ""
        if not un or not pw:
            flash("Username and password are required.", "danger")
            return redirect(url_for("admin.staff_new"))
        if User.query.filter_by(username=un).first():
            flash("This username is already taken.", "danger")
            return redirect(url_for("admin.staff_new"))
        u = User(
            username=un,
            full_name=(request.form.get("full_name") or un).strip(),
            email=request.form.get("email") or "",
            phone=request.form.get("phone") or "",
            role="staff",
            is_active=True,
        )
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        flash("Staff account created.", "success")
        return redirect(url_for("admin.staff_user_detail", uid=u.id))
    return render_template("admin/staff_form.html", user=None)


@admin_bp.route("/staff-users/<int:uid>")
@login_required
@admin_required
def staff_user_detail(uid):
    u = User.query.get_or_404(uid)
    if u.role != "staff":
        flash("Invalid staff record.", "danger")
        return redirect(url_for("admin.staff_users"))
    bills = u.bills.order_by(Bill.created_at.desc()).limit(25).all()
    bill_total = (
        db.session.query(func.coalesce(func.sum(Bill.grand_total), 0))
        .filter(Bill.staff_id == u.id)
        .scalar()
        or 0
    )
    return_count = u.returns.count()
    return render_template(
        "admin/staff_detail.html",
        user=u,
        bills=bills,
        bill_count=u.bills.count(),
        bill_total=bill_total,
        return_count=return_count,
    )


@admin_bp.route("/staff-users/<int:uid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def staff_user_edit(uid):
    u = User.query.get_or_404(uid)
    if u.role != "staff":
        flash("Not a staff user.", "danger")
        return redirect(url_for("admin.staff_users"))
    if request.method == "POST":
        u.full_name = (request.form.get("full_name") or "").strip() or u.full_name
        u.email = request.form.get("email") or ""
        u.phone = request.form.get("phone") or ""
        new_pw = request.form.get("new_password") or ""
        if new_pw:
            if len(new_pw) < 6:
                flash("Password must be at least 6 characters.", "danger")
                return redirect(url_for("admin.staff_user_edit", uid=uid))
            u.set_password(new_pw)
        db.session.commit()
        flash("Staff profile updated.", "success")
        return redirect(url_for("admin.staff_user_detail", uid=u.id))
    return render_template("admin/staff_form.html", user=u)


@admin_bp.route("/staff-users/<int:uid>/toggle", methods=["POST"])
@login_required
@admin_required
def staff_toggle(uid):
    u = User.query.get_or_404(uid)
    if u.role != "staff":
        flash("Invalid.", "danger")
        return redirect(url_for("admin.staff_users"))
    u.is_active = not u.is_active
    db.session.commit()
    flash("Access status updated.", "success")
    return redirect(url_for("admin.staff_user_detail", uid=u.id))


@admin_bp.route("/staff-users/<int:uid>/delete", methods=["POST"])
@login_required
@admin_required
def staff_delete(uid):
    u = User.query.get_or_404(uid)
    if u.role != "staff":
        flash("Invalid.", "danger")
        return redirect(url_for("admin.staff_users"))
    if u.bills.count():
        flash("Cannot delete: deactivate the account instead (sales history exists).", "warning")
        return redirect(url_for("admin.staff_user_detail", uid=u.id))
    db.session.delete(u)
    db.session.commit()
    flash("Staff user removed.", "info")
    return redirect(url_for("admin.staff_users"))


@admin_bp.route("/api/bill/<int:bid>/lines")
@login_required
@admin_required
def api_bill_lines(bid):
    Bill.query.get_or_404(bid)
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


@admin_bp.route("/password", methods=["GET", "POST"])
@login_required
@admin_required
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
            return redirect(url_for("admin.dashboard"))
    return render_template("admin/change_password.html")

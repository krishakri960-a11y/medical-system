from datetime import date, datetime
from decimal import Decimal

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(32))
    role = db.Column(db.String(20), nullable=False, default="staff")  # admin | staff
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bills = db.relationship("Bill", backref="staff", lazy="dynamic")
    returns = db.relationship("MedicineReturn", backref="staff", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Brand(db.Model):
    __tablename__ = "brands"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)

    medicines = db.relationship("Medicine", backref="brand", lazy="dynamic")


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)

    medicines = db.relationship("Medicine", backref="category", lazy="dynamic")


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    contact_number = db.Column(db.String(32))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    company_name = db.Column(db.String(160))

    medicines = db.relationship("Medicine", backref="supplier", lazy="dynamic")
    purchases = db.relationship("Purchase", backref="supplier", lazy="dynamic")


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    contact_number = db.Column(db.String(32))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bills = db.relationship("Bill", backref="customer", lazy="dynamic")


class Medicine(db.Model):
    __tablename__ = "medicines"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    batch_number = db.Column(db.String(80), nullable=False, index=True)
    manufacturing_date = db.Column(db.Date, nullable=False)
    expiry_date = db.Column(db.Date, nullable=False, index=True)
    purchase_price = db.Column(db.Numeric(12, 2), nullable=False)
    selling_price = db.Column(db.Numeric(12, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    min_stock_level = db.Column(db.Integer, nullable=False, default=10)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bill_items = db.relationship("BillItem", backref="medicine", lazy="dynamic")
    purchase_lines = db.relationship("Purchase", backref="medicine", lazy="dynamic")


class Purchase(db.Model):
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=True)
    medicine_name = db.Column(db.String(160))
    batch_number = db.Column(db.String(80))
    quantity = db.Column(db.Integer, nullable=False)
    purchase_price = db.Column(db.Numeric(12, 2), nullable=False)
    purchase_date = db.Column(db.Date, nullable=False, index=True)
    total_amount = db.Column(db.Numeric(14, 2), nullable=False)


class Bill(db.Model):
    __tablename__ = "bills"

    id = db.Column(db.Integer, primary_key=True)
    bill_number = db.Column(db.String(40), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    discount_percent = db.Column(db.Numeric(5, 2), default=Decimal("0"))
    tax_percent = db.Column(db.Numeric(5, 2), default=Decimal("0"))
    subtotal = db.Column(db.Numeric(14, 2), default=Decimal("0"))
    discount_amount = db.Column(db.Numeric(14, 2), default=Decimal("0"))
    tax_amount = db.Column(db.Numeric(14, 2), default=Decimal("0"))
    grand_total = db.Column(db.Numeric(14, 2), default=Decimal("0"))
    notes = db.Column(db.Text)

    items = db.relationship("BillItem", backref="bill", lazy="dynamic", cascade="all, delete-orphan")
    returns = db.relationship("MedicineReturn", backref="bill", lazy="dynamic")


class BillItem(db.Model):
    __tablename__ = "bill_items"

    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey("bills.id"), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False)
    line_total = db.Column(db.Numeric(14, 2), nullable=False)


class MedicineReturn(db.Model):
    __tablename__ = "medicine_returns"

    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey("bills.id"), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    refund_amount = db.Column(db.Numeric(14, 2), nullable=False)
    return_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reason = db.Column(db.Text)

    medicine = db.relationship("Medicine")


def today_bounds():
    start = datetime.combine(date.today(), datetime.min.time())
    end = datetime.combine(date.today(), datetime.max.time())
    return start, end

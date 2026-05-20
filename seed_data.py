"""
Load demonstration data (~8 records per master table) after the schema exists.
Run from project root:  python seed_data.py
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from app import create_app, db
from app.models import (
    Bill,
    BillItem,
    Brand,
    Category,
    Customer,
    Medicine,
    Purchase,
    Supplier,
    User,
)
from app.utils import next_bill_number


def main():
    app = create_app()
    with app.app_context():
        if Brand.query.count() >= 4:
            print("Database already contains seed-like data; skipping.")
            print("Delete medical_inventory.db in the project folder to re-seed.")
            return

        brands = [
            Brand(name=n, description="Demo brand")
            for n in [
                "Cipla",
                "Sun Pharma",
                "Dr. Reddy's",
                "Mankind",
                "Abbott",
                "GlaxoSmithKline",
                "Pfizer",
                "Novartis",
            ]
        ]
        for b in brands:
            db.session.add(b)
        db.session.flush()

        categories = [
            Category(name=n, description="Demo category")
            for n in [
                "Analgesics",
                "Antibiotics",
                "Antiseptics",
                "Vitamins",
                "Cardiac",
                "Respiratory",
                "Diabetes",
                "Gastro",
            ]
        ]
        for c in categories:
            db.session.add(c)
        db.session.flush()

        suppliers = []
        for i in range(8):
            suppliers.append(
                Supplier(
                    name=f"Supplier {i + 1}",
                    contact_number=f"980000000{i}",
                    email=f"sup{i + 1}@demo.med",
                    address=f"{100 + i} Trade Center Rd",
                    company_name=f"MediTrade Co {i + 1}",
                )
            )
        for s in suppliers:
            db.session.add(s)
        db.session.flush()

        customers = []
        for i in range(8):
            customers.append(
                Customer(
                    name=f"Customer {chr(65 + i)}",
                    contact_number=f"990000000{i}",
                    email=f"cust{i + 1}@demo.med",
                    address=f"{i + 1} Park Avenue",
                )
            )
        for c in customers:
            db.session.add(c)
        db.session.flush()

        staff1 = User(
            username="staff1",
            full_name="Riya Sharma",
            email="riya@demo.med",
            phone="9100000001",
            role="staff",
            is_active=True,
        )
        staff1.set_password("staff123")
        staff2 = User(
            username="staff2",
            full_name="Amit Verma",
            email="amit@demo.med",
            phone="9100000002",
            role="staff",
            is_active=True,
        )
        staff2.set_password("staff123")
        db.session.add_all([staff1, staff2])
        db.session.flush()

        today = date.today()
        med_specs = [
            ("Paracetamol 500mg", 0, 0, 12.5, 25, 400, 50, today + timedelta(days=400)),
            ("Amoxicillin 250mg", 1, 1, 45, 85, 120, 40, today + timedelta(days=120)),
            ("Cetirizine 10mg", 2, 2, 8, 18, 200, 60, today - timedelta(days=10)),
            ("Vitamin D3 60k", 3, 3, 120, 220, 80, 25, today + timedelta(days=60)),
            ("Atorvastatin 10mg", 4, 4, 55, 95, 150, 35, today + timedelta(days=200)),
            ("Salbutamol Inhaler", 5, 5, 180, 260, 45, 15, today + timedelta(days=300)),
            ("Metformin 500mg", 6, 6, 20, 38, 300, 80, today + timedelta(days=500)),
            ("Omeprazole 20mg", 7, 7, 15, 28, 250, 70, today + timedelta(days=30)),
        ]

        medicines = []
        for idx, (name, bi, ci, pprice, sprice, qty, minq, exp) in enumerate(med_specs):
            medicines.append(
                Medicine(
                    name=name,
                    brand_id=brands[bi].id,
                    category_id=categories[ci].id,
                    supplier_id=suppliers[idx].id,
                    batch_number=f"B{2026}{idx:02d}",
                    manufacturing_date=today - timedelta(days=60),
                    expiry_date=exp,
                    purchase_price=Decimal(str(pprice)),
                    selling_price=Decimal(str(sprice)),
                    quantity=qty,
                    min_stock_level=minq,
                    description="Seeded batch line for analytics and UI demos.",
                )
            )
        for m in medicines:
            db.session.add(m)
        db.session.flush()

        for i, m in enumerate(medicines[:6]):
            db.session.add(
                Purchase(
                    supplier_id=m.supplier_id,
                    medicine_id=m.id,
                    medicine_name=m.name,
                    batch_number=m.batch_number,
                    quantity=50 + i * 5,
                    purchase_price=m.purchase_price,
                    purchase_date=today - timedelta(days=7 + i),
                    total_amount=(m.purchase_price * (50 + i * 5)).quantize(Decimal("0.01")),
                )
            )

        admin = User.query.filter_by(username="admin").first()

        def create_bill(customer, staff, lines, discount=Decimal("0"), tax=Decimal("5"), days_ago=0):
            sub = Decimal("0")
            bill_items_data = []
            for med, q in lines:
                line_total = (med.selling_price * q).quantize(Decimal("0.01"))
                sub += line_total
                bill_items_data.append((med, q, line_total))
            disc_amt = (sub * discount / Decimal("100")).quantize(Decimal("0.01"))
            after = sub - disc_amt
            tax_amt = (after * tax / Decimal("100")).quantize(Decimal("0.01"))
            grand = (after + tax_amt).quantize(Decimal("0.01"))
            bill = Bill(
                bill_number=next_bill_number(),
                customer_id=customer.id,
                staff_id=staff.id,
                discount_percent=discount,
                tax_percent=tax,
                subtotal=sub,
                discount_amount=disc_amt,
                tax_amount=tax_amt,
                grand_total=grand,
                notes="Seeded bill",
                created_at=datetime.utcnow() - timedelta(days=days_ago),
            )
            db.session.add(bill)
            db.session.flush()
            for med, q, lt in bill_items_data:
                db.session.add(
                    BillItem(
                        bill_id=bill.id,
                        medicine_id=med.id,
                        quantity=q,
                        unit_price=med.selling_price,
                        unit_cost=med.purchase_price,
                        line_total=lt,
                    )
                )
                med.quantity = max(0, int(med.quantity) - q)

        create_bill(customers[0], staff1, [(medicines[0], 20), (medicines[1], 10)], days_ago=1)
        create_bill(customers[1], staff1, [(medicines[2], 5), (medicines[4], 15)], days_ago=2)
        create_bill(customers[2], staff2, [(medicines[5], 8), (medicines[6], 40), (medicines[7], 12)], days_ago=3)
        if admin:
            create_bill(customers[3], admin, [(medicines[0], 30), (medicines[3], 6)], discount=Decimal("5"), days_ago=4)

        db.session.commit()
        print("Seed complete.")
        print("  admin / admin123")
        print("  staff1 / staff123   staff2 / staff123")


if __name__ == "__main__":
    main()

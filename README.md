# MedInventory Pro — Medical Inventory & Billing System with Analytics

A Flask web application for **pharmacy-style inventory**, **customer billing**, **staff desk operations**, and **admin analytics**. It supports role-based access (administrator vs. staff), SQLite persistence, printable bills, stock and expiry tracking, purchase entries, returns, and reporting dashboards.

---

## Technology stack

| Layer | Technology |
|--------|------------|
| **Runtime** | Python 3 |
| **Web framework** | [Flask](https://flask.palletsprojects.com/) 3.0.3 |
| **ORM / database** | [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/) 3.1.1 · **SQLite** (`medical_inventory.db`) |
| **Authentication** | [Flask-Login](https://flask-login.readthedocs.io/) 0.6.3 (session-based) |
| **Security (passwords)** | Werkzeug password hashing |
| **Frontend** | HTML5, [Bootstrap](https://getbootstrap.com/) 5.3.3 (CDN), [Bootstrap Icons](https://icons.getbootstrap.com/) |
| **Charts (analytics)** | [Chart.js](https://www.chartjs.org/) 4.4.2 (CDN) |
| **Utilities** | `python-dateutil` |

Static styling lives in `app/static/css/app.css`. Templates use Jinja2 (`app/templates/`).

---

## Features (high level)

- **Public / auth**: Landing page, login, logout; redirect by role (admin → `/admin`, staff → `/staff`).
- **Master data**: Brands, categories, suppliers, medicines (batch, prices, stock, expiry), customers.
- **Inventory**: Stock overview, low/out/expired views, manual stock adjustments, purchase orders.
- **Sales**: Bills with line items, discount & tax, auto bill numbers, print-friendly receipts.
- **Returns**: Return lines against bills; restock medicines and record refund amounts (staff: own bills only).
- **Analytics & reports**: KPIs, charts (daily/monthly revenue, category/brand mix), best sellers, printable/HTML reports.
- **User management (admin)**: Create and manage staff accounts (activate/deactivate, edit, optional delete).

---

## Project structure (overview)

```
Medical Inventory & Billing System with Analytics/
├── run.py                 # App entry: runs Flask on 0.0.0.0:5000 (debug)
├── requirements.txt
├── seed_data.py           # Optional demo data loader
├── medical_inventory.db   # SQLite DB (created on first run)
└── app/
    ├── __init__.py        # App factory, DB URI, login, context globals
    ├── models.py          # SQLAlchemy models (User, Medicine, Bill, …)
    ├── main_routes.py     # /, /login, /logout
    ├── admin_routes.py    # /admin/*
    ├── staff_routes.py    # /staff/*
    ├── utils.py           # Role guards, pagination helpers, bill number helper
    ├── static/css/
    └── templates/
        ├── base.html, landing.html, login.html
        ├── admin/         # Admin UI templates
        └── staff/         # Staff desk UI templates
```

---

## Modules & functionality

### 1. Public site (`main` blueprint)

| Path | Purpose |
|------|---------|
| `/` | **Landing**: marketing-style home. Logged-in users redirect to the correct dashboard. |
| `/login` | **Sign-in**: username + password; supports optional `?next=` redirect. |
| `/logout` | Ends session (requires login). |

### 2. Administrator panel (`/admin`)

Requires user with **`role = admin`**. Sidebar groups: overview, master data, inventory & buying, sales, insights, system.

| Area | Routes / behavior |
|------|-------------------|
| **Dashboard** | KPIs, shortcuts, recent activity-style summaries. |
| **Brands** | List (paginated), **create**, **detail**, **edit**, **delete**. |
| **Categories** | Same CRUD pattern as brands. |
| **Suppliers** | Same CRUD; contact and company fields. |
| **Medicines** | Full **CRUD**: brand/category/supplier links, batch, MFG/expiry dates, purchase/sell price, quantity, min stock, description; **detail** shows related usage. |
| **Customers** | **CRUD** including **delete**; detail with bill history. |
| **Stock** | Consolidated stock index; **low**, **out**, **expired** views; actions to **add stock**, **update** levels, **remove expired** (business rules in routes). |
| **Purchases** | Purchase records (supplier, medicine, qty, price, date); **list**, **new**, **detail**, **edit**, **delete**. |
| **Expiry** | Dedicated expiry-focused listing and tooling. |
| **Billing** | **List** all bills; **create** bill (lines, discount %, tax %); **bill detail**; **print** view. |
| **Sales** | Aggregate overview plus **medicine-wise**, **daily**, and **monthly** breakdowns. |
| **Returns** | **List** return records; **new** return (admin can target bills as implemented in routes). |
| **Reports** | Dynamic reports under `/admin/reports/<name>`: e.g. `stock`, `low`, `expired`, `purchase`, `sales`, `customers`, `suppliers`, `profit`, `billing-daily`, `billing-monthly`. |
| **Analytics** | Dashboard with revenue, estimated profit, stock value, expiry loss; Chart.js for trends and category/brand visuals; best sellers / low rotation lists. |
| **Staff users** | List desk users; **create** staff; **detail**; **edit**; **toggle active**; **delete** (where allowed). |
| **Password** | Admin changes own password. |
| **API (internal)** | e.g. `/admin/api/bill/<id>/lines` JSON for return/billing helpers. |

### 3. Staff desk panel (`/staff`)

Requires user with **`role = staff`**. Optimized for daily counter work: **read-only catalogue**, **own sales**, **own returns**, customer management without master-delete of medicines.

| Path | Functionality |
|------|----------------|
| `/staff/dashboard` | Personal KPIs (SKUs available, today’s bill count & revenue), **recent bills** (yours), **low stock** watch with links to medicine detail; quick actions. |
| `/staff/medicines` | **Paginated** medicine catalogue with search + brand/category filters; **read-only**. |
| `/staff/medicines/<id>` | **Medicine detail** (full SKU card: supplier, prices, batch, expiry, stock, notes). |
| `/staff/customers` | **Paginated** customer directory with search. |
| `/staff/customers/new` | **Create** customer (GET form + POST). |
| `/staff/customers/<id>` | **Customer profile**: contact info, **bills you issued** only, **your** revenue with that customer; links to billing and bill views. |
| `/staff/customers/<id>/edit` | **Edit** customer (GET + POST). |
| `/staff/billing` | **POS-style billing**: customer, multi-line medicines (in-stock only), discount % & tax %, notes; saves bill, decrements stock; redirects to **bill detail**. |
| `/staff/billing/<id>` | **Bill detail** (own bills only): line items, totals, notes; links to print and customer. |
| `/staff/billing/<id>/print` | **Printable receipt**. |
| `/staff/sales` | **Paginated** history of **your** bills; filters by bill #, customer name, date range; links to detail/print. |
| `/staff/stock` | Stock views: **all** (optional **search** by name/batch), **low**, **expired**, **expiring within 60 days**; links to medicine detail. |
| `/staff/returns` | **Paginated return log** (y yours); optional filter by bill number. |
| `/staff/returns/new` | **New return**: pick **your** bill → line from API → quantity + reason; restocks SKU and stores refund. |
| `/staff/api/bill/<id>/lines` | JSON line list for return form (forbidden if not your bill). |
| `/staff/profile` | Update **full name, email, phone** (username is admin-managed). |
| `/staff/password` | **Change password** (current + new + confirm). |

Staff **cannot** delete customers, edit medicines, or see other staff’s bills in restricted views (enforced in routes).

---

## Database

- **Engine**: SQLite file `medical_inventory.db` in the **project root** (same folder as `run.py`).
- **Creation**: Tables are created automatically via `db.create_all()` when the app starts (`create_app()`).
- **Default admin**: If no `admin` user exists, one is created at startup (see **Default credentials**).

Main entities include: `User`, `Brand`, `Category`, `Supplier`, `Customer`, `Medicine`, `Purchase`, `Bill`, `BillItem`, `MedicineReturn`.

---

## How to run the project

### Prerequisites

- Python **3.10+** recommended (compatible with Flask 3.x).
- `pip` (or a virtual environment).

### 1. Clone or open the project folder

```bash
cd "path/to/Medical Inventory & Billing System with Analytics"
```

### 2. Create a virtual environment (recommended)

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. (Optional) Load demonstration data

Creates brands, categories, suppliers, customers, medicines, sample bills, and **staff** users if the DB looks empty:

```bash
python seed_data.py
```

If data already exists, the script skips loading. To start fresh: **stop the app**, delete `medical_inventory.db`, run the app once (to recreate schema), then run `seed_data.py` again.

### 5. Start the development server

```bash
python run.py
```

- **URL**: [http://127.0.0.1:5000](http://127.0.0.1:5000)  
- Debug mode is enabled in `run.py` for local development.

### 6. Sign in

- Open `/login`.
- Use an **admin** or **staff** account (see below).

---

## Default credentials

### Auto-created administrator (always ensured if missing)

| Field | Value |
|--------|--------|
| **Username** | `admin` |
| **Password** | `admin123` |

Created by `_ensure_default_admin()` in `app/__init__.py` when the database has no `admin` user.

### Demonstration staff (only after running `seed_data.py`)

| Username | Password | Display name |
|----------|----------|----------------|
| `staff1` | `staff123` | Riya Sharma |
| `staff2` | `staff123` | Amit Verma |

**Important:** Change all default passwords before any production or shared deployment. Update `SECRET_KEY` and `SQLALCHEMY_DATABASE_URI` in `app/__init__.py` (or use environment variables) for real environments.

---

## URL quick reference

| Area | Base path |
|------|-----------|
| Public | `/` |
| Login | `/login` |
| Admin | `/admin/...` |
| Staff | `/staff/...` |

---

## Development notes

- **Bill numbers**: Generated with a daily prefix (see `app/utils.py` — `next_bill_number()`).
- **Currency**: UI labels use **₹** (Indian rupee formatting in templates).
- **Pagination**: Admin and staff list pages use shared helpers (`paginate_url` / `paginate_url_global` in `app/utils.py` and `app/__init__.py`).

---

## License / usage

This repository is provided as an application template for learning or internal use. Add a license file if you redistribute the project.

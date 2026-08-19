# 🌿 Plant Nursery Management System

A complete full-stack **Plant Nursery Management System** built with **Flask**, **PostgreSQL (Neon)**, and **SQLAlchemy**. It includes a customer-facing website and a comprehensive, fully dynamic admin panel where the admin controls *every* manageable element of the site.

## ✨ Features

### Customer Website
- Responsive, elegant **dark green + white** theme (mobile → ultrawide)
- Home page with hero, announcements, featured/popular plants, categories, and dynamic homepage sections
- Plant catalog with search, category filter, price/availability filters, and sorting
- Plant detail pages with specs, stock, and quantity-based add-to-cart
- Customer registration & login (secure password hashing)
- Shopping cart (add / update / remove) with live badge
- Checkout that verifies stock, deducts inventory, creates orders + sales, and notifies the customer
- Customer profile: order history, edit profile, change password
- Contact form (saves message + notifies admin)
- Notifications center

### Admin Panel (everything is DB-driven)
- Secure admin/staff authentication with role-based access
- Dashboard with stats, charts, recent orders/customers, low-stock, latest messages
- **Plants** — full CRUD with image upload, featured/popular flags, stock
- **Categories** — CRUD with image
- **Inventory** — stock monitoring + manual adjustments (with audit log)
- **Customers** — list, detail (with order history), enable/disable
- **Orders** — list with filters, detail view (customer + items), status updates that notify customers
- **Sales** — revenue analytics by plant & category
- **Suppliers** — CRUD
- **Staff** — CRUD (super-admin only) with permissions
- **Messages** — view + reply (notifies customer)
- **Notifications** — broadcast to customers / admins
- **Website Management** — site name, tagline, about, contact, logo, favicon
- **Navigation** — header & footer menu items
- **Banners** — homepage promotional banners
- **Homepage Sections** — custom content blocks
- **Footer** — content & link toggles
- **Social Links** — platforms & URLs
- **Announcements** — site-wide announcement bar
- **Reports** — plants, inventory, customers, orders, sales, categories (printable)
- **Settings** — admin profile & password

## 🧱 Tech Stack
- **Backend:** Python 3.11+, Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF (CSRF)
- **Database:** PostgreSQL (Neon) with SSL
- **Frontend:** HTML5, CSS3 (Grid/Flexbox, responsive), JavaScript (ES6), Font Awesome 6
- **Security:** Werkzeug password hashing, CSRF protection, secure file uploads, input validation

## 🚀 Setup

1. **Clone / open the project**
   ```bash
   cd "plant nursery"
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv
   venv\Scripts\activate        # Windows
   # source venv/bin/activate   # macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   - Copy `.env.example` to `.env`
   - The app uses a local **SQLite** database (``nursery.db``) by default - no external DB setup needed
   - Set a strong `SECRET_KEY`
   - (Optional) Set default admin credentials

   ```bash
   cp .env.example .env
   ```

5. **Run the application**
   ```bash
   python run.py
   ```
   The app automatically creates all database tables and seeds default data
   (admin account, website settings, navigation, footer, social links, categories)
   on first launch.

6. **Open in your browser**
   - Website: http://localhost:5000
   - Admin: http://localhost:5000/admin
   - Default admin login: `admin` / `admin123` (change immediately)

## 🔐 Security Notes
- Passwords are hashed with Werkzeug's `pbkdf2:sha256`.
- Database credentials are loaded from environment variables only — never hard-coded.
- All admin routes are protected by `@admin_required` / `@super_admin_required` / `@staff_permission`.
- File uploads are validated by type, extension, and size, and stored with secure random filenames.
- CSRF protection is enabled on all state-changing forms.

## 📁 Project Structure
```
plant nursery/
├── app/
│   ├── __init__.py          # App factory, context processors, error handlers
│   ├── config.py            # Configuration (DB, upload, secrets)
│   ├── extensions.py        # db, login_manager
│   ├── models.py            # SQLAlchemy models
│   ├── decorators.py        # Auth decorators
│   ├── utils.py             # Helpers (uploads, currency, slugify)
│   ├── routes/
│   │   ├── main.py          # Public site
│   │   ├── auth.py          # Login / register / logout
│   │   ├── customer.py      # Profile, orders, checkout
│   │   └── admin.py         # Admin panel
│   ├── static/
│   │   ├── css/             # style.css, admin.css
│   │   ├── js/              # main.js, admin.js
│   │   └── images/          # favicon.svg, placeholder.svg, about.svg
│   └── templates/           # Jinja2 templates (base, main, auth, customer, admin, errors)
├── config.py
├── run.py
├── requirements.txt
├── .env.example
└── README.md
```

## 🌱 Notes
- The admin panel is the single source of truth: change the logo, nav, banners,
  homepage sections, announcements, social links, and all content from the UI —
  no source-code edits required.
- For production, set `FLASK_CONFIG=production` and use a strong `SECRET_KEY`.
# Plant-Nursery  

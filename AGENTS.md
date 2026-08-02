# AGENTS.md — Asha Shop FastAPI

## Project Overview

**Asha Shop FastAPI** is a full-featured Persian e-commerce platform rebuilt from a .NET 7 / C# / Onion Architecture original into **Python FastAPI** with **Docker Compose**. It includes a public storefront, comprehensive admin panel, JWT authentication, Iranian payment/SMS/tax integrations, and Persian (fa) / English (en) multi-language support.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| Web Framework | FastAPI 0.104 |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic 1.13 |
| Database | PostgreSQL 16 |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Validation | Pydantic v2 |
| Templates | Jinja2 (RTL Persian) |
| CSS | Tailwind CSS (CDN) |
| Icons | Font Awesome 6 (CDN) |
| Font | Vazirmatn (CDN) |
| API Docs | Swagger / ReDoc (auto) |
| Container | Docker + docker-compose |
| PDF | ReportLab |
| Excel | openpyxl |
| Email | aiosmtplib (Outlook SMTP) |
| SMS | FarazSMS / Melipayamak / Bale |
| Payment | ZarinPal |
| Persian Date | jdatetime |
| SEO | JSON-LD Schema.org (18 classes) |
| Background Jobs | TimedHostedService (async) |

---

## Project Structure

```
asha-shop-fastapi/
├── alembic/                       # Database migrations
│   ├── versions/
│   │   ├── 371737714c04_initial.py   # Initial migration (85 tables)
│   │   └── .gitkeep
│   ├── env.py                     # Alembic environment config
│   ├── script.py.mako             # Migration template
│   └── alembic.ini                # Alembic config
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point (119 lines)
│   ├── database.py                # Async SQLAlchemy engine + session
│   ├── seed.py                    # Database seed data (roles, users, policies)
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/                    # API version 1 (19 route files)
│   │       ├── auth.py            # JWT login/register/profile
│   │       ├── products.py        # Product CRUD + search
│   │       ├── categories.py      # Category tree + CRUD
│   │       ├── brands.py          # Brand CRUD
│   │       ├── cart.py            # Cart + checkout
│   │       ├── orders.py          # Order management
│   │       ├── payments.py        # ZarinPal payment gateway
│   │       ├── invoices.py        # Invoice CRUD
│   │       ├── purchase_orders.py # Purchase order CRUD
│   │       ├── admin.py           # Admin dashboard/stats/roles/settings
│   │       ├── admin_pages.py     # Admin page routes (916 lines)
│   │       ├── tickets.py         # Support tickets API
│   │       ├── chats.py           # Chat messaging API
│   │       ├── wallet.py          # Wallet balance/transfers
│   │       ├── finance.py         # Currency/receipts CRUD
│   │       ├── warehouse.py       # Warehouse movements
│   │       ├── notifications.py   # SMS/email send endpoints
│   │       ├── notify.py          # Back-in-stock + hooks + user actions
│   │       ├── seo.py             # JSON-LD schema + sitemap + robots
│   │       └── export.py          # PDF/Excel export + receipt upload + audit logs
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py            # Pydantic Settings (from .env)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── base.py                # SQLAlchemy Base + BaseEntityMixin
│   │   ├── security.py            # JWT create/decode, bcrypt hash/verify
│   │   └── dependencies.py        # get_current_user, require_role, get_admin
│   ├── middleware/
│   │   └── __init__.py            # Logging, security headers, localization, session, error handling
│   ├── models/                    # SQLAlchemy ORM models (12 files)
│   │   ├── __init__.py            # Imports all models for Alembic
│   │   ├── enums.py               # All enum types (40+ classes)
│   │   ├── identity.py            # User, Role, UserRole, RoleClaim, Claim, IdentityInformation
│   │   ├── common.py              # Address, SiteSetting, Captcha, ProvinceCity, etc.
│   │   ├── product.py             # Product, Category, Brand, Variety, Tag, etc.
│   │   ├── product_features.py    # TechnicalFeature, TechnicalTable, etc.
│   │   ├── order.py               # Order, OrderProduct, OrderStatusRecord, Discount
│   │   ├── invoice.py             # Invoice, InvoiceProduct, PurchaseOrder, Supplier
│   │   ├── finance.py             # Currency, Wallet, PaymentRequest, Receipt, WarehouseMovement
│   │   ├── customer_content.py    # Customer, Comment, Media, NotifiedProduct, etc.
│   │   ├── support.py             # Ticket, Chat, ChatMessage
│   │   └── manufacturer.py        # Manufacturer, ASHAInfo, Capability
│   ├── routes/
│   │   └── shop_pages.py          # Shop page routes (home, products, cart, checkout, profile)
│   ├── schemas/                   # Pydantic request/response models (9 files)
│   │   ├── __init__.py
│   │   ├── auth.py                # Login, Register, Token, UserResponse
│   │   ├── product.py             # Product, Category, Brand, SearchParams
│   │   ├── order.py               # CartItem, OrderRequest, OrderResponse
│   │   ├── invoice.py             # Invoice, InvoiceProduct, PurchaseOrder
│   │   ├── payment.py             # PaymentRequest, PaymentVerify
│   │   ├── finance.py             # Wallet, Receipt, Currency
│   │   ├── support.py             # Ticket, Chat, ChatMessage
│   │   └── warehouse.py           # WarehouseMovement, StockAlert
│   ├── services/                  # Business logic layer (14 files)
│   │   ├── __init__.py            # Exports all service functions
│   │   ├── auth_service.py        # Register, login, token refresh, password mgmt
│   │   ├── product_service.py     # Product/category/brand CRUD, search, filters
│   │   ├── order_service.py       # Cart management, order creation, status tracking
│   │   ├── invoice_service.py     # Invoice CRUD, tax calculations, order→invoice
│   │   ├── payment_service.py     # ZarinPal request/verify/callback
│   │   ├── sms_service.py         # FarazSMS, Melipayamak, Bale multi-provider
│   │   ├── email_service.py       # Outlook SMTP via aiosmtplib
│   │   ├── seo_service.py         # 18 JSON-LD Schema.org classes + converters
│   │   ├── admin_service.py       # Dashboard stats, order distribution, low stock
│   │   ├── finance_service.py     # Wallet CRUD, receipts, currency history
│   │   ├── support_service.py     # Ticket/chat CRUD, messaging
│   │   ├── warehouse_service.py   # Inventory movements, stock tracking
│   │   ├── localization_service.py# JSON-based fa/en translation
│   │   ├── easy_tax_payer.py      # Iranian tax invoice library
│   │   ├── notified_product_service.py # Back-in-stock alerts, user actions, search history
│   │   ├── pdf/
│   │   │   └── invoice_pdf.py     # ReportLab PDF generation for invoices/orders
│   │   └── excel/
│   │       └── excel_export.py    # openpyxl Excel export for products/orders/invoices
│   ├── templates/                 # Jinja2 templates (68 .html files)
│   │   ├── shop/                  # Public storefront (28 templates)
│   │   │   ├── base.html          # Main layout with header/footer
│   │   │   ├── index.html         # Homepage with featured/new/categories
│   │   │   ├── product_list.html  # Product grid + filters + pagination
│   │   │   ├── product_detail.html# Full product page + images + varieties
│   │   │   ├── cart.html          # Shopping cart with quantity controls
│   │   │   ├── checkout.html      # Address/payment/shipping form
│   │   │   ├── order_list.html    # User orders table
│   │   │   ├── order_detail.html  # Order detail + status history
│   │   │   ├── profile.html       # User profile with sidebar
│   │   │   ├── addresses.html     # Address CRUD
│   │   │   ├── bank_info.html     # Bank account management
│   │   │   ├── favorites.html     # Wishlist display
│   │   │   ├── identity.html      # Identity info for tax invoices
│   │   │   ├── change_password.html
│   │   │   ├── invoice_list.html  # User invoices
│   │   │   ├── receipt_list.html  # Payment receipts history
│   │   │   ├── receipt_upload.html# Bank receipt upload form
│   │   │   ├── wallet.html        # Wallet balance + transfers
│   │   │   ├── ticket_list.html   # Support tickets list
│   │   │   ├── ticket_new.html    # New ticket form
│   │   │   ├── ticket_detail.html # Ticket messages + reply
│   │   │   ├── search.html        # Search results
│   │   │   ├── brands.html        # Brand listing
│   │   │   ├── brand_detail.html  # Products by brand
│   │   │   ├── about.html
│   │   │   ├── contact.html
│   │   │   ├── faq.html
│   │   │   ├── forgot_password.html
│   │   │   ├── login.html
│   │   │   └── register.html
│   │   ├── admin/                 # Admin panel (32 templates)
│   │   │   ├── base.html          # Admin layout with sidebar navigation
│   │   │   ├── dashboard.html     # Stats cards + recent orders + low stock
│   │   │   ├── products.html      # Product data table
│   │   │   ├── product_form.html  # Create/edit product form
│   │   │   ├── categories.html    # Category tree + add form
│   │   │   ├── category_form.html # Category create/edit
│   │   │   ├── brands.html        # Brand list
│   │   │   ├── brand_form.html    # Brand create/edit
│   │   │   ├── orders.html        # Order list with status filter
│   │   │   ├── order_detail.html  # Order detail + status modal
│   │   │   ├── users.html         # User list with role modal
│   │   │   ├── user_detail.html   # User detail + role management
│   │   │   ├── roles.html         # Role list
│   │   │   ├── role_form.html     # Role create/edit
│   │   │   ├── invoices.html      # Invoice list
│   │   │   ├── invoice_detail.html# Invoice detail with products
│   │   │   ├── purchase_orders.html
│   │   │   ├── purchase_order_form.html
│   │   │   ├── suppliers.html
│   │   │   ├── supplier_form.html
│   │   │   ├── receipts_list.html
│   │   │   ├── currency_list.html
│   │   │   ├── warehouse_movements.html
│   │   │   ├── warehouse.html
│   │   │   ├── tickets.html
│   │   │   ├── ticket_detail.html
│   │   │   ├── comments.html      # Comment moderation
│   │   │   ├── settings.html      # Site settings form
│   │   │   ├── generic_list.html  # Reusable data table for all entity types
│   │   │   ├── generic_form.html  # Reusable form for all entity types
│   │   │   └── logs.html          # Audit log viewer
│   │   ├── email/                 # Email templates (4 .html)
│   │   │   ├── order_confirmation.html
│   │   │   ├── payment_confirmation.html
│   │   │   ├── verification_code.html
│   │   │   └── product_notification.html
│   │   └── errors/                # Error pages (2 .html)
│   │       ├── 404.html
│   │       └── 500.html
│   ├── utils/                     # Shared utilities (3 files)
│   │   ├── __init__.py
│   │   ├── operation_result.py    # Generic success/fail result wrapper
│   │   ├── persian_tools.py       # Persian date/number/string utilities
│   │   └── common_works.py        # Captcha, Cookies, Sessions, Slug, TableResult, etc.
│   ├── locales/                   # Localization (fa/en JSON)
│   │   ├── fa/common.json         # Persian translations (80+ keys)
│   │   └── en/common.json         # English translations (80+ keys)
│   └── static/                    # Static assets
│       └── uploads/               # User uploads (products, medias, receipts, datasheets)
├── tests/
│   └── test_services.py           # pytest unit tests
├── deploy/                        # Production deployment
│   ├── nginx.conf                 # Nginx + SSL + gzip + caching
│   ├── docker-compose.prod.yml    # Multi-stage prod setup
│   └── .env.example               # Production env template
├── .env                           # Development environment variables
├── .gitignore
├── alembic.ini                    # Alembic config (PostgreSQL)
├── docker-compose.yml             # Development docker-compose
├── Dockerfile                     # Python 3.12-slim image
├── pyproject.toml                 # pytest config
├── requirements.txt               # Python dependencies
└── AGENTS.md                      # This file
```

---

## Architecture

### Layer diagram
```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI App (app/main.py)             │
│  ┌───────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │ Middleware │  │ Templates│  │  API Routes (api/v1/) │ │
│  │(logging,   │  │(Jinja2)  │  │  - Auth, Products    │ │
│  │ security,  │  │          │  │  - Orders, Invoices   │ │
│  │ session)   │  │          │  │  - Cart, Payments     │ │
│  └───────────┘  └──────────┘  │  - Admin, SEO, Export  │ │
│                                └──────────────────────┘ │
│  ┌─────────────────────────────────────────────────────┐│
│  │              Services (app/services/)                ││
│  │  auth_service  product_service  order_service        ││
│  │  invoice_service  payment_service  sms_service       ││
│  │  email_service  seo_service  admin_service           ││
│  │  finance_service  warehouse_service  support_service ││
│  └─────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────┐│
│  │              Models (app/models/)                    ││
│  │  SQLAlchemy ORM — 85 tables across 12 model files   ││
│  └─────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────┐│
│  │              Database (PostgreSQL 16)                ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### Dependency injection pattern
- All API routes use FastAPI `Depends()` for:
  - Database sessions (`get_db`)
  - Authentication (`get_current_active_user`)
  - Role-based authorization (`require_role()`, `require_any_role()`, `get_admin_user`)
- Services are plain async functions called directly from route handlers

---

## Key Patterns & Conventions

### 1. Database Access
- **Async throughout** — `async with AsyncSession` via `async_session_factory`
- **Soft deletes** — `BaseEntityMixin.is_removed` on every entity
- **Decimal precision** — `Numeric(14, 2)` on all monetary fields (`.NET decimal` equivalent)
- **UUID primary keys** — matching .NET's `Guid` via `UUID(as_uuid=True)`

### 2. Authentication & Authorization
- **JWT** access tokens + refresh tokens via `python-jose`
- **bcrypt** password hashing via `passlib`
- Role-based access: `require_role("Admin")`, `require_any_role("Admin", "Product Manager")`
- Admin check: `get_admin_user` dependency
- Policies are defined in `app/seed.py` as `OperationAR` objects

### 3. API Design
- RESTful JSON API at `/api/v1/`
- Swagger docs at `/docs` (dev only)
- All endpoints prefixed, versioned, and documented
- Pagination via `page`/`page_size` query params on list endpoints
- Sorting via `sort_by`/`sort_desc` query params

### 4. Admin Panel
- **Dual approach**: REST API at `/api/v1/admin/*` + Jinja2 pages at `/admin/*`
- Generic CRUD patterns using `admin/generic_list.html` and `admin/generic_form.html`
- Admin page routes in `api/v1/admin_pages.py` (916 lines)

### 5. Shop (Public Storefront)
- Server-rendered Jinja2 templates at `/`, `/products`, `/cart`, `/checkout`, `/profile`, etc.
- Data fetched via API calls in JavaScript for dynamic sections
- RTL Persian layout with Tailwind CSS

### 6. Multi-Language (fa/en)
- JSON locale files in `app/locales/{locale}/common.json`
- Locale middleware detects `Accept-Language` header or `locale` cookie
- `LocalizationService` class for programmatic access

### 7. Background Jobs
- `TimedHostedService` runs during app lifespan
- Currently handles back-in-stock notifications (3600s interval)
- Easily extensible for other periodic tasks

### 8. SMS & Email
- Multi-provider SMS: `FarazSmsSender`, `MelipayamakSmsSender`, `BaleSmsSender`
- `SelectedSmsSender` delegates to configured provider + Bale for OTP
- Email via `aiosmtplib` (Outlook SMTP)
- Hooks in `api/v1/notify.py` auto-send on events

---

## Database Schema (85 tables)

| Domain | Tables | File |
|--------|--------|------|
| Identity | `users`, `roles`, `user_roles`, `role_claims`, `claims`, `user_logins`, `user_tokens`, `identity_informations` | `models/identity.py` |
| Common | `addresses`, `site_settings`, `captchas`, `bank_infos`, `mobile_numbers`, `sms_codes`, `logs`, `admin_parameters`, `province_cities`, `cities` | `models/common.py` |
| Products | `products`, `categories`, `brands`, `varieties`, `product_varieties`, `product_images`, `product_medias`, `category_medias`, `tags`, `product_tags`, `related_products`, `similar_products`, `suggested_products`, `favorite_product_lists`, `favorite_list_items`, `visited_products`, `price_histories`, `menu_datasheets`, `product_types`, `product_units`, `category_options`, `warranties`, `currencies` | `models/product.py` |
| Product Features | `technical_features`, `technical_feature_enums`, `technical_feature_values`, `technical_tables`, `technical_table_products`, `category_technical_features`, `features`, `product_accessories` | `models/product_features.py` |
| Orders | `orders`, `order_products`, `order_status_records`, `pay_methods`, `post_types`, `discounts` | `models/order.py` |
| Invoices | `invoices`, `invoice_products`, `invoice_references`, `purchase_orders`, `purchase_order_details`, `suppliers`, `supplier_products` | `models/invoice.py` |
| Finance | `currency_details`, `payment_requests`, `receipts`, `transactions`, `wallets`, `wallet_transfers`, `warehouse_movements` | `models/finance.py` |
| Customer | `customers`, `notifications`, `notified_products`, `search_histories`, `search_details`, `user_actions` | `models/customer_content.py` |
| Content | `comments`, `medias` | `models/customer_content.py` |
| Support | `tickets`, `chats`, `chat_messages`, `chat_reference_histories` | `models/support.py` |
| Manufacturer | `manufacturers`, `asha_infos`, `capabilities`, `paragraphs` | `models/manufacturer.py` |

---

## Common Development Tasks

### Local Development (without Docker)
```bash
# Install dependencies
pip install -r requirements.txt

# Set up PostgreSQL and update .env with local connection string
# Run migrations
alembic upgrade head

# Seed data
python -m app.seed

# Run server
uvicorn app.main:app --reload
```

### Docker Development
```bash
docker-compose up --build
```

### Add Migration
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Run Tests
```bash
pytest tests/ -v
```

### API Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Default Admin Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | `a.dastan@ashabeam.com` | `@Aa123456` |

---

## Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Files | `snake_case` | `product_service.py` |
| Classes | `PascalCase` | `ProductService` |
| Functions | `snake_case` | `get_product_by_id` |
| API routes | `snake_case` | `get_current_active_user` |
| Tables | `snake_case` (plural) | `order_products` |
| Models | `PascalCase` (singular) | `OrderProduct` |
| Columns | `snake_case` | `stock_quantity` |
| Enums | `PascalCase` | `OrderStatus.PAID` |
| Pydantic schemas | `PascalCase` + suffix | `ProductCreate`, `ProductResponse` |
| Private helpers | `_snake_case` | `_build_user_response` |

---

## Important Notes for AI Agents

1. **This is a FastAPI/Python project** — not .NET/Node.js
2. **All DB access is async** — use `await db.execute()`, never sync queries
3. **Soft delete is default** — always filter `is_removed == False`
4. **Docker networking** — app connects to `db` hostname (Docker service name)
5. **Localization is JSON-based** — in `app/locales/`, not .resx files
6. **Admin panel** — page routes in `admin_pages.py`, API in separate files
7. **Shop pages** — Jinja2 templates served by `shop_pages.py`
8. **Migrations** — auto-generated via Alembic; do not modify existing migrations
9. **180 API endpoints** registered across 19 route files
10. **68 HTML templates** across shop (28), admin (32), email (4), errors (2), and base layouts
# Asha Shop — FastAPI

A full-featured Persian e-commerce platform rebuilt from .NET 7 to Python FastAPI.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 + FastAPI 0.104 |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 (async) |
| Migrations | Alembic 1.13 |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Templates | Jinja2 (RTL Persian UI) |
| Payment | ZarinPal Gateway |
| SMS | FarazSMS / Melipayamak / Bale (multi-provider) |
| Email | Outlook SMTP (aiosmtplib) |
| Frontend | Tailwind CSS + Vazirmatn Font + Font Awesome |
| Container | Docker + docker-compose |

## Quick Start

### Prerequisites
- Docker & docker-compose
- Python 3.12 (for local development)

### Run with Docker
```bash
# Copy environment file
cp .env .env.local  # Edit as needed

# Build & start
docker-compose up --build

# App: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set up database (PostgreSQL must be running)
alembic upgrade head

# Run server
uvicorn app.main:app --reload
```

### Run Tests
```bash
pytest tests/ -v
```

## Project Structure

```
asha-shop-fastapi/
├── alembic/                    # Database migrations
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── database.py             # Async SQLAlchemy session
│   ├── api/v1/                 # API routes (auth, products, orders, etc.)
│   ├── config/                 # Pydantic Settings
│   ├── core/                   # Base models, security, dependencies
│   ├── models/                 # SQLAlchemy ORM models (85+ tables)
│   ├── schemas/                # Pydantic request/response schemas
│   ├── services/               # Business logic layer
│   ├── templates/              # Jinja2 templates (shop + admin)
│   ├── static/                 # Static assets (CSS, JS, uploads)
│   ├── utils/                  # Persian tools, operation result
│   ├── locales/                # fa/en translations
│   └── middleware/             # Logging, security, error handling
├── tests/                      # Pytest test suite
├── deploy/                     # Nginx config, docker-compose.prod
├── .env                        # Environment variables
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## API Endpoints (107+)

| Area | Endpoints | Description |
|------|-----------|-------------|
| Auth | 11 | Register, login, refresh, profile, admin users |
| Products | 12 | Search, filter, sort, detail, featured, related |
| Categories | 10 | Tree, flat, products by category, CRUD |
| Brands | 4 | List, detail, CRUD |
| Cart | 9 | Add, remove, update, checkout, pay/post methods |
| Orders | 6 | User orders, detail, admin all, status update |
| Payment | 5 | ZarinPal request, callback, status |
| Notifications | 6 | SMS (verify, order, product), Email (verify, order, payment) |
| Invoices | 7 | CRUD, from-order, suppliers |
| Admin | 10 | Dashboard, roles, settings, comments, users |
| Wallet | 4 | Balance, transfers, credit/debit |
| Finance | 6 | Currencies, receipts, confirm |
| Warehouse | 6 | Movements, import/export, low stock alerts |
| Support | 10 | Tickets CRUD, chat messages, seen status |
| SEO | 7 | JSON-LD schemas, sitemap, robots.txt |

## Architecture

```
shop_pages → templates/shop/     (public storefront)
admin_pages → templates/admin/   (admin panel)
       ↓
api/v1/*  →  services/*  →  models/*  →  database.py
                                     ↓
                                PostgreSQL
```

## Features

- ✅ Full e-commerce CRUD (products, categories, brands, orders, invoices)
- ✅ Custom auth (JWT + phone/email login + roles/permissions)
- ✅ Shopping cart + checkout flow
- ✅ ZarinPal payment gateway
- ✅ Multi-provider SMS (FarazSMS, Melipayamak, Bale)
- ✅ Email notifications (Outlook SMTP)
- ✅ Admin panel with dashboard + full CRUD pages
- ✅ Public storefront (home, products, cart, profile, orders)
- ✅ Warehouse inventory management
- ✅ Wallet system + bank receipts
- ✅ Iranian tax invoice (EasyTaxPayer)
- ✅ Multi-language (fa/en) via JSON locales
- ✅ JSON-LD structured data (17 Schema.org types)
- ✅ Sitemap.xml + robots.txt
- ✅ Persian (Shamsi) date utilities
- ✅ Soft delete on all entities
- ✅ Docker + Nginx production setup

# Student Thrift Store

## Overview

Student Thrift Store is a campus marketplace where students can list, browse, and wishlist pre-owned items such as electronics, books, fashion, furniture, and study gear. Buyers contact sellers through displayed username/email — there is no in-app checkout or payment yet.

## Features

- User registration and login (session-based)
- Product listings with optional image uploads
- Create, read, update, and delete listings (owners and admins)
- Search and filter by keyword, category, and price range
- Wishlist add/remove toggle
- Seller contact display (username and email)
- Django admin for `Product` and `Wishlist`

## Tech Stack

- Python
- Django
- Django REST Framework
- MySQL (application database)
- HTML / CSS / JavaScript
- Bootstrap 5
- jQuery
- Pillow (image handling)
- PyMySQL
- python-dotenv

## Architecture

```
Browser (templates/index.html + AJAX)
        ↓
Django + Django REST Framework
        ↓
MySQL (transactional database)
```

Uploaded images are stored under `media/product_images/` on the local filesystem.

## Database Models

### User (Django built-in)

Authentication and listing ownership.

### Product

Listings posted by users.

Important fields: `title`, `description`, `price` (Decimal), `category` (controlled values), `image`, `created_at`, `updated_at`, `user` (FK).

Allowed categories:

`Electronics`, `Fashion`, `Books`, `Furniture`, `Gaming`, `Education`, `Misc`

### Wishlist

Saved products per user (`unique_together` on user + product).

```
User
 ├── Product
 │     └── Wishlist
 └── Wishlist
```

## API Endpoints

All API routes are under `/api/`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/products/` | List/search/filter products (`search`, `category`, `min_price`, `max_price`) |
| POST | `/api/products/` | Create product (login required) |
| PUT | `/api/update/<id>/` | Update product (owner or superuser) |
| DELETE | `/api/delete/<id>/` | Delete product (owner or superuser) |
| POST | `/api/register/` | Register and log in |
| POST | `/api/login/` | Log in |
| POST | `/api/logout/` | Log out |
| GET | `/api/profile/` | Current session user |
| GET | `/api/wishlist/` | Current user's wishlist |
| POST | `/api/wishlist/` | Toggle wishlist item (`product_id`) |

Frontend:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Main SPA page |
| — | `/admin/` | Django admin |
| — | `/accounts/` | Django auth URLs (login template available) |

## Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd student-thrift-store
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install requirements

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your local values (`SECRET_KEY`, MySQL credentials, etc.).  
Do **not** commit `.env`.

### 5. Create the MySQL database

```sql
CREATE DATABASE thrift_store CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Ensure MySQL is running and matches `DB_*` in `.env`.

### 6. Run migrations

```bash
python manage.py migrate
```

### 7. (Optional) Create a superuser

```bash
python manage.py createsuperuser
```

### 8. (Optional) Load sample data

CSV import (uses `products.csv`):

```bash
python import_csv.py
```

Random seed data:

```bash
python seed_data.py
```

Both scripts clear existing products first. `seed_data.py` also deletes non-`admin` users.

### 9. Start the development server

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

### SQLite override (optional)

For local experiments without MySQL:

```bash
USE_SQLITE=1 python manage.py migrate
USE_SQLITE=1 python manage.py runserver
```

Automated tests always use SQLite.

## Testing

```bash
python manage.py test store
```

Event instrumentation tests:

```bash
USE_SQLITE=1 python manage.py test store.tests_events
```

## Analytics (Phase 1)

The API emits marketplace analytics events after successful DB commits (`transaction.on_commit`):

`user_registered`, `listing_created`, `listing_updated`, `listing_deleted`, `wishlist_added`, `wishlist_removed`

See `analytics/README.md`. Events are logged locally in Phase 1 — **Kafka is not connected yet**.

## Future Improvements

These are **not implemented** today:

- Purchase / order / payment flows
- Listing sold status and expiration
- Reviews and messaging
- Kafka streaming, S3 raw storage, Airflow, dbt, warehouse, Tableau (planned later phases)

## Security notes

- Keep secrets in `.env`, never in git
- Set `DEBUG=False` and a strong `SECRET_KEY` outside local development
- Configure `ALLOWED_HOSTS` for any deployed environment

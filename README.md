# Vanilla Coffee — Web Platform

Flask web platform for **Vanilla Coffee** — bilingual (Russian / Uzbek)
QR-menu with full product catalog stored in SQLite.

## Quick start

```bash
pip install -r requirements.txt
python seed.py          # seed the database (run once, or to reset)
python app.py
```

Open: http://localhost:5050

The first time `app.py` starts it auto-creates and seeds the DB if empty —
so `seed.py` is only needed when you want to **reset** the data.

## Project layout

```
coffee/
├── app.py            # Flask app, routes, order + i18n + menu API
├── db.py             # SQLite layer (categories, products, sizes, ingredients)
├── seed.py           # CLI: reset + seed the DB
├── seed_data.py      # full bilingual catalog: 7 categories, 57 products
├── i18n.py           # all UI text translations (RU / UZ)
├── vanilla.db        # SQLite database (auto-created)
├── orders.json       # incoming orders (auto-created)
├── requirements.txt
├── templates/
│   ├── index.html    # main page (Jinja2, server-rendered initial RU/UZ)
│   └── admin.html    # barista order panel (auto-refresh every 15s)
└── static/
    ├── css/styles.css
    └── js/app.js     # menu, cart, hover-loader lang switcher, detail modal
```

## Routes

| Route | Purpose |
| --- | --- |
| `GET  /` | main page |
| `GET  /?lang=uz` or `?lang=ru` | switch language |
| `GET  /table/<id>` | QR-bound page for table N |
| `GET  /admin` | barista panel (incoming orders) |
| `GET  /api/menu` | categories + products (bilingual) |
| `GET  /api/product/<id>` | single product details |
| `GET  /api/i18n` | full UI text map |
| `POST /api/order` | place order |
| `GET  /api/orders` | list all saved orders |

## Generating QR codes for tables

Each table should print a QR pointing to:

```
https://<your-domain>/table/1
https://<your-domain>/table/2
…
```

When scanned, the client lands on the menu with their table number bound to
the session — orders sent from that device show `Table N` in the admin panel.

## Language switching (hover-to-commit)

The language chip in the top nav reveals a dropdown on hover.
Hovering an option triggers a **circular progress ring** that fills in
~650 ms. If you keep hovering until it completes, the language commits
and the entire UI swaps without a full reload. Moving away cancels it.

Selected language is also pushed to the server session, so subsequent
page loads stay in the chosen language.

## Catalog

Seven categories, 57 items, real prices in UZS.
Each product has bilingual name, description, list of ingredients,
optional badge tag, image, and 1–3 size/price tiers.

Edit `seed_data.py` to add or change products, then run `python seed.py`
to apply.

## Tech

- Python 3 + Flask 3
- SQLite via standard `sqlite3` (no ORM, no external DB)
- Vanilla JS / CSS — no build step, no framework
- Google Fonts (Inter, Playfair Display, Pacifico)
# coffee

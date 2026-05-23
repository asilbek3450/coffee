"""
Vanilla Coffee — Flask web platform
Bilingual (RU/UZ) interactive QR-menu + admin CRUD, SEO-ready, Railway-ready.
"""
from functools import wraps
from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, url_for, flash, make_response,
)
from datetime import datetime, timezone
import json
import os
import secrets
import uuid

import db
import seed
from i18n import I18N, dict_for

# ---------- ENV / CONFIG ----------
IS_PROD = os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("FLASK_ENV") == "production"

SECRET_KEY = os.environ.get("SECRET_KEY") or ("dev-" + secrets.token_hex(16))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "wcoffee-admin")
SITE_URL = (os.environ.get("SITE_URL", "http://localhost:5050")).rstrip("/")

DATA_DIR = os.environ.get("DATA_DIR") or os.path.dirname(__file__)
os.makedirs(DATA_DIR, exist_ok=True)
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")

SUPPORTED_LANGS = ("ru", "uz")
DEFAULT_LANG = "ru"


# ---------- JINJA FILTERS ----------
def _from_json_filter(value):
    if not value:
        return []
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []


# ---------- APP ----------
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.jinja_env.filters["from_json"] = _from_json_filter

# Secure session cookies in production
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(IS_PROD),
    PREFERRED_URL_SCHEME="https" if IS_PROD else "http",
    JSON_AS_ASCII=False,
    SEND_FILE_MAX_AGE_DEFAULT=60 * 60 * 24 * 30,  # 30d static cache (mtime busted)
)


# ---------- Security & cache headers ----------
@app.after_request
def add_security_headers(resp):
    # Long cache for hashed/versioned static assets
    if request.path.startswith("/static/"):
        resp.headers.setdefault("Cache-Control", "public, max-age=2592000, immutable")
    # SEO + security headers
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if IS_PROD:
        resp.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains"
        )
    return resp


@app.context_processor
def inject_asset_url():
    def asset_url(filename):
        file_path = os.path.join(app.static_folder, filename)
        version = None
        try:
            version = int(os.path.getmtime(file_path))
        except OSError:
            version = None
        return url_for("static", filename=filename, v=version)

    return {"asset_url": asset_url}


# ---------- BOOTSTRAP: ensure DB exists & seeded ----------
def _bootstrap_db():
    db.init_db()
    if not db.all_categories():
        seed.run()


_bootstrap_db()


# ---------- ORDERS HELPERS ----------
def load_orders():
    if not os.path.exists(ORDERS_FILE):
        return []
    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_orders(orders):
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)


# ---------- LANG HELPER ----------
def current_lang():
    lang = (request.args.get("lang") or session.get("lang") or DEFAULT_LANG).lower()
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    return lang


# ---------- SEO HELPERS ----------
SEO = {
    "ru": {
        "title": "Vanilla Coffee — Спешелти кофейня в Ташкенте | Кофе, выпечка, завтраки",
        "description": (
            "Vanilla Coffee — уютная speciality-кофейня в Ташкенте. "
            "Свежеобжаренный кофе, домашняя выпечка, авторские напитки, завтраки, фреши. "
            "QR-меню, заказ со столика, работаем с 8:00 до 23:00."
        ),
        "keywords": (
            "Vanilla Coffee, ваниль кофе, ванилла кофе, кофейня Ташкент, speciality coffee, "
            "кофе с собой, латте, капучино, раф, фреши, домашняя выпечка, завтраки Ташкент, "
            "лучшая кофейня, coffee shop Tashkent"
        ),
    },
    "uz": {
        "title": "Vanilla Coffee — Toshkentdagi speciality kafe | Kofe, shirinliklar, nonushta",
        "description": (
            "Vanilla Coffee — Toshkent markazidagi qulay speciality kafe. "
            "Yangi qovurilgan kofe, uy shirinliklari, mualliflik ichimliklari, "
            "nonushta va freshlar. QR-menyu va stoldan turib buyurtma. 8:00–23:00."
        ),
        "keywords": (
            "Vanilla Coffee, vanilla kofe, vanilla, kofe, Toshkent kafe, speciality coffee, "
            "latte, kapuchino, raf, fresh sharbat, uy shirinliklari, nonushta Toshkent, "
            "Toshkentdagi eng yaxshi kafe, coffee shop Tashkent"
        ),
    },
}


def build_seo(lang, table=None):
    base = SEO.get(lang, SEO["ru"])
    if table:
        suffix = f" — Стол {table}" if lang == "ru" else f" — Stol {table}"
        return {**base, "title": base["title"] + suffix}
    return base


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_jsonld(lang):
    """Schema.org graph: CafeOrCoffeeShop + Menu + WebSite + Organization."""
    products = db.all_products()
    cats = {c["id"]: c for c in db.all_categories()}

    menu_sections = {}
    for p in products:
        cid = p["category_id"]
        menu_sections.setdefault(cid, []).append(p)

    sections = []
    for cid, items in menu_sections.items():
        c = cats.get(cid, {"name": {"ru": cid, "uz": cid}})
        sections.append({
            "@type": "MenuSection",
            "name": c["name"].get(lang, c["name"]["ru"]),
            "hasMenuItem": [
                {
                    "@type": "MenuItem",
                    "name": p["name"].get(lang, p["name"]["ru"]),
                    "description": p["desc"].get(lang, p["desc"]["ru"]),
                    "image": p["img"],
                    "offers": [
                        {
                            "@type": "Offer",
                            "price": s["price"],
                            "priceCurrency": "UZS",
                            "availability": "https://schema.org/InStock",
                            "name": (s["label"] + (" мл" if s["kind"] == "ml" else "")),
                        }
                        for s in p["sizes"]
                    ],
                }
                for p in items
            ],
        })

    cafe = {
        "@type": "CafeOrCoffeeShop",
        "@id": f"{SITE_URL}/#cafe",
        "name": "Vanilla Coffee",
        "description": SEO[lang]["description"],
        "url": SITE_URL,
        "logo": f"{SITE_URL}/static/img/logo-mark.png",
        "image": [
            f"{SITE_URL}/static/img/og.svg",
            f"{SITE_URL}/static/img/logo-full.png",
        ],
        "telephone": "+998 90 123 45 67",
        "priceRange": "$$",
        "servesCuisine": ["Coffee", "Bakery", "Breakfast"],
        "paymentAccepted": "Cash, Credit Card, Click, Payme",
        "currenciesAccepted": "UZS",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "Coffee Street, 24",
            "addressLocality": "Tashkent",
            "addressRegion": "Tashkent",
            "postalCode": "100000",
            "addressCountry": "UZ",
        },
        "geo": {
            "@type": "GeoCoordinates",
            "latitude": "41.311081",
            "longitude": "69.240562",
        },
        "openingHoursSpecification": [
            {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday",
                              "Friday", "Saturday", "Sunday"],
                "opens": "08:00",
                "closes": "23:00",
            }
        ],
        "hasMenu": {
            "@type": "Menu",
            "name": "Vanilla Coffee Menu",
            "hasMenuSection": sections,
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "4.9",
            "reviewCount": "127",
        },
        "sameAs": [
            "https://www.instagram.com/vanillacoffee",
            "https://t.me/vanillacoffee",
        ],
    }

    website = {
        "@type": "WebSite",
        "@id": f"{SITE_URL}/#website",
        "url": SITE_URL,
        "name": "Vanilla Coffee",
        "description": SEO[lang]["description"],
        "inLanguage": [lang, "ru", "uz"],
        "publisher": {"@id": f"{SITE_URL}/#cafe"},
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{SITE_URL}/?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    }

    organization = {
        "@type": "Organization",
        "@id": f"{SITE_URL}/#organization",
        "name": "Vanilla Coffee",
        "url": SITE_URL,
        "logo": f"{SITE_URL}/static/img/logo-mark.png",
        "sameAs": [
            "https://www.instagram.com/vanillacoffee",
            "https://t.me/vanillacoffee",
        ],
    }

    return {
        "@context": "https://schema.org",
        "@graph": [cafe, website, organization],
    }


def build_menu_sections(lang):
    categories = db.all_categories()
    products = db.all_products()
    grouped = []

    for category in categories:
        items = [p for p in products if p["category_id"] == category["id"]]
        if not items:
            continue

        min_price = min(
            size["price"]
            for item in items
            for size in item.get("sizes", [])
        )

        grouped.append({
            "id": category["id"],
            "name": category["name"].get(lang, category["name"]["ru"]),
            "icon": category.get("icon", ""),
            "cover": items[0].get("img") or "/static/img/og.svg",
            "items_count": len(items),
            "min_price": min_price,
            "products": items,
        })

    return grouped


def build_menu_section_by_id(lang, category_id):
    for section in build_menu_sections(lang):
        if section["id"] == category_id:
            return section
    return None


def build_i18n_payload():
    return {k: {"ru": v.get("ru", ""), "uz": v.get("uz", "")} for k, v in I18N.items()}


# ---------- PUBLIC ROUTES ----------
@app.route("/")
def index():
    table = request.args.get("table")
    if table:
        session["table"] = table
    lang = current_lang()
    session["lang"] = lang
    return render_template(
        "index.html",
        table=session.get("table"),
        lang=lang,
        t=dict_for(lang),
        supported_langs=SUPPORTED_LANGS,
        site_url=SITE_URL,
        seo=build_seo(lang, session.get("table")),
        jsonld=json.dumps(build_jsonld(lang), ensure_ascii=False),
        categories=db.all_categories(),
        products=db.all_products(),
        initial_i18n=json.dumps(build_i18n_payload(), ensure_ascii=False),
        initial_menu=json.dumps({
            "categories": db.all_categories(),
            "products": db.all_products(),
        }, ensure_ascii=False),
        canonical=f"{SITE_URL}/",
    )


@app.route("/table/<table_id>")
def table_view(table_id):
    session["table"] = table_id
    lang = current_lang()
    session["lang"] = lang
    return render_template(
        "index.html",
        table=table_id,
        lang=lang,
        t=dict_for(lang),
        supported_langs=SUPPORTED_LANGS,
        site_url=SITE_URL,
        seo=build_seo(lang, table_id),
        jsonld=json.dumps(build_jsonld(lang), ensure_ascii=False),
        categories=db.all_categories(),
        products=db.all_products(),
        initial_i18n=json.dumps(build_i18n_payload(), ensure_ascii=False),
        initial_menu=json.dumps({
            "categories": db.all_categories(),
            "products": db.all_products(),
        }, ensure_ascii=False),
        canonical=f"{SITE_URL}/table/{table_id}",
    )


@app.route("/menu")
def menu_page():
    lang = current_lang()
    session["lang"] = lang
    return render_template(
        "menu.html",
        table=session.get("table"),
        lang=lang,
        t=dict_for(lang),
        supported_langs=SUPPORTED_LANGS,
        site_url=SITE_URL,
        seo={
            **build_seo(lang),
            "title": "Vanilla Coffee Menyusi" if lang == "uz" else "Меню Vanilla Coffee",
        },
        jsonld=json.dumps(build_jsonld(lang), ensure_ascii=False),
        canonical=f"{SITE_URL}/menu",
        menu_sections=build_menu_sections(lang),
    )


@app.route("/menu/category/<category_id>")
def menu_category_page(category_id):
    lang = current_lang()
    session["lang"] = lang
    section = build_menu_section_by_id(lang, category_id)
    if not section:
        return not_found(None)

    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1,
             "name": "Vanilla Coffee", "item": SITE_URL + "/"},
            {"@type": "ListItem", "position": 2,
             "name": ("Меню" if lang == "ru" else "Menyu"),
             "item": f"{SITE_URL}/menu"},
            {"@type": "ListItem", "position": 3,
             "name": section["name"],
             "item": f"{SITE_URL}/menu/category/{category_id}"},
        ],
    }

    return render_template(
        "menu_category.html",
        table=session.get("table"),
        lang=lang,
        t=dict_for(lang),
        supported_langs=SUPPORTED_LANGS,
        site_url=SITE_URL,
        seo={
            **build_seo(lang),
            "title": f"{section['name']} | Vanilla Coffee",
        },
        jsonld=json.dumps(build_jsonld(lang), ensure_ascii=False),
        breadcrumb_jsonld=json.dumps(breadcrumb, ensure_ascii=False),
        canonical=f"{SITE_URL}/menu/category/{category_id}",
        section=section,
    )


# ---------- API ----------
@app.route("/api/menu")
def api_menu():
    return jsonify({
        "categories": db.all_categories(),
        "products": db.all_products(),
    })


@app.route("/api/product/<pid>")
def api_product(pid):
    p = db.product_by_id(pid)
    if not p:
        return jsonify({"ok": False, "error": "Not found"}), 404
    return jsonify({"ok": True, "product": p})


@app.route("/api/i18n")
def api_i18n():
    return jsonify(build_i18n_payload())


@app.route("/api/order", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    if not items:
        return jsonify({"ok": False, "error": "Empty cart"}), 400

    order = {
        "id": str(uuid.uuid4())[:8].upper(),
        "table": data.get("table") or session.get("table") or "—",
        "items": items,
        "total": data.get("total", 0),
        "note": (data.get("note") or "").strip()[:300],
        "lang": data.get("lang") or session.get("lang") or DEFAULT_LANG,
        "created_at": utc_now_iso(),
        "status": "new",
    }

    orders = load_orders()
    orders.append(order)
    save_orders(orders)

    return jsonify({"ok": True, "order_id": order["id"], "eta_min": 7})


@app.route("/api/orders")
def list_orders():
    return jsonify(load_orders())


# ---------- HEALTH + SEO ----------
@app.route("/healthz")
def healthz():
    """Railway healthcheck endpoint."""
    try:
        s = db.stats()
        return jsonify({"ok": True, **s, "ts": utc_now_iso()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/robots.txt")
def robots():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /admin/\n"
        "Disallow: /api/order\n"
        "Disallow: /api/orders\n"
        f"\nSitemap: {SITE_URL}/sitemap.xml\n"
    )
    resp = make_response(body)
    resp.headers["Content-Type"] = "text/plain; charset=utf-8"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/sitemap.xml")
def sitemap():
    """Sitemap with bilingual hreflang alternates."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = []

    def add(loc):
        urls.append({
            "loc": loc,
            "lastmod": now,
            "alternates": [
                {"hreflang": "ru", "href": loc + ("&" if "?" in loc else "?") + "lang=ru"},
                {"hreflang": "uz", "href": loc + ("&" if "?" in loc else "?") + "lang=uz"},
                {"hreflang": "x-default", "href": loc},
            ],
        })

    add(f"{SITE_URL}/")
    add(f"{SITE_URL}/menu")
    for category in db.all_categories():
        add(f"{SITE_URL}/menu/category/{category['id']}")
    # Include a handful of table pages (extend as needed)
    for n in range(1, 21):
        add(f"{SITE_URL}/table/{n}")

    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
           '        xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for u in urls:
        xml.append("  <url>")
        xml.append(f"    <loc>{u['loc']}</loc>")
        xml.append(f"    <lastmod>{u['lastmod']}</lastmod>")
        xml.append("    <changefreq>weekly</changefreq>")
        xml.append("    <priority>0.8</priority>")
        for a in u["alternates"]:
            xml.append(f'    <xhtml:link rel="alternate" hreflang="{a["hreflang"]}" href="{a["href"]}"/>')
        xml.append("  </url>")
    xml.append("</urlset>")

    resp = make_response("\n".join(xml))
    resp.headers["Content-Type"] = "application/xml; charset=utf-8"
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


# ================================================================
# ADMIN PANEL — login + CRUD for categories, products, orders
# ================================================================

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        u = (request.form.get("username") or "").strip()
        p = request.form.get("password") or ""
        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session["admin"] = True
            nxt = request.args.get("next") or url_for("admin_dashboard")
            return redirect(nxt)
        error = "Неверный логин или пароль"
    return render_template("admin/login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    s = db.stats()
    orders = load_orders()
    return render_template(
        "admin/dashboard.html",
        stats=s,
        orders=orders,
        recent_orders=list(reversed(orders))[:5],
    )


@app.route("/admin/orders")
@login_required
def admin_orders():
    return render_template("admin/orders.html", orders=list(reversed(load_orders())))


# ---------- categories ----------
@app.route("/admin/categories")
@login_required
def admin_categories():
    cats = db.list_categories_raw()
    with db.get_conn() as conn:
        counts = {
            r["category_id"]: r["c"]
            for r in conn.execute(
                "SELECT category_id, COUNT(*) AS c FROM products GROUP BY category_id"
            ).fetchall()
        }
    for c in cats:
        c["product_count"] = counts.get(c["id"], 0)
    return render_template("admin/categories.html", categories=cats)


@app.route("/admin/categories/new", methods=["GET", "POST"])
@login_required
def admin_category_new():
    if request.method == "POST":
        return _save_category(None)
    return render_template("admin/category_form.html", cat=None, mode="new")


@app.route("/admin/categories/<cid>/edit", methods=["GET", "POST"])
@login_required
def admin_category_edit(cid):
    cat = db.category_by_id(cid)
    if not cat:
        flash("Категория не найдена")
        return redirect(url_for("admin_categories"))
    if request.method == "POST":
        return _save_category(cat)
    return render_template("admin/category_form.html", cat=cat, mode="edit")


def _save_category(existing):
    f = request.form
    name_ru = (f.get("name_ru") or "").strip()
    name_uz = (f.get("name_uz") or "").strip()
    icon = (f.get("icon") or "").strip() or "📦"
    sort = int(f.get("sort_order") or 0)

    if not name_ru or not name_uz:
        flash("Введите название на обоих языках")
        return redirect(request.url)

    if existing:
        cid = existing["id"]
    else:
        cid = db.unique_id_for_category(db.slugify(name_ru, "cat"))

    db.insert_category({
        "id": cid, "name_ru": name_ru, "name_uz": name_uz,
        "icon": icon, "sort_order": sort,
    })
    flash("Категория сохранена ✓")
    return redirect(url_for("admin_categories"))


@app.route("/admin/categories/<cid>/delete", methods=["POST"])
@login_required
def admin_category_delete(cid):
    ok, err = db.delete_category(cid)
    flash("Удалено ✓" if ok else f"Нельзя удалить: {err}")
    return redirect(url_for("admin_categories"))


# ---------- products ----------
@app.route("/admin/products")
@login_required
def admin_products():
    cat = request.args.get("cat") or ""
    q = (request.args.get("q") or "").lower()
    items = db.list_products_raw()
    if cat:
        items = [p for p in items if p["category_id"] == cat]
    if q:
        items = [p for p in items if q in (p["name_ru"] or "").lower() or q in (p["name_uz"] or "").lower()]
    return render_template(
        "admin/products.html",
        products=items,
        categories=db.list_categories_raw(),
        current_cat=cat,
        q=q,
    )


@app.route("/admin/products/new", methods=["GET", "POST"])
@login_required
def admin_product_new():
    if request.method == "POST":
        return _save_product(None)
    return render_template(
        "admin/product_form.html",
        product=None, mode="new",
        categories=db.list_categories_raw(),
    )


@app.route("/admin/products/<pid>/edit", methods=["GET", "POST"])
@login_required
def admin_product_edit(pid):
    p = db.product_raw(pid)
    if not p:
        flash("Товар не найден")
        return redirect(url_for("admin_products"))
    if request.method == "POST":
        return _save_product(p)
    return render_template(
        "admin/product_form.html",
        product=p, mode="edit",
        categories=db.list_categories_raw(),
    )


def _save_product(existing):
    f = request.form
    name_ru = (f.get("name_ru") or "").strip()
    name_uz = (f.get("name_uz") or "").strip()
    if not name_ru or not name_uz:
        flash("Введите название на обоих языках")
        return redirect(request.url)

    cat = (f.get("category_id") or "").strip()
    if not cat or not db.category_by_id(cat):
        flash("Выберите существующую категорию")
        return redirect(request.url)

    ing_ru = [line.strip() for line in (f.get("ingredients_ru") or "").splitlines() if line.strip()]
    ing_uz = [line.strip() for line in (f.get("ingredients_uz") or "").splitlines() if line.strip()]

    labels = f.getlist("size_label")
    kinds = f.getlist("size_kind")
    prices = f.getlist("size_price")
    sizes = []
    for i in range(len(labels)):
        lab = labels[i].strip()
        if not lab:
            continue
        try:
            pr = int(prices[i].replace(" ", "").replace(",", ""))
        except (ValueError, IndexError):
            continue
        kd = kinds[i] if i < len(kinds) else "ml"
        sizes.append({"label": lab, "kind": kd, "price": pr})
    if not sizes:
        flash("Добавьте хотя бы один размер с ценой")
        return redirect(request.url)

    if existing:
        pid = existing["id"]
    else:
        pid = db.unique_id_for_product(db.slugify(name_ru, "item"))

    db.insert_product({
        "id": pid,
        "category_id": cat,
        "name_ru": name_ru, "name_uz": name_uz,
        "desc_ru": (f.get("desc_ru") or "").strip(),
        "desc_uz": (f.get("desc_uz") or "").strip(),
        "ingredients_ru": ing_ru, "ingredients_uz": ing_uz,
        "tag_ru": (f.get("tag_ru") or "").strip(),
        "tag_uz": (f.get("tag_uz") or "").strip(),
        "img": (f.get("img") or "").strip(),
        "volume_note": (f.get("volume_note") or "").strip() or None,
        "sort_order": int(f.get("sort_order") or 0),
        "sizes": sizes,
    })
    flash("Товар сохранён ✓")
    return redirect(url_for("admin_products"))


@app.route("/admin/products/<pid>/delete", methods=["POST"])
@login_required
def admin_product_delete(pid):
    db.delete_product(pid)
    flash("Товар удалён ✓")
    return redirect(url_for("admin_products"))


# ---------- 404 ----------
@app.errorhandler(404)
def not_found(_e):
    lang = current_lang()
    return render_template(
        "index.html",
        table=session.get("table"),
        lang=lang,
        t=dict_for(lang),
        supported_langs=SUPPORTED_LANGS,
        site_url=SITE_URL,
        seo=build_seo(lang),
        jsonld=json.dumps(build_jsonld(lang), ensure_ascii=False),
        categories=db.all_categories(),
        products=db.all_products(),
        initial_i18n=json.dumps(build_i18n_payload(), ensure_ascii=False),
        initial_menu=json.dumps({
            "categories": db.all_categories(),
            "products": db.all_products(),
        }, ensure_ascii=False),
        canonical=f"{SITE_URL}/",
    ), 404


# ---------- DEV SERVER ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=not IS_PROD)

"""SQLite layer for Vanilla Coffee menu."""
import sqlite3
import os
import json
from contextlib import contextmanager

# In production (Railway): set DATA_DIR=/data and mount a Volume there
# so the SQLite file survives redeploys.
DATA_DIR = os.environ.get("DATA_DIR") or os.path.dirname(__file__)
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "vanilla.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
  id          TEXT PRIMARY KEY,
  name_ru     TEXT NOT NULL,
  name_uz     TEXT NOT NULL,
  icon        TEXT,
  sort_order  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS products (
  id              TEXT PRIMARY KEY,
  category_id     TEXT NOT NULL REFERENCES categories(id),
  name_ru         TEXT NOT NULL,
  name_uz         TEXT NOT NULL,
  desc_ru         TEXT,
  desc_uz         TEXT,
  ingredients_ru  TEXT,        -- JSON list[str]
  ingredients_uz  TEXT,        -- JSON list[str]
  tag_ru          TEXT,
  tag_uz          TEXT,
  img             TEXT,
  volume_note     TEXT,        -- e.g. "350 ml", "1 шт"
  sort_order      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS product_sizes (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id   TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  size_label   TEXT NOT NULL,    -- "250", "450", "1 шт"
  size_kind    TEXT NOT NULL DEFAULT 'ml',  -- 'ml' or 'piece'
  price        INTEGER NOT NULL,
  sort_order   INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_products_cat ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_sizes_product ON product_sizes(product_id);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def _row_to_product(row, sizes):
    return {
        "id": row["id"],
        "category_id": row["category_id"],
        "name": {"ru": row["name_ru"], "uz": row["name_uz"]},
        "desc": {"ru": row["desc_ru"] or "", "uz": row["desc_uz"] or ""},
        "ingredients": {
            "ru": json.loads(row["ingredients_ru"] or "[]"),
            "uz": json.loads(row["ingredients_uz"] or "[]"),
        },
        "tag": {"ru": row["tag_ru"] or "", "uz": row["tag_uz"] or ""},
        "img": row["img"],
        "volume_note": row["volume_note"],
        "sizes": sizes,
    }


def all_categories():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM categories ORDER BY sort_order, id"
        ).fetchall()
        return [
            {
                "id": r["id"],
                "name": {"ru": r["name_ru"], "uz": r["name_uz"]},
                "icon": r["icon"],
            }
            for r in rows
        ]


def all_products():
    with get_conn() as conn:
        prod_rows = conn.execute(
            "SELECT * FROM products ORDER BY sort_order, id"
        ).fetchall()
        size_rows = conn.execute(
            "SELECT * FROM product_sizes ORDER BY product_id, sort_order, id"
        ).fetchall()

        sizes_by_pid = {}
        for s in size_rows:
            sizes_by_pid.setdefault(s["product_id"], []).append(
                {
                    "label": s["size_label"],
                    "kind": s["size_kind"],
                    "price": s["price"],
                }
            )

        return [_row_to_product(r, sizes_by_pid.get(r["id"], [])) for r in prod_rows]


def product_by_id(pid):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE id = ?", (pid,)
        ).fetchone()
        if not row:
            return None
        sizes = conn.execute(
            "SELECT * FROM product_sizes WHERE product_id = ? ORDER BY sort_order, id",
            (pid,),
        ).fetchall()
        return _row_to_product(
            row,
            [
                {"label": s["size_label"], "kind": s["size_kind"], "price": s["price"]}
                for s in sizes
            ],
        )


def insert_category(cat):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO categories (id, name_ru, name_uz, icon, sort_order) "
            "VALUES (?, ?, ?, ?, ?)",
            (cat["id"], cat["name_ru"], cat["name_uz"], cat["icon"], cat["sort_order"]),
        )


def insert_product(p):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO products
               (id, category_id, name_ru, name_uz, desc_ru, desc_uz,
                ingredients_ru, ingredients_uz, tag_ru, tag_uz, img,
                volume_note, sort_order)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                p["id"], p["category_id"],
                p["name_ru"], p["name_uz"],
                p.get("desc_ru", ""), p.get("desc_uz", ""),
                json.dumps(p.get("ingredients_ru", []), ensure_ascii=False),
                json.dumps(p.get("ingredients_uz", []), ensure_ascii=False),
                p.get("tag_ru", ""), p.get("tag_uz", ""),
                p["img"],
                p.get("volume_note"),
                p.get("sort_order", 0),
            ),
        )
        conn.execute("DELETE FROM product_sizes WHERE product_id = ?", (p["id"],))
        for i, s in enumerate(p.get("sizes", [])):
            conn.execute(
                "INSERT INTO product_sizes (product_id, size_label, size_kind, price, sort_order) "
                "VALUES (?, ?, ?, ?, ?)",
                (p["id"], str(s["label"]), s.get("kind", "ml"), int(s["price"]), i),
            )


def reset():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()


# ---------- CRUD helpers ----------

def list_categories_raw():
    """Return categories as plain dicts ready for forms."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM categories ORDER BY sort_order, id"
        ).fetchall()
        return [dict(r) for r in rows]


def category_by_id(cid):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (cid,)).fetchone()
        return dict(row) if row else None


def delete_category(cid):
    with get_conn() as conn:
        # Will cascade only if FK on; products keep cid but we'd rather block.
        n = conn.execute(
            "SELECT COUNT(*) AS c FROM products WHERE category_id = ?", (cid,)
        ).fetchone()["c"]
        if n:
            return False, f"Category has {n} products"
        conn.execute("DELETE FROM categories WHERE id = ?", (cid,))
        return True, ""


def list_products_raw():
    """Returns flat list of products with bilingual fields + sizes attached."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT p.*, c.name_ru AS cat_name_ru, c.name_uz AS cat_name_uz "
            "FROM products p LEFT JOIN categories c ON c.id = p.category_id "
            "ORDER BY p.sort_order, p.id"
        ).fetchall()
        size_rows = conn.execute(
            "SELECT * FROM product_sizes ORDER BY product_id, sort_order, id"
        ).fetchall()
        sizes_by = {}
        for s in size_rows:
            sizes_by.setdefault(s["product_id"], []).append(dict(s))

        out = []
        for r in rows:
            d = dict(r)
            d["sizes"] = sizes_by.get(r["id"], [])
            out.append(d)
        return out


def product_raw(pid):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        if not row:
            return None
        sizes = conn.execute(
            "SELECT * FROM product_sizes WHERE product_id = ? ORDER BY sort_order, id",
            (pid,),
        ).fetchall()
        d = dict(row)
        d["sizes"] = [dict(s) for s in sizes]
        return d


def delete_product(pid):
    with get_conn() as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (pid,))


def slugify(text, fallback="item"):
    """Crude ASCII slug generator for product/category ids."""
    import re
    s = (text or "").lower().strip()
    # Cyrillic transliteration map (rough)
    table = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
        "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
        "ў": "o", "ғ": "g", "қ": "q", "ҳ": "h", "’": "", "‘": "",
    }
    out = []
    for ch in s:
        out.append(table.get(ch, ch))
    s = "".join(out)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or fallback


def unique_id_for_product(base):
    """Return base or base-2, base-3, … if taken."""
    with get_conn() as conn:
        i = 1
        candidate = base
        while True:
            row = conn.execute(
                "SELECT 1 FROM products WHERE id = ? LIMIT 1", (candidate,)
            ).fetchone()
            if not row:
                return candidate
            i += 1
            candidate = f"{base}-{i}"


def unique_id_for_category(base):
    with get_conn() as conn:
        i = 1
        candidate = base
        while True:
            row = conn.execute(
                "SELECT 1 FROM categories WHERE id = ? LIMIT 1", (candidate,)
            ).fetchone()
            if not row:
                return candidate
            i += 1
            candidate = f"{base}-{i}"


def stats():
    with get_conn() as conn:
        cats = conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"]
        prods = conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
        return {"categories": cats, "products": prods}

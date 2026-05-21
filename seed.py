"""Seed the SQLite DB with categories and products."""
from db import reset, insert_category, insert_product
from seed_data import CATEGORIES, PRODUCTS


def run():
    reset()
    for i, c in enumerate(CATEGORIES):
        insert_category(c)
    for i, p in enumerate(PRODUCTS):
        p.setdefault("sort_order", i)
        insert_product(p)
    print(f"Seeded {len(CATEGORIES)} categories and {len(PRODUCTS)} products.")


if __name__ == "__main__":
    run()

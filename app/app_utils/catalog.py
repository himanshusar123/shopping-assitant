# Product catalog data and helpers for the Shopping Assistant

PRODUCTS = [
    {
        "id": "E101",
        "name": "QuantumSound Wireless Headphones",
        "category": "Electronics",
        "price": 129.99,
        "description": "Active noise-cancelling headphones with 40-hour battery life and high-fidelity sound.",
        "stock": 25,
    },
    {
        "id": "E102",
        "name": "SmartTrack Fitness Band",
        "category": "Electronics",
        "price": 49.99,
        "description": "Heart rate monitoring, sleep tracking, step counting, and IP68 water resistance.",
        "stock": 10,
    },
    {
        "id": "C201",
        "name": "EcoSoft Organic Cotton Hoodie",
        "category": "Clothing",
        "price": 59.99,
        "description": "Super soft, fleece-lined unisex hoodie made from 100% organic cotton.",
        "stock": 50,
    },
    {
        "id": "C202",
        "name": "FlexStride Running Shoes",
        "category": "Clothing",
        "price": 89.99,
        "description": "Lightweight, breathable running sneakers with responsive cushioning and grip.",
        "stock": 15,
    },
    {
        "id": "B301",
        "name": "The Agentic Future",
        "category": "Books",
        "price": 19.99,
        "description": "An insightful guide on how AI agents are transforming coding, workflows, and industry.",
        "stock": 100,
    },
    {
        "id": "B302",
        "name": "Vibe Coding: The Art of Generative Development",
        "category": "Books",
        "price": 24.99,
        "description": "Learn the methodology of prompt-driven programming and human-AI pair programming.",
        "stock": 80,
    },
]


def search_catalog(query: str = "", category: str | None = None) -> list[dict]:
    """Helper function to filter and search the products list."""
    results = []
    q = query.lower().strip()
    cat = category.lower().strip() if category else None

    for product in PRODUCTS:
        # Category filter
        if cat and product["category"].lower() != cat:
            continue

        # Text search (name or description)
        if q:
            if (
                q not in product["name"].lower()
                and q not in product["description"].lower()
            ):
                continue

        results.append(product)

    return results


def get_by_id(product_id: str) -> dict | None:
    """Helper function to fetch product by its ID."""
    pid = product_id.upper().strip()
    for product in PRODUCTS:
        if product["id"] == pid:
            return product
    return None

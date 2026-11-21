
from IPython.display import display, HTML
import pandas as pd
from html import escape

def display_bundles(solutions):
    
    css = """
    <style>
    .shop-wrapper {
        font-family: Arial, sans-serif;
        color: #f5f5f5;
        background: #000000;
        max-width: 1150px;
        margin: auto;
        padding: 20px;
        border-radius: 16px;
    }

    .shop-heading {
        font-size: 27px;
        font-weight: 750;
        color: #ffffff;
        margin: 15px 0 6px;
    }

    .shop-subheading {
        color: #a1a1aa;
        margin-bottom: 25px;
        font-size: 14px;
    }

    .bundle-card {
        background: #111111;
        border: 1px solid #292929;
        border-radius: 16px;
        padding: 22px;
        margin: 22px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.4);
    }

    .bundle-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 10px;
        margin-bottom: 20px;
    }

    .bundle-title {
        font-size: 20px;
        font-weight: 700;
        color: white;
    }

    .bundle-count {
        background: #252525;
        color: #d4d4d8;
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 12px;
    }

    .product-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 18px;
    }

    .product-card {
        background: #1a1a1a;
        border: 1px solid #303030;
        border-radius: 13px;
        padding: 14px;
        transition: 0.2s;
        min-width: 0;
    }

    .product-card:hover {
        border-color: #525252;
        box-shadow: 0 5px 18px rgba(0,0,0,0.5);
        transform: translateY(-3px);
    }

    .image-area {
        height: 190px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #ffffff;
        border-radius: 10px;
        margin-bottom: 13px;
    }

    .product-image {
        max-width: 100%;
        max-height: 180px;
        object-fit: contain;
    }

    .category-label {
        color: #a1a1aa;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }

    .product-title {
        font-size: 14px;
        font-weight: 650;
        line-height: 1.5;
        min-height: 42px;
        margin: 5px 0 10px;
        color: #f5f5f5;
    }

    .rating {
        font-size: 12px;
        color: #fbbf24;
        margin-bottom: 12px;
    }

    .price {
        font-size: 21px;
        font-weight: 750;
        color: #4ade80;
    }

    .old-price {
        color: #888888;
        font-size: 12px;
        text-decoration: line-through;
        margin-left: 7px;
    }

    .amazon-link {
        display: block;
        text-align: center;
        text-decoration: none !important;
        background: #292929;
        color: #ffffff !important;
        border-radius: 8px;
        padding: 10px;
        margin-top: 14px;
        font-size: 12px;
        font-weight: 650;
    }

    .amazon-link:hover {
        background: #404040;
    }

    .bundle-footer {
        border-top: 1px solid #333333;
        margin-top: 22px;
        padding-top: 18px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 12px;
    }

    .total-label {
        color: #a1a1aa;
        font-size: 13px;
    }

    .total-price {
        color: #4ade80;
        font-size: 25px;
        font-weight: 800;
    }
    </style>
    """


    html = css + """
    <div class="shop-wrapper">
        <div class="shop-heading">Your Shopping Bundles</div>
        <div class="shop-subheading">
            Explore recommended product combinations
        </div>
    """

    for i, bundle in enumerate(solutions, 1):

        total = 0
        products_html = ""

        for key, product in bundle.items():

            if isinstance(product, pd.Series):
                product = product.to_dict()

            title = escape(str(product.get("title", "Product")))
            category = escape(str(product.get("category_name", "General")))

            product_id=product.get("asin","")
            image = product.get("imgUrl", "")
            url = product.get("productURL", "")

            price = float(product.get("price_inr", 0) or 0)
            total += price

            stars = product.get("stars", "N/A")
            reviews = product.get("reviews", 0)
            old_price = product.get("listPrice")

            image_html = (
                f'<img class="product-image" '
                f'src="{escape(image, quote=True)}" '
                f'alt="{title}" loading="lazy">'
                if isinstance(image, str) and image.startswith("https://")
                else '<span style="color:#999">Image unavailable</span>'
            )

            old_price_html = ""
            if old_price is not None and pd.notna(old_price):
                try:
                    old_price = float(old_price)
                    if old_price > price:
                        old_price_html = (
                            f'<span class="old-price">'
                            f'₹{old_price:,.2f}</span>'
                        )
                except (ValueError, TypeError):
                    pass

            link_html = (
                f'<a class="amazon-link" '
                f'href="{escape(url, quote=True)}" target="_blank">'
                'View Product on Amazon ↗</a>'
                if isinstance(url, str) and url.startswith("https://")
                else ""
            )

            products_html += f"""
            <div class="product-card">
                <div class="image-area">{image_html}</div>
                <div class="category-label">{category}</div>
                <div class="product-title">{title}</div>
                <div class="category-label">{product_id}</div>
                <div class="rating">
                    ★ {escape(str(stars))} &nbsp;|&nbsp;
                    {escape(str(reviews))} reviews
                </div>
                <div>
                    <span class="price">₹{price:,.2f}</span>
                    {old_price_html}
                </div>
                {link_html}
            </div>
            """

        html += f"""
        <div class="bundle-card">
            <div class="bundle-header">
                <div class="bundle-title">
                    🛍️ Bundle {i}
                </div>
                <div class="bundle-count">
                    {len(bundle)} PRODUCTS
                </div>
            </div>

            <div class="product-grid">
                {products_html}
            </div>

            <div class="bundle-footer">
                <div>
                    <div class="total-label">Total bundle price</div>
                    <div class="total-price">₹{total:,.2f}</div>
                </div>
                <div class="total-label">
                    {len(bundle)} products selected
                </div>
            </div>
        </div>
        """

    html += "</div>"

    display(HTML(html))

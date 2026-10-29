import os
from typing import Any

import requests
import streamlit as st

API_BASE_URL = "http://127.0.0.1:8000"
SEND_URL = f"{API_BASE_URL}/send"
RECEIVE_URL = f"{API_BASE_URL}/recieve"

st.set_page_config(
    page_title="ShopPair | Smart Shopping",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "page" not in st.session_state:
    st.session_state.page = "home"

if "selected_product" not in st.session_state:
    st.session_state.selected_product = None

if "selected_category" not in st.session_state:
    st.session_state.selected_category = None

if "selected_bundle" not in st.session_state:
    st.session_state.selected_bundle = None

# ------------------------------- Styling -------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .stApp { background: #f5f6f7; color: #161616; }
    header[data-testid="stHeader"] { background: transparent; }
    .block-container { padding-top: 1.2rem; max-width: 1400px; }
    .top-strip {
        background: #131921; color: white; padding: 12px 22px;
        border-radius: 12px; display: flex; align-items: center;
        justify-content: space-between; gap: 16px; margin-bottom: 18px;
    }
    .brand { font-size: 1.55rem; font-weight: 800; letter-spacing: -0.8px; }
    .brand span { color: #ffbd69; }
    .top-note { color: #e8e8e8; font-size: .85rem; }
    .hero {
        background: linear-gradient(120deg, #ffffff 0%, #fff8ed 100%);
        border: 1px solid #ece7df; border-radius: 18px;
        padding: 28px 30px; margin-bottom: 20px;
    }
    .eyebrow { text-transform: uppercase; letter-spacing: 1.7px; color: #a65d00;
        font-size: .72rem; font-weight: 800; margin-bottom: 8px; }
    .hero h1 { font-size: clamp(1.8rem, 3vw, 2.65rem); line-height: 1.1;
        letter-spacing: -1.4px; margin: 0 0 10px 0; color: #171717; }
    .hero p { color: #5c5c5c; margin: 0; max-width: 680px; }
    .section-heading { font-size: 1.3rem; font-weight: 800; letter-spacing: -.4px;
        margin: 18px 0 4px 0; }
    .section-sub { color: #6b7280; font-size: .9rem; margin-bottom: 14px; }
    .bundle-card {
        background: white; border: 1px solid #e5e7eb; border-radius: 16px;
        padding: 16px; margin-bottom: 18px; box-shadow: 0 3px 12px rgba(0,0,0,.035);
    }
    .bundle-title { color: #222; font-size: .78rem; text-transform: uppercase;
        letter-spacing: 1px; font-weight: 800; margin-bottom: 12px; }
    .product-name { font-size: .9rem; font-weight: 650; line-height: 1.35;
        min-height: 60px; margin: 9px 0 8px 0; color: #222; }
    .product-category { color: #777; font-size: .76rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: .6px; }
    .product-price { font-size: 1.05rem; font-weight: 800; color: #111; }
    .product-meta { color: #6b7280; font-size: .78rem; margin-top: 4px; }
    .total-row {
        border-top: 1px solid #ececec; margin-top: 14px; padding-top: 14px;
        display: flex; align-items: center; justify-content: space-between; gap: 12px;
    }
    .total-label { color: #626262; font-size: .85rem; }
    .total-price { color: #111; font-size: 1.45rem; font-weight: 800; }
    div.stButton > button, div.stLinkButton > a {
        background: #111111 !important; color: #ffffff !important;
        border: 1px solid #111111 !important; border-radius: 9px !important;
        font-weight: 700 !important; min-height: 42px; width: 100%;
        transition: transform .15s ease, background .15s ease;
    }
    div.stButton > button:hover, div.stLinkButton > a:hover {
        background: #333333 !important; border-color: #333333 !important;
        color: white !important; transform: translateY(-1px);
    }
    div[data-testid="stTextInput"] input {
        border-radius: 10px; min-height: 48px; border-color: #d7d7d7;
    }
    .search-hint { font-size: .8rem; color: #777; margin-top: 5px; }
    .empty-state {
        text-align: center; padding: 35px 20px; border: 1px dashed #d1d5db;
        border-radius: 15px; background: white; color: #666;
    }
    .footer-note { text-align: center; color: #8a8a8a; font-size: .78rem;
        padding: 25px 0 10px 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------- Helpers -------------------------------
def money_inr(value: Any) -> str:
    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return "Price unavailable"


def product_image(product: dict) -> str | None:
    url = product.get("imgUrl")
    return url if isinstance(url, str) and url.startswith(("https://", "http://")) else None


def normalize_bundles(payload: Any) -> list[dict]:
    """Expected shape: {'data': [{'Shoes': {...}, 'Shirts': {...}}, ...]}"""
    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict):
        raw_items = payload.get("data", [])
    else:
        return []

    bundles = []
    for item in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(item, dict):
            continue
        products = [
            (str(category), product)
            for category, product in item.items()
            if isinstance(product, dict)
        ]
        if products:
            total = sum(
                float(product.get("price_inr") or 0)
                for _, product in products
                if isinstance(product.get("price_inr"), (int, float, str))
                and str(product.get("price_inr")).strip() != ""
            )
            bundles.append({"products": products, "total": total})
    return bundles


def search_products(user_prompt: str):
    try:
        # Send prompt using your FastAPI Pydantic model
        response = requests.post(
            f"{API_BASE_URL}/send",
            json={
                "data": {},
                "user_prompt": user_prompt
            },
            timeout=30
        )
        response.raise_for_status()

        # Fetch generated product combinations
        response = requests.get(
            f"{API_BASE_URL}/recieve",
            timeout=120
        )
        response.raise_for_status()

        return normalize_bundles(response.json())

    except requests.exceptions.RequestException as exc:
        st.error(f"API request failed: {exc}")
        return []


# ---------------- Product Details Page ----------------
if st.session_state.page == "product":
    product = st.session_state.selected_product
    category = st.session_state.selected_category

    if st.button("← Back to Results"):
        st.session_state.page = "home"
        st.rerun()

    if product:
        st.title(product.get("title", "Product Details"))

        left, right = st.columns([1, 1])

        with left:
            image_url = product.get("imgUrl")
            if image_url:
                st.image(image_url, use_container_width=True)

        with right:
            st.caption(category)
            st.subheader(product.get("title", "Untitled Product"))
            st.write(f"**Price:** {money_inr(product.get('price_inr'))}")
            st.write(f"**Rating:** ★ {product.get('stars', 'N/A')}")
            st.write(f"**Reviews:** {product.get('reviews', 0)}")
            st.write(f"**ASIN:** {product.get('asin', 'N/A')}")

    st.stop()


# ---------------- Bundle Details Page ----------------
if st.session_state.page == "bundle":
    bundle = st.session_state.selected_bundle

    if st.button("← Back to Results"):
        st.session_state.page = "home"
        st.rerun()

    if bundle:
        st.title("Your Product Bundle")
        st.write("Review all products included in this combination.")

        products = bundle["products"]
        columns = st.columns(len(products), gap="large")

        for column, (category, product) in zip(columns, products):
            with column:
                st.subheader(category)

                image_url = product.get("imgUrl")
                if image_url:
                    st.image(image_url, use_container_width=True)

                st.write(product.get("title", "Untitled Product"))
                st.markdown(
                    f"### {money_inr(product.get('price_inr'))}"
                )
                st.caption(
                    f"Rating: ★ {product.get('stars', 'N/A')}"
                )

        st.divider()
        st.subheader(
            f"Total: {money_inr(bundle['total'])}"
        )

    st.stop()


# ------------------------------- Header -------------------------------
st.markdown(
    """
    <div class="top-strip">
      <div class="brand">Shop<span>Pair</span></div>
      <div class="top-note">Discover products. Compare bundles. Shop smarter.</div>
    </div>
    <div class="hero">
      <div class="eyebrow">Smart shopping, made simple</div>
      <h1>Tell us what you're looking for.</h1>
      <p>Describe your needs in plain English and discover curated product pairs with clear prices and one combined total.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------- Search -------------------------------
with st.form("shopping_search_form", clear_on_submit=False):
    left, right = st.columns([5, 1], vertical_alignment="bottom")
    with left:
        prompt = st.text_input(
            "What do you want to shop for?",
            placeholder="e.g. Comfortable work shoes and basic white t-shirts under ₹8,000",
            label_visibility="collapsed",
        )
    with right:
        submitted = st.form_submit_button("Search products", use_container_width=True)

st.markdown(
    '<div class="search-hint">Tip: include your use case, preferred style, budget, size, or any must-have features.</div>',
    unsafe_allow_html=True,
)

if "bundles" not in st.session_state:
    st.session_state.bundles = []
if "last_prompt" not in st.session_state:
    st.session_state.last_prompt = ""

if submitted:
    if not prompt.strip():
        st.warning("Enter a search prompt first.")
    else:
        st.session_state.last_prompt = prompt.strip()
        with st.spinner("Finding matching products…"):
            st.session_state.bundles = search_products(prompt.strip())

bundles = st.session_state.bundles

# ------------------------------- Results -------------------------------
if st.session_state.last_prompt:
    st.markdown(
        f'<div class="section-heading">Results for your search</div>'
        f'<div class="section-sub">Prompt: “{st.session_state.last_prompt}”</div>',
        unsafe_allow_html=True,
    )

if bundles:
    st.caption(f"{len(bundles)} product bundle{'s' if len(bundles) != 1 else ''} found")
    # Each object in data is one bundle, typically containing Shoes + Shirts.
    for bundle_index, bundle in enumerate(bundles, start=1):
        products = bundle["products"]
        st.markdown('<div class="bundle-card">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="bundle-title">Bundle {bundle_index} · {len(products)} items</div>',
            unsafe_allow_html=True,
        )

        columns = st.columns(len(products), gap="large")
        for column, (category, product) in zip(columns, products):
            with column:
                image_url = product_image(product)
                if image_url:
                    st.markdown(
                        """
                        <style>
                        div[data-testid="stImage"] img {
                            width: 100%;
                            height: 220px;
                            object-fit: contain;
                            background-color: #ffffff;
                            border-radius: 8px;
                        }
                        </style>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.image(image_url, use_container_width=True)
                else:
                    st.markdown(
                        '<div class="empty-state">Image unavailable</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    f'<div class="product-category">{category}</div>',
                    unsafe_allow_html=True,
                )
                title = str(product.get("title") or "Untitled product")
                st.markdown(
                    f'<div class="product-name">{title}</div>',
                    unsafe_allow_html=True,
                )

                stars = product.get("stars")
                reviews = product.get("reviews")
                if isinstance(stars, (int, float)):
                    st.markdown(
                        f'<div class="product-meta">★ {stars:.1f} '
                        f'· {reviews if reviews is not None else 0} reviews</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(
                    f'<div class="product-price">{money_inr(product.get("price_inr"))}</div>',
                    unsafe_allow_html=True,
                )
                original = product.get("listPrice")
                if isinstance(original, (int, float)) and original > 0:
                    st.markdown(
                        f'<div class="product-meta">Listed price: {money_inr(original)}</div>',
                        unsafe_allow_html=True,
                    )
                if st.button(
                        "View Product",
                        key=f"view_product_{bundle_index}_{category}",
                        use_container_width=True,):
                    st.session_state.selected_product = product
                    st.session_state.selected_category = category
                    st.session_state.page = "product"
                    st.rerun()

        st.markdown(
            f"""
            <div class="total-row">
              <div>
                <div class="total-label">Combined bundle price</div>
                <div class="total-price">{money_inr(bundle["total"])}</div>
              </div>
              <div style="color:#777;font-size:.82rem;text-align:right;">
                {len(products)} items · Prices shown in INR
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # A black call-to-action for the whole bundle. Since checkout is not
        # implemented by this API, it opens the first item; individual item links
        # above allow users to open each product.
        first_product = products[0][1]
        if st.button(
            "View Bundle",
            key=f"view_bundle_{bundle_index}",
            use_container_width=True,
        ):
            st.session_state.selected_bundle = bundle
            st.session_state.page = "bundle"
            st.rerun()

elif st.session_state.last_prompt:
    st.markdown(
        """
        <div class="empty-state">
          <h3>No product bundles to show yet</h3>
          <p>Try a broader prompt, or check whether your backend returned a non-empty <code>data</code> array.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <div class="empty-state">
          <h3>Your next great find starts here.</h3>
          <p>Search for a product combination to see images, item prices, ratings, and the combined INR total.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="footer-note">ShopPair is a shopping discovery interface. Product availability and final prices are determined by the retailer.</div>',
    unsafe_allow_html=True,
)

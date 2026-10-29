import re
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="ShopSmart | Product Search",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------- Styling ---------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: Inter, sans-serif; }
    .stApp { background: #f4f6f8; }
    header[data-testid="stHeader"] { background: #172337; }
    .shop-header {
        background: #172337; color: white; padding: 18px 24px;
        border-radius: 12px; margin-bottom: 16px;
    }
    .shop-brand { font-size: 28px; font-weight: 800; letter-spacing: -1px; }
    .shop-brand span { color: #ffb84d; }
    .shop-sub { color: #d7dfeb; font-size: 13px; margin-top: 3px; }
    .search-hint { color: #5e6a7a; font-size: 13px; margin: 4px 0 14px; }
    .result-heading { font-size: 22px; font-weight: 750; color: #172337; }
    .muted { color: #64748b; font-size: 13px; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: white; border: 1px solid #e5e9ef; border-radius: 12px;
    }
    .product-title {
        font-size: 15px; font-weight: 600; line-height: 1.4;
        color: #1d2939; min-height: 42px;
    }
    .product-price { font-size: 23px; font-weight: 800; color: #b12704; }
    .product-meta { font-size: 12px; color: #667085; margin: 4px 0; }
    .best-seller {
        display: inline-block; background: #fff0cc; color: #7a4b00;
        font-size: 11px; font-weight: 700; padding: 4px 7px; border-radius: 5px;
        margin: 3px 0 8px;
    }
    div.stButton > button { border-radius: 8px; font-weight: 600; }
    a { text-decoration: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

REQUIRED_COLUMNS = [
    "asin", "title", "imgUrl", "productURL", "stars", "reviews", "price",
    "listPrice", "category_id", "isBestSeller", "boughtInLastMonth", "price_inr"
]


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def to_number(series):
    # Handles numeric columns that may have been stored as strings with symbols/commas.
    return pd.to_numeric(
        series.astype(str).str.replace(r"[₹,$,\s]", "", regex=True),
        errors="coerce",
    )


def parse_bool(value):
    if isinstance(value, bool):
        return value
    return clean_text(value).lower() in {"true", "1", "yes", "y"}


@st.cache_data(show_spinner=False)
def load_csv(uploaded_bytes, file_name):
    from io import BytesIO
    df = pd.read_csv(BytesIO(uploaded_bytes))
    return prepare_data(df)


@st.cache_data(show_spinner=False)
def load_csv_path(path, modified_time):
    return prepare_data(pd.read_csv(path))


def prepare_data(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))

    for col in ["title", "imgUrl", "productURL", "asin"]:
        df[col] = df[col].map(clean_text)

    for col in ["stars", "reviews", "price", "listPrice", "category_id",
                "boughtInLastMonth", "price_inr"]:
        df[col] = to_number(df[col])

    df["isBestSeller"] = df["isBestSeller"].map(parse_bool)
    df["title_lower"] = df["title"].str.lower()
    df["display_price"] = df["price_inr"].where(df["price_inr"].notna(), df["price"])
    df["display_price"] = pd.to_numeric(df["display_price"], errors="coerce")
    df = df[df["title"].ne("")].reset_index(drop=True)
    return df


def keyword_search(df, query):
    """Keyword matching in product titles. All query terms must appear for a strong match;
    if no all-term match exists, show products matching at least one term."""
    query = query.strip().lower()
    if not query:
        return df.copy()

    terms = [t for t in re.findall(r"[\w]+", query) if t]
    if not terms:
        return df.copy()

    title = df["title_lower"].fillna("")
    all_mask = pd.Series(True, index=df.index)
    for term in terms:
        all_mask &= title.str.contains(re.escape(term), regex=True, na=False)

    matches = df[all_mask].copy()
    if not matches.empty:
        matches["match_quality"] = len(terms)
        return matches

    any_mask = pd.Series(False, index=df.index)
    for term in terms:
        any_mask |= title.str.contains(re.escape(term), regex=True, na=False)

    matches = df[any_mask].copy()
    if not matches.empty:
        matches["match_quality"] = matches["title_lower"].apply(
            lambda t: sum(term in t for term in terms)
        )
    return matches


def money(value):
    if pd.isna(value):
        return "Price unavailable"
    return "₹{:,.0f}".format(float(value))


# ----------------------------- Header ----------------------------------
st.markdown(
    """
    <div class="shop-header">
      <div class="shop-brand">Shop<span>Smart</span> 🛍️</div>
      <div class="shop-sub">Discover products from your catalog • Search by product name or keywords</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------- Data source -----------------------------
with st.sidebar:
    st.markdown("## 🧭 Shop filters")
    st.caption("Load your Amazon products CSV to get started.")
    uploaded_file = st.file_uploader("Upload products CSV", type=["csv"])
    default_path = st.text_input(
        "Or enter CSV file path",
        value="Data/amazon_products.csv",
        help="Example: AI_Project/Data/amazon_products.csv",
    )

df = None
load_error = None
try:
    if uploaded_file is not None:
        df = load_csv(uploaded_file.getvalue(), uploaded_file.name)
    elif default_path and Path(default_path).is_file():
        path = Path(default_path)
        df = load_csv_path(str(path.resolve()), path.stat().st_mtime)
except Exception as exc:
    load_error = str(exc)

if df is None:
    st.info("Upload your product CSV in the sidebar, or enter the correct path to your CSV file.")
    if load_error:
        st.error(f"Could not load the CSV: {load_error}")
    st.markdown(
        """
        **Expected columns:** `asin`, `title`, `imgUrl`, `productURL`, `stars`,
        `reviews`, `price`, `listPrice`, `category_id`, `isBestSeller`,
        `boughtInLastMonth`, `price_inr`.

        Save this file as `app.py`, then run:
        ```bash
        pip install streamlit pandas
        streamlit run app.py
        ```
        """
    )
    st.stop()

if df.empty:
    st.warning("The CSV loaded successfully, but it contains no products with a title.")
    st.stop()

# ----------------------------- Search bar ------------------------------
col_search, col_clear = st.columns([8, 1])
with col_search:
    query = st.text_input(
        "Search products",
        placeholder="Try: wireless mouse, white shirt, running shoes...",
        label_visibility="collapsed",
        key="product_search",
    )
with col_clear:
    if st.button("Clear", use_container_width=True):
        st.session_state["product_search"] = ""
        st.rerun()

st.markdown(
    '<div class="search-hint">Search uses keyword matching against product titles. '
    'Try a few product words for broader results.</div>',
    unsafe_allow_html=True,
)

# ----------------------------- Sidebar filters -------------------------
with st.sidebar:
    st.divider()
    st.markdown("### Refine results")

    price_series = df["display_price"].dropna()
    if not price_series.empty:
        min_price = max(0.0, float(price_series.min()))
        max_price = float(price_series.max())
        if min_price == max_price:
            selected_prices = (min_price, max_price)
            st.caption(f"Price: {money(min_price)}")
        else:
            selected_prices = st.slider(
                "Price range (₹)",
                min_value=float(min_price),
                max_value=float(max_price),
                value=(float(min_price), float(max_price)),
                step=max(1.0, round((max_price - min_price) / 100, 0)),
            )
    else:
        selected_prices = None
        st.caption("No numeric prices found.")

    rating_values = df["stars"].dropna()
    min_rating_option = st.selectbox(
        "Minimum rating",
        options=[0, 3, 3.5, 4, 4.5],
        index=0,
        format_func=lambda x: "Any rating" if x == 0 else f"{x}★ and above",
    )

    best_seller_only = st.checkbox("Best sellers only", value=False)

    category_values = sorted(df["category_id"].dropna().unique().tolist())
    selected_categories = st.multiselect(
        "Category IDs",
        options=category_values,
        format_func=lambda x: str(int(x)) if float(x).is_integer() else str(x),
        help="Choose one or more category IDs, or leave empty for all categories.",
    )

    sort_by = st.selectbox(
        "Sort by",
        [
            "Best match",
            "Popularity (bought recently)",
            "Customer rating",
            "Price: low to high",
            "Price: high to low",
            "Most reviewed",
        ],
    )

# ----------------------------- Filter and rank -------------------------
results = keyword_search(df, query)

if selected_prices is not None:
    results = results[
        results["display_price"].isna()
        | results["display_price"].between(selected_prices[0], selected_prices[1])
    ]
if min_rating_option > 0:
    results = results[results["stars"].fillna(0) >= min_rating_option]
if best_seller_only:
    results = results[results["isBestSeller"]]
if selected_categories:
    results = results[results["category_id"].isin(selected_categories)]

if sort_by == "Best match" and "match_quality" in results.columns:
    results = results.sort_values(
        ["match_quality", "stars", "reviews"],
        ascending=[False, False, False],
        na_position="last",
    )
elif sort_by == "Popularity (bought recently)":
    results = results.sort_values("boughtInLastMonth", ascending=False, na_position="last")
elif sort_by == "Customer rating":
    results = results.sort_values("stars", ascending=False, na_position="last")
elif sort_by == "Price: low to high":
    results = results.sort_values("display_price", ascending=True, na_position="last")
elif sort_by == "Price: high to low":
    results = results.sort_values("display_price", ascending=False, na_position="last")
elif sort_by == "Most reviewed":
    results = results.sort_values("reviews", ascending=False, na_position="last")

# ----------------------------- Results ----------------------------------
left, right = st.columns([3, 1])
with left:
    st.markdown(
        f'<div class="result-heading">{"Results for “" + query + "”" if query else "Explore products"}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="muted">{len(results):,} products found · {len(df):,} products in catalog</div>',
        unsafe_allow_html=True,
    )
with right:
    per_page = st.selectbox("Products per page", [12, 24, 48], index=0)

if results.empty:
    st.warning("No products matched these search terms and filters. Try fewer keywords or relax the filters.")
    st.stop()

total_pages = max(1, (len(results) + per_page - 1) // per_page)
if "page_num" not in st.session_state:
    st.session_state.page_num = 1
st.session_state.page_num = min(st.session_state.page_num, total_pages)

page_col1, page_col2, page_col3 = st.columns([1, 5, 1])
with page_col1:
    if st.button("← Previous", disabled=st.session_state.page_num <= 1):
        st.session_state.page_num -= 1
        st.rerun()
with page_col2:
    st.markdown(
        f'<div class="muted" style="text-align:center;padding-top:8px;">'
        f'Page {st.session_state.page_num} of {total_pages}</div>',
        unsafe_allow_html=True,
    )
with page_col3:
    if st.button("Next →", disabled=st.session_state.page_num >= total_pages):
        st.session_state.page_num += 1
        st.rerun()

start = (st.session_state.page_num - 1) * per_page
page_results = results.iloc[start:start + per_page]

cards = st.columns(4, gap="medium")
for idx, (_, product) in enumerate(page_results.iterrows()):
    with cards[idx % 4]:
        with st.container(border=True):
            img_url = clean_text(product["imgUrl"])
            if img_url.startswith(("https://", "http://")):
                st.image(img_url, use_container_width=True)
            else:
                st.markdown(
                    '<div style="height:170px;display:flex;align-items:center;justify-content:center;'
                    'background:#f8fafc;border-radius:8px;color:#98a2b3;">No image available</div>',
                    unsafe_allow_html=True,
                )

            title = clean_text(product["title"])
            st.markdown(f'<div class="product-title">{title}</div>', unsafe_allow_html=True)

            if parse_bool(product["isBestSeller"]):
                st.markdown('<span class="best-seller">BEST SELLER</span>', unsafe_allow_html=True)

            st.markdown(
                f'<div class="product-price">{money(product["display_price"])}</div>',
                unsafe_allow_html=True,
            )

            list_price = product["listPrice"]
            price = product["display_price"]
            if pd.notna(list_price) and pd.notna(price) and float(list_price) > float(price) > 0:
                discount = round((float(list_price) - float(price)) / float(list_price) * 100)
                st.markdown(
                    f'<div class="product-meta"><s>{money(list_price)}</s> · {discount}% off</div>',
                    unsafe_allow_html=True,
                )

            stars = product["stars"]
            reviews = product["reviews"]
            rating_text = f"⭐ {float(stars):.1f}" if pd.notna(stars) else "No rating"
            review_text = f"{int(reviews):,} reviews" if pd.notna(reviews) else "No reviews"
            st.markdown(
                f'<div class="product-meta">{rating_text} &nbsp; | &nbsp; {review_text}</div>',
                unsafe_allow_html=True,
            )

            bought = product["boughtInLastMonth"]
            if pd.notna(bought) and bought > 0:
                st.markdown(
                    f'<div class="product-meta">{int(bought):,}+ bought recently</div>',
                    unsafe_allow_html=True,
                )

            product_url = clean_text(product["productURL"])
            if product_url.startswith(("https://", "http://")):
                st.link_button("View product ↗", product_url, use_container_width=True)
            else:
                st.button(
                    "Product link unavailable",
                    key=f"unavailable_{product['asin']}_{start + idx}",
                    disabled=True,
                    use_container_width=True,
                )

st.caption("Product data and availability come from your CSV and linked product pages. Prices may change on the retailer's website.")

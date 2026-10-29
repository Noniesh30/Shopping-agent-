import re
import pandas as pd
import unicodedata

def normalize_text(text):
    text = unicodedata.normalize("NFKC", str(text)).lower()
    text = re.sub(r"[-_/]+", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def matches_term(title, term):
    title = normalize_text(title)
    term = normalize_text(term)

    if not term:
        return False

    pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
    return bool(re.search(pattern, title))

def search_products(domain, item):
    domain = domain.copy()
    titles = domain["title"].fillna("").map(normalize_text)

    keywords = item.get("keywords") or []
    preferences = item.get("preferences") or []

    # Match any keyword using whole-word matching
    if keywords:
        patterns = [
            r"(?<!\w)" + re.escape(normalize_text(k)) + r"(?!\w)"
            for k in keywords if normalize_text(k)
        ]

        if patterns:
            pattern = "|".join(patterns)
            mask = titles.str.contains(pattern, regex=True, na=False)
            domain = domain.loc[mask].copy()
            titles = titles.loc[domain.index]

    # Rank products by the number of matched preferences
    if preferences:
        domain["preference_matches"] = [
            sum(matches_term(title, pref) for pref in preferences)
            for title in titles
        ]

        domain = domain.sort_values(
            "preference_matches",
            ascending=False,
            kind="stable"
        )

    return domain
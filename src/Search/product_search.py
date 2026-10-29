
import re
import pandas as pd
import unicodedata

def normalize_text(text):
    text = unicodedata.normalize("NFKC", str(text)).lower()
    text = re.sub(r"[-_/]+", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def word_variants(word):
    variants = {word}

    # Common English plural forms
    if len(word) > 3 and word.endswith("ies"):
        variants.add(word[:-3] + "y")

    if len(word) > 3 and word.endswith("es"):
        variants.add(word[:-2])

    if len(word) > 2 and word.endswith("s") and not word.endswith("ss"):
        variants.add(word[:-1])

    return variants

def matches_term(title, term):
    title_words = normalize_text(title).split()
    term_words = normalize_text(term).split()

    if not term_words:
        return False

    # Match a word or phrase, allowing common plural differences
    title_variants = [word_variants(w) for w in title_words]
    term_variants = [word_variants(w) for w in term_words]

    for i in range(len(title_words) - len(term_words) + 1):
        matched = all(
            title_variants[i + j] & term_variants[j]
            for j in range(len(term_words))
        )
        if matched:
            return True

    return False

def search_products(domain, item):
    domain = domain.copy()
    titles = domain["title"].fillna("").map(normalize_text)

    keywords = item.get("keywords") or []
    preferences = item.get("preferences") or []

    # Require ALL keywords to match (AND logic)
    valid_keywords = [
        normalize_text(k) for k in keywords if normalize_text(k)
    ]

    if valid_keywords:
        mask = pd.Series(True, index=domain.index)

        for keyword in valid_keywords:
            keyword_mask = pd.Series(
                [
                    matches_term(title, keyword)
                    for title in titles
                ],
                index=domain.index
            )
            mask &= keyword_mask

        domain = domain.loc[mask].copy()
        titles = titles.loc[domain.index]

    # Rank products by the number of matched preferences
    valid_preferences = [
        normalize_text(p)
        for p in preferences if normalize_text(p)
    ]

    if valid_preferences:
        domain["preference_matches"] = [
            sum(
                matches_term(title, pref)
                for pref in valid_preferences
            )
            for title in titles
        ]

        domain = domain.sort_values(
            "preference_matches",
            ascending=False,
            kind="stable"
        )

    return domain

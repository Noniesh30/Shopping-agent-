
def reorder_bundles(solutions):
    if len(solutions) <= 1:
        return solutions

    # Extract unique product ASINs from each bundle
    bundle_products = []

    for bundle in solutions:
        products = set()

        for product in bundle.values():
            if hasattr(product, "get"):
                asin = product.get("asin")
                if asin is not None:
                    products.add(asin)

        bundle_products.append(products)

    remaining = list(range(len(solutions)))
    ordered_indexes = []

    # Start with the first bundle
    current = remaining.pop(0)
    ordered_indexes.append(current)

    while remaining:
        previous_products = bundle_products[current]

        # Prefer bundles with no common products
        next_index = min(
            remaining,
            key=lambda idx: (
                len(previous_products & bundle_products[idx]),
                -len(bundle_products[idx]),
                idx
            )
        )

        ordered_indexes.append(next_index)
        remaining.remove(next_index)
        current = next_index

    return [solutions[i] for i in ordered_indexes]

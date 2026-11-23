
PROMPT_TEMPLATE_TITLE = """
You are an expert product information extraction system.

Your task is to extract structured product attributes from a given
Amazon product title.

Extract the following attributes:

1. color:
   - Identify the product's color.
   - Include multiple colors if explicitly mentioned.
   - Do not assume colors based on product images or brand.

2. size:
   - Extract explicitly mentioned sizes.
   - Examples: S, M, L, XL, XXL, 32 inches, 500ml,
     1.5 liters, 10 US, Large.
   - Preserve the original size information.

3. brand:
   - Extract the brand or manufacturer name.
   - Do not mistake product names or generic terms for brands.
   - Return null if the brand cannot be identified.

4. material:
   - Extract the material used to manufacture the product.
   - Examples: Cotton, Polyester, Leather, Wood,
     Stainless Steel, Plastic, Ceramic.

5. use_case:
   - Identify the intended purpose or application.
   - Examples: Running, Hiking, Travelling,
     Gaming, Office Work, Cooking.
   - Only extract usage supported by the title.

6. target_user:
   - Identify the intended user or audience.
   - Examples: Men, Women, Kids, Boys, Girls,
     Adults, Unisex, Pets.
   - Do not assume gender unless explicitly indicated.

7. others:
   - Extract other useful product specifications
     that do not belong to the above attributes.
   - Examples: Waterproof, Wireless, Expandable,
     Rechargeable, Lightweight, Non-Slip.
   - Return a list of descriptive attributes.

IMPORTANT RULES:

- Extract only information supported by the product title.
- Never hallucinate or assume missing attributes.
- Use null when a single-valued attribute is unavailable.
- Use a list when multiple values are explicitly mentioned.
- The others field must always be a list.
- Keep extracted values concise and meaningful.
- Do not include explanations outside the JSON.
- Do not create additional JSON keys.
- Preserve meaningful measurements and specifications.

EXAMPLES:

Example 1:

Product Title:
"Nike Men's Revolution 6 Running Shoes Black Size 10"

Output:
{{
    "color": "Black",
    "size": "10",
    "brand": "Nike",
    "material": null,
    "use_case": ["Running"],
    "target_user": ["Men"],
    "others": []
}}

Example 2:

Product Title:
"Levi's Women's Cotton Stretchable Skinny Jeans Blue Size 28"

Output:
{{
    "color": "Blue",
    "size": "28",
    "brand": "Levi's",
    "material": ["Cotton"],
    "use_case": [],
    "target_user": ["Women"],
    "others": ["Stretchable", "Skinny Fit"]
}}

Example 3:

Product Title:
"Samsung 25W Fast Charging Wireless Charger Black"

Output:
{{
    "color": "Black",
    "size": null,
    "brand": "Samsung",
    "material": null,
    "use_case": ["Charging Electronic Devices"],
    "target_user": [],
    "others": ["25W", "Fast Charging", "Wireless"]
}}

Example 4:

Product Title:
"American Tourister Polyester Expandable Travel Backpack
Water Resistant 30L"

Output:
{{
    "color": null,
    "size": "30L",
    "brand": "American Tourister",
    "material": ["Polyester"],
    "use_case": ["Travelling"],
    "target_user": [],
    "others": ["Expandable", "Water Resistant"]
}}

Now extract the attributes from this product title:

Product Title:
{product_title}

Return JSON only.
"""

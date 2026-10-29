from sentence_transformers import SentenceTransformer
import pandas as pd 
import numpy as np
import re 

def normalize(text):
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
print("Loading model completed")
folder = "Data\\"
categories = pd.read_csv(folder + "amazon_categories.csv")
categories["normalized_name"] = categories["category_name"].apply(normalize)
category_names = categories["normalized_name"].tolist()


categories["normalized_name"] = categories["category_name"].apply(normalize)
category_names = categories["normalized_name"].tolist()

category_embeddings = model.encode(
    categories["category_name"].tolist(),
    normalize_embeddings=True,
    convert_to_numpy=True,
    show_progress_bar=True
).astype(np.float32)


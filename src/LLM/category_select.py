from src.LLM.embedding import model,category_embeddings,categories
import numpy as np 

def get_top_categories(llm_category, top_k):

    query_embedding = model.encode(
        [llm_category],
        normalize_embeddings=True,
        convert_to_numpy=True
    )[0].astype(np.float32)

    embedding_scores = category_embeddings @ query_embedding

    top_indices = np.argsort(-embedding_scores)[:top_k]

    results = []
    category_ids=[]
    print(f"Top {top_k} categories:")
    print("Category_id          Category_name")
    for idx in top_indices:
        print(int(categories.iloc[idx]["category_id"]),categories.iloc[idx]["category_name"])
        results.append({
            "category_id": int(categories.iloc[idx]["category_id"]),
            "category_name": categories.iloc[idx]["category_name"],
            "embedding_score": round(float(embedding_scores[idx]), 4),
        }) 
        category_ids.append( int(categories.iloc[idx]["category_id"]))
    
    return results,category_ids
from src.LLM.embedding import model,category_embeddings,categories
import numpy as np 

def get_top_categories(llm_category, top_k=5):

    query_embedding = model.encode(
        [llm_category],
        normalize_embeddings=True,
        convert_to_numpy=True
    )[0].astype(np.float32)

    embedding_scores = category_embeddings @ query_embedding

    top_indices = np.argsort(-embedding_scores)[:top_k]

    results = []
    category_ids=[]
    for idx in top_indices:
        results.append({
            "category_id": int(categories.iloc[idx]["id"]),
            "category_name": categories.iloc[idx]["category_name"],
            "embedding_score": round(float(embedding_scores[idx]), 4),
        }) 
        category_ids.append( int(categories.iloc[idx]["id"]))
    
    return results,category_ids
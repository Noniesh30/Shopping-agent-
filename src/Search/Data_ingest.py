import pandas as pd 

def data_ingest():
    print("Ingesting Data")
    folder = "Data\\"
    products = pd.read_csv(folder + "amazon_final.csv")
    categories = pd.read_csv(folder + "amazon_final_category_mapping.csv")

    #Processing Data 
    print("Procesisng Data")
    products.columns = products.columns.str.strip()
    print("Columns:")
    print(products.columns.tolist())
    print("\nNumber of products:", len(products))
    return products,categories
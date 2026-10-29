
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any

app = FastAPI(title="Cross-Platform API")

from src.Search.Data_ingest import data_ingest 
from src.Search.search import Searching
from src.LLM.template import extract_requirements
import pandas as pd

print("Startup Completed")
products,categories=data_ingest()
obj=Searching(products,categories)  

def get_product_solutions(prompt):
    main_template=extract_requirements(prompt)
    print(main_template)
    solutions=obj.finding_products(main_template)
    return solutions


# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:8501",
    "http://127.0.0.1:8501"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temporary storage for received data
data_store = {}

# Request model
class DataRequest(BaseModel):
    data: dict[str, Any]
    user_prompt: str

# Route 1: Receive data from the client
@app.post("/send")
def send_data(request: DataRequest):
    data_store["latest"] = {
        "user_prompt": request.user_prompt
        }

    print("Received prompt:", request.user_prompt)
    return {
        "status": "success",
        "message": "Data received successfully",
    }

# Route 2: Send data to the client
@app.get("/recieve")
def receive_data():
    if "latest" not in data_store:
        return {"data": []}
    prompt= data_store["latest"]["user_prompt"]
    main_template=extract_requirements(prompt)
    print(main_template)
    solutions=obj.finding_products(main_template)

    return {
        "data": solutions
    }

# Health check
@app.get("/")
def home():
    return {"message": "API is running"}

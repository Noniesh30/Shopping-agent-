
import json
import hashlib
import re
import tempfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any

app = FastAPI(title="Cross-Platform API")

#Search Module
from src.Search.Data_ingest import data_ingest 
from src.Search.search import Searching
from src.LLM.template import extract_requirements
import pandas as pd

print("Startup Completed")
products,categories=data_ingest()
obj=Searching(products,categories)

#Memory Module 
from src.Memory.Memory_store import load_user_data,get_registered_user,load_user_memory,write_json_atomically
from src.Memory.Memory_store import user_memory_path,EmailRequest,migrate_legacy_memory,DataRequest,ProductMemoryRequest
from src.Memory.Memory_store import USER_DATA_PATH,MEMORY_DIRECTORY
from src.Memory.Memory_store import buy,click
from src.Memory.Multi import user_data_lock
from src.Memory.Multi import append_preference_memory_record,requirements_by_search_category,inferred_item_from_product,save_user_memory

#Applying Values 
from src.Values.reasoning import Reasoning
reasoning = Reasoning()

#Reinforcement Learning
from src.rl_module.api import ReinforcementLearning
rl = ReinforcementLearning.load()   


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

#Needed
def pass_through_user_memory(
    user_id: str,
    memory_type: str,
    product: dict[str, Any],
    action: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    with user_data_lock:
        try:
            user_data = load_user_data()
            if get_registered_user(user_data, user_id) is None:
                raise HTTPException(status_code=404, detail="User not found.")
            memory_path = user_memory_path(user_id)
            memory = load_user_memory(user_id)

            if memory_type == "click":
                category = product.get("category")
                product_id = product.get("asin") or product.get("id")
                product_name = product.get("title") or product.get("name")
                inferred_record = next(
                    (
                        record for record in reversed(memory["preference_memory"])
                        if record.get("source_type") == "agent_inferred"
                        and (
                            (product_id and record.get("product_id") == product_id)
                            or (
                                not product_id
                                and product_name
                                and record.get("product_name") == product_name
                            )
                        )
                    ),
                    None,
                )
                item = data_store.get(user_id, {}).get(
                    "requirements_by_category",
                    {},
                ).get(category)
                if item is None:
                    item = inferred_item_from_product(product)
                if inferred_record is None:
                    append_preference_memory_record(
                        memory,
                        user_id,
                        item,
                        source_type="agent_inferred",
                        use_freq=0,
                        product=product,
                        bought=False,
                        action=action
                    )
                else:
                    inferred_record["product_id"] = product_id
                    inferred_record["product_name"] = product_name
                    inferred_record["product_details"] = product
                    inferred_record["last_updated_at"] = datetime.now(timezone.utc).isoformat()

            elif memory_type == "buy":
                product_id = product.get("asin") or product.get("id")
                category = product.get("category")
                category_name = (
                    re.sub(r"-\d+$", "", category).replace("-", " ").strip().lower()
                    if isinstance(category, str)
                    else ""
                )
                inferred_record = next(
                    (
                        record for record in reversed(memory["preference_memory"])
                        if record.get("source_type") == "agent_inferred"
                        and (
                            record.get("product_id") == product_id
                            or record.get("product_name") == (
                                product.get("title") or product.get("name")
                            )
                            or (
                                not record.get("product_id")
                                and category_name
                                and str(record.get("name", "")).strip().lower()
                                == category_name
                            )
                        )
                    ),
                    None,
                )
                if inferred_record is None:
                    item = data_store.get(user_id, {}).get(
                        "requirements_by_category",
                        {},
                    ).get(category)
                    if item is None:
                        item = inferred_item_from_product(product)
                    inferred_record = append_preference_memory_record(
                        memory,
                        user_id,
                        item,
                        source_type="agent_inferred",
                        use_freq=0,
                        product=product,
                        bought=True,
                        action=action
                    )
                else:
                    inferred_record["bought"] = True
                    inferred_record["product_id"] = product_id
                    inferred_record["product_name"] = (
                        product.get("title") or product.get("name")
                    )
                    inferred_record["product_details"] = product
                    inferred_record["last_updated_at"] = datetime.now(timezone.utc).isoformat()

            if not isinstance(memory, dict):
                raise ValueError("The memory action must return a JSON object.")
            write_json_atomically(memory_path, memory)
            return memory
        except HTTPException:
            raise
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=500,
                detail="Could not process user memory action.",
            ) from exc


@app.post("/users")
def store_user_email(request: EmailRequest):
    email = request.email.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")

    with user_data_lock:
        try:
            user_data = load_user_data()
            users = user_data["users"]

            user = next((entry for entry in users if entry["email"].lower() == email), None)
            already_registered = user is not None
            if user is None:
                user = {
                    "user_id": email,
                    "email": email,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                users.append(user)
            for entry in users:
                entry_email = entry["email"].strip().lower()
                migrate_legacy_memory(entry, entry_email)

            user_id = email
            write_json_atomically(USER_DATA_PATH, user_data)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=500,
                detail="Could not store the email address.",
            ) from exc

    return {
        "status": "success",
        "message": "Email stored successfully.",
        "already_registered": already_registered,
        "user_id": user_id,
    }


# Route 1: Receive data from the client
@app.post("/send")
def send_data(request: DataRequest):
    with user_data_lock:
        try:
            user_data = load_user_data()
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=500, detail="Could not read registered users.") from exc
        if get_registered_user(user_data, request.user_id) is None:
            raise HTTPException(status_code=404, detail="User not found.")

    data_store[request.user_id] = {"user_prompt": request.user_prompt}

    print("Received prompt:", request.user_prompt)
    return {
        "status": "success",
        "message": "Data received successfully",
    }


@app.post("/memory/click")
def record_product_click(request: ProductMemoryRequest):
    return pass_through_user_memory(
        request.user_id,
        "click",
        request.product,
        click,
    )


@app.post("/memory/buy")
def record_buy_click(request: ProductMemoryRequest):
    return pass_through_user_memory(
        request.user_id,
        "buy",
        request.product,
        buy,
    )


# Route 2: Send data to the client
@app.get("/recieve")
def receive_data(user_id: str):
    if user_id not in data_store:
        return {"data": []}
    prompt = data_store[user_id]["user_prompt"]
    present_promt_records=[]
    try:
        requirements = extract_requirements(prompt)
        present_promt_records=save_user_memory(user_id, requirements)
        data_store[user_id]["requirements_by_category"] = requirements_by_search_category(
            requirements
        )
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=500, detail="Could not save search memory.") from exc

    Memory_applied_records=[]
    if present_promt_records!=[] and present_promt_records is not None:
        print("==========================================")
        print("Before applying Memory actions requirements")
        for records in present_promt_records: # type: ignore
            records={"user_id":user_id,"items":[records]}
            assessed_records=reasoning.add_safe_preferences(records,user_id)
            memeory_action_assigned_records = rl.assign_actions(assessed_records)  
            print("======================================")
            print("After applying memory actions")
            with open("output.json", "w") as file:
                json.dump(memeory_action_assigned_records, file, indent=4)

            
    print(requirements)
    solutions = obj.finding_products(requirements)

    return {
        "data": solutions
    }





# Health check
@app.get("/")
def home():
    return {"message": "API is running"}

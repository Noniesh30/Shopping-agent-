
import json
import hashlib
import re
import tempfile
import threading
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

#Memory Module 
from src.Memory.Memory_store import load_user_data,get_registered_user,load_user_memory,write_json_atomically
from src.Memory.Memory_store import user_memory_path,EmailRequest,migrate_legacy_memory,DataRequest,ProductMemoryRequest
from src.Memory.Memory_store import USER_DATA_PATH,MEMORY_DIRECTORY

print("Startup Completed")
products,categories=data_ingest()
obj=Searching(products,categories)  

user_data_lock = threading.Lock()

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


def append_user_event(user_id: str, memory_type: str, event: dict[str, Any]) -> None:
    memory_key = f"{memory_type}_memory"
    with user_data_lock:
        try:
            user_data = load_user_data()
            if get_registered_user(user_data, user_id) is None:
                raise HTTPException(status_code=404, detail="User not found.")

            memory = load_user_memory(user_id)
            records = memory[memory_key]
            records.append({
                "memory_id": max(
                    (int(record.get("memory_id", 0)) for record in records),
                    default=0,
                ) + 1,
                "user_id": user_id,
                **event,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            write_json_atomically(user_memory_path(user_id), memory)
        except HTTPException:
            raise
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Could not save {memory_type} memory.",
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

    data_store[request.user_id] = {
        "user_prompt": request.user_prompt
    }

    print("Received prompt:", request.user_prompt)
    return {
        "status": "success",
        "message": "Data received successfully",
    }


@app.post("/memory/click")
def record_product_click(request: ProductMemoryRequest):
    append_user_event(
        request.user_id,
        "click",
        {"product": request.product},
    )
    return {"status": "success", "message": "Product click recorded."}


@app.post("/memory/buy")
def record_buy_click(request: ProductMemoryRequest):
    append_user_event(
        request.user_id,
        "buy",
        {"product": request.product},
    )
    return {
        "status": "success",
        "message": "Buy click recorded; retailer purchase is not confirmed.",
    }


# Route 2: Send data to the client
@app.get("/recieve")
def receive_data(user_id: str):
    if user_id not in data_store:
        return {"data": []}
    prompt = data_store[user_id]["user_prompt"]
    try:
        requirements = extract_requirements(prompt)
        save_prompt_memory(user_id, prompt, requirements)
        save_user_memory(user_id, requirements)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=500, detail="Could not save search memory.") from exc
    print(requirements)
    solutions = obj.finding_products(requirements)

    return {
        "data": solutions
    }


def requirement_memory_fields(item: dict[str, Any]) -> dict[str, Any]:
    attributes = item.get("attributes", {})
    if not isinstance(attributes, dict):
        attributes = {}
    preferences = {
        key: (values[0] if len(values) == 1 and key != "others" else values)
        for key, values in attributes.items()
        if isinstance(values, list) and values
    }
    if not preferences and isinstance(item.get("preferences"), list):
        preferences = {"others": item["preferences"]} if item["preferences"] else {}

    return {
        "name": item.get("name", ""),
        "keywords": item.get("keywords", []),
        "preferences": preferences,
        "budget": item.get("budget"),
        "min_rating": item.get("min_rating"),
        "min_reviews": item.get("min_reviews"),
        "category_id": item.get("category_id", []),
    }

def save_prompt_memory(
    user_id: str,
    prompt: str,
    requirements: dict[str, Any],
) -> None:
    items = requirements.get("items")
    if not isinstance(items, list):
        raise ValueError("Extracted requirements must contain an items list.")
    if not items:
        items = [{}]

    with user_data_lock:
        user_data = load_user_data()
        if get_registered_user(user_data, user_id) is None:
            raise HTTPException(status_code=404, detail="User not found.")

        memory = load_user_memory(user_id)
        records = memory["prompt_memory"]
        now = datetime.now(timezone.utc).isoformat()
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("An extracted requirement is invalid.")
            memory_fields = requirement_memory_fields(item)
            fingerprint = hashlib.sha256(
                json.dumps(
                    {"prompt": prompt, **memory_fields},
                    sort_keys=True,
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
            records.append({
                "memory_id": max(
                    (int(record.get("memory_id", 0)) for record in records),
                    default=0,
                ) + 1,
                "user_id": user_id,
                **memory_fields,
                "prompt": prompt,
                "source_type": "user_prompt",
                "created_at": now,
                "last_updated_at": now,
                "hash_value": fingerprint,
                "use_freq": 1,
            })
        write_json_atomically(user_memory_path(user_id), memory)


def save_user_memory(user_id: str, requirements: dict[str, Any]) -> None:
    items = requirements.get("items")
    if not isinstance(items, list):
        raise ValueError("Extracted requirements must contain an items list.")

    memory_path = user_memory_path(user_id)
    with user_data_lock:
        try:
            user_data = load_user_data()
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=500, detail="Could not read registered users.") from exc
        if get_registered_user(user_data, user_id) is None:
            raise HTTPException(status_code=404, detail="User not found.")

        memory = load_user_memory(user_id)
        records = memory["preference_memory"]

        now = datetime.now(timezone.utc).isoformat()
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("An extracted requirement is invalid.")
            memory_data = requirement_memory_fields(item)
            fingerprint = hashlib.sha256(
                json.dumps(memory_data, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            existing = next(
                (record for record in records if record.get("hash_value") == fingerprint),
                None,
            )
            if existing is not None:
                existing["last_updated_at"] = now
                existing["use_freq"] = int(existing.get("use_freq", 1)) + 1
                continue

            records.append({
                "user_id": user_id,
                "memory_id": max(
                    (int(record.get("memory_id", 0)) for record in records),
                    default=0,
                ) + 1,
                **memory_data,
                "source_type": "user_prompt",
                "created_at": now,
                "last_updated_at": now,
                "hash_value": fingerprint,
                "use_freq": 1,
            })

        write_json_atomically(memory_path, memory)

# Health check
@app.get("/")
def home():
    return {"message": "API is running"}

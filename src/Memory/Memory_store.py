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

USER_DATA_PATH = Path(__file__).resolve().parent / "Users" / "shop_users.json"
MEMORY_DIRECTORY = Path(__file__).resolve().parent / "User_Memory"

# Request model
class DataRequest(BaseModel):
    data: dict[str, Any]
    user_prompt: str
    user_id: str


class EmailRequest(BaseModel):
    email: str


class ProductMemoryRequest(BaseModel):
    user_id: str
    product: dict[str, Any]


def write_json_atomically(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        suffix=".tmp",
        delete=False,
    ) as temporary_file:
        json.dump(data, temporary_file, indent=2)
        temporary_path = Path(temporary_file.name)
    temporary_path.replace(path)


def load_user_data() -> dict[str, Any]:
    if not USER_DATA_PATH.exists():
        return {"users": []}
    user_data = json.loads(USER_DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(user_data, dict) or not isinstance(user_data.get("users"), list):
        raise ValueError("The user JSON file has an invalid structure.")
    if any(not isinstance(user, dict) or not isinstance(user.get("email"), str) for user in user_data["users"]):
        raise ValueError("The user JSON file contains an invalid user entry.")
    return user_data


def user_memory_path(user_id: str) -> Path:
    email_hash = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    return MEMORY_DIRECTORY / f"user_{email_hash}.json"


def user_event_memory_path(user_id: str, memory_type: str) -> Path:
    email_hash = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    return MEMORY_DIRECTORY / f"user_{email_hash}_{memory_type}_memory.json"



def load_user_memory(user_id: str) -> dict[str, Any]:
    path = user_memory_path(user_id)

    if path.exists():
        memory = json.loads(path.read_text(encoding="utf-8"))

        # Handle legacy list format
        if isinstance(memory, list):
            memory = {
                "user_id": user_id,
                "preference_memory": memory,
                "prompt_memory": [],
                "click_memory": [],
                "buy_memory": [],
            }

        if not isinstance(memory, dict):
            raise ValueError("The user memory file has an invalid structure.")

    else:
        memory = {}

    # Initialize top-level structure
    memory["user_id"] = user_id

    for key in ("preference_memory", "prompt_memory", "click_memory", "buy_memory"):
        memory.setdefault(key, [])

        if not isinstance(memory[key], list) or any(
            not isinstance(record, dict) for record in memory[key]
        ):
            raise ValueError(f"The {key} data has an invalid structure.")

    # Initialize and validate prompt memory records
    for record in memory["prompt_memory"]:
        record.setdefault("name", "")
        record.setdefault("keywords", [])
        record.setdefault("preferences", {})
        record.setdefault("budget", None)
        record.setdefault("min_rating", None)
        record.setdefault("min_reviews", None)
        record.setdefault("category_id", [])
        record.setdefault("source_type", "user_prompt")
        record.setdefault("last_updated_at", record.get("created_at"))
        record.setdefault("use_freq", 1)

        # Validate record fields
        if not isinstance(record["keywords"], list):
            raise ValueError("Prompt keywords must be a list.")

        if not isinstance(record["preferences"], dict):
            raise ValueError("Prompt preferences must be a dictionary.")

        if not isinstance(record["category_id"], list):
            raise ValueError("Prompt category_id must be a list.")

        # Generate hash if missing
        if not record.get("hash_value"):
            hash_data = {
                "prompt": record.get("prompt", ""),
                "name": record["name"],
                "keywords": record["keywords"],
                "preferences": record["preferences"],
                "budget": record["budget"],
                "min_rating": record["min_rating"],
                "min_reviews": record["min_reviews"],
                "category_id": record["category_id"],
            }

            record["hash_value"] = hashlib.sha256(
                json.dumps(
                    hash_data,
                    sort_keys=True,
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()

    return memory





def migrate_legacy_memory(user: dict[str, Any], user_id: str) -> None:
    legacy_id = user.get("user_id")
    memory_path = user_memory_path(user_id)
    memory = load_user_memory(user_id)
    paths_to_remove = []

    if isinstance(legacy_id, int):
        legacy_path = MEMORY_DIRECTORY / f"user_{legacy_id}.json"
        if legacy_path.exists() and legacy_path != memory_path:
            legacy_records = json.loads(legacy_path.read_text(encoding="utf-8"))
            if not isinstance(legacy_records, list) or any(
                not isinstance(record, dict) for record in legacy_records
            ):
                raise ValueError("The legacy user memory file has an invalid structure.")
            memory["preference_memory"].extend(legacy_records)
            for memory_id, record in enumerate(memory["preference_memory"], start=1):
                record["user_id"] = user_id
                record["memory_id"] = memory_id
            paths_to_remove.append(legacy_path)

    for memory_type in ("prompt", "click", "buy"):
        event_path = user_event_memory_path(user_id, memory_type)
        if not event_path.exists():
            continue
        event_records = json.loads(event_path.read_text(encoding="utf-8"))
        if not isinstance(event_records, list) or any(
            not isinstance(record, dict) for record in event_records
        ):
            raise ValueError(f"The {memory_type} memory file has an invalid structure.")
        target_records = memory[f"{memory_type}_memory"]
        target_records.extend(event_records)
        for memory_id, record in enumerate(target_records, start=1):
            record["user_id"] = user_id
            record["memory_id"] = memory_id
        paths_to_remove.append(event_path)

    write_json_atomically(memory_path, memory)
    for path in paths_to_remove:
        path.unlink()
    user["user_id"] = user_id


def get_registered_user(user_data: dict[str, Any], user_id: str) -> dict[str, Any] | None:
    return next(
        (
            user for user in user_data["users"]
            if user.get("email", "").strip().lower() == user_id
        ),
        None,
    )
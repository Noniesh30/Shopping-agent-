from datetime import datetime, timezone
import hashlib
import json
import copy
from pathlib import Path
from .hash import calculate_hash

def load_memory(user_id):
    """
    loading data from memory.json file

    """
    main_user=list(user_id.split("@"))[0]
    memory_path = Path(__file__).resolve().parents[2] / "User_Memory" / f"{main_user}.json"
    with open(memory_path, "r", encoding="utf-8") as file:
        memory_data = json.load(file)
    return memory_data["preference_memory"]


def fetch_relevant_records ( input_schema , memory_data ) :
    """ 
    filter the memory data by user_id and name i.e. wherever both match keep that record in relevant records

    """
    user_id = input_schema["user_id"]
    user_records = []

    for record in memory_data:
        if record["user_id"] == user_id:
            user_records.append(copy.deepcopy(record))

    relevant_records = []
    for item in input_schema["items"]:
        item_records = []
        for record in user_records:
            if record["name"] == item["name"]:
                item_records.append(record)

        relevant_records.append(item_records)
    return relevant_records

def write_back( updated_new_memory ) :
    """
    write back updated memory to memory.json file
    """
    memory_path = Path(__file__).resolve().parents[2] / "data" / "memory.json"
    with open(memory_path, "w", encoding="utf-8") as file:
        json.dump(updated_new_memory, file, indent=4, ensure_ascii=False)


def store_input_schema ( input_schema , memory_data) :
    """ 
    source_type , created_at, last_updated_at , hash_value , use_count for each item in input_schema and user_id will come from schema itself

    """
    user_id = input_schema["user_id"]
    if memory_data:
        next_memory_id = max(
            record["memory_id"] for record in memory_data
        ) + 1
    else:
        next_memory_id = 1
    current_timestamp = datetime.now(timezone.utc).isoformat()
    for item in input_schema["items"]:
        new_record = {
            "user_id": user_id,
            "memory_id": next_memory_id,
            "name": item["name"],
            "keywords": item["keywords"],
            "preferences": item["preferences"],
            "budget": item["budget"],
            "min_rating": item["min_rating"],
            "min_reviews": item["min_reviews"],
            "category_id": item["category_id"],
            "source_type": "user_prompt",
            "created_at": current_timestamp,
            "last_updated_at": current_timestamp,
            "use_freq": 1
        }
        # Generate hash after all other record fields are added.
        new_record["hash_value"] = calculate_hash(new_record)
        print(calculate_hash(new_record))
        memory_data.append(new_record)
        next_memory_id += 1
    return memory_data


def update_memory ( input_schema , memory_data ) :
    updated_new_memory = store_input_schema ( input_schema, memory_data)
    write_back(updated_new_memory)



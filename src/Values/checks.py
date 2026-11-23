from datetime import datetime, timezone
import hashlib
import json
import hmac
from src.Values.config import SECRET_KEY
from .hash import calculate_hash

def find_consequence_of_error ( consistency_assessed, input_schema ) :
    """
    if budget is too high compared to recent_request 
    if min_reviews are too less compared to recent_request
    for product categories which involves medicines etc. 
    keeping budget and reviews separate from preferences because they influence buying decision not like decision for a product

    """
    consequence_assessed = []
    for records in consistency_assessed:
        for record in records:
            consequence_count = 0
            for item in input_schema["items"]:
                if record["name"] == item["name"]:
                    if record.get("budget") is not None and item.get("budget") is not None:
                        if record["budget"] > 1.5 * item["budget"]:
                            consequence_count += 1
                    if record.get("min_reviews") is not None and item.get("min_reviews") is not None:
                        if record["min_reviews"] < (3/4) * item["min_reviews"]:
                            consequence_count += 1
                    break
            if "assessed_values" not in record:
                record["assessed_values"] = {}
            record["assessed_values"]["consequence"] = consequence_count
        consequence_assessed.append(records)
    return consequence_assessed


def find_memory_conflicts ( record_corruption_assessed , fixed_attributes ) :
    """
    between pairs of relevant records find conflicts for attributes present in both the records that is for each relevant record find the number of conflicting records with it 

    """
    consistency_assessed = []
    for records in record_corruption_assessed:
        for record1 in records:
            conflict_count = 0
            for record2 in records:
                if record1["memory_id"] == record2["memory_id"]:
                    continue
                conflicts = number_of_conflicting_values(
                    record1, record2, fixed_attributes
                )
                if conflicts > 0:
                    conflict_count += 1
            if "assessed_values" not in record1:
                record1["assessed_values"] = {}
            record1["assessed_values"]["consistency_with_memory"] = conflict_count
        consistency_assessed.append(records)
    return consistency_assessed


def find_corrupted_records(suspicion_assessed):
    record_corruption_assessed = []
    for records in suspicion_assessed:
        for record in records:
            # stored_hash = record.get("hash_value")
            # if not stored_hash:
            #     corruption = 1
            # else:
            #     calculated_hash = calculate_hash(record)
            #     corruption = int(
            #         not hmac.compare_digest(
            #             calculated_hash,
            #             stored_hash
            #         )
            #     )
            record.setdefault("assessed_values", {})
            record["assessed_values"]["record_corruption"] = 0  
        record_corruption_assessed.append(records)
    return record_corruption_assessed

def contains_suspicious_keyword(value,suspicious_keywords):
    """Recursively check strings inside dictionaries and lists."""
    if isinstance(value, str):
        return any(
            keyword in value.lower()
            for keyword in suspicious_keywords
        )
    elif isinstance(value, dict):
        return any(
            contains_suspicious_keyword(v,suspicious_keywords)
            for v in value.values()
        )
    elif isinstance(value, (list, tuple, set)):
        return any(
            contains_suspicious_keyword(v,suspicious_keywords)
            for v in value
        )
    return False

def find_suspicion(uncertainty_assessed, fixed_attributes):
    """
    Check field types and suspicious keywords in all nested fields.
    Increase suspicion count when an incorrect type or suspicious
    keyword is found.
    """
    suspicion_assessed = []
    suspicious_keywords = ["ignore", "override", "reveal", "expose", "send"]
    expected_types = {
        "user_id": str,
        "memory_id": int,
        "name": str,
        "keywords": list,
        "preferences": dict,
        "budget": (int, float, type(None)),
        "min_rating": (int, float, type(None)),
        "min_reviews": (int, type(None)),
        "category_id": list,
        "source_type": str,
        "created_at": str,
        "last_updated_at": str,
        "hash_value": str,
        "use_freq": int
    }  
    for records in uncertainty_assessed:
        for record in records:
            suspicion_count = 0
            # 1. Check top-level field types
            for field, expected_type in expected_types.items():
                if field in record:
                    if not isinstance(record[field], expected_type):
                        suspicion_count += 1
            # 2. Check suspicious keywords in nested fields
            for field, value in record.items():
                if field in ("hash_value", "assessed_values"):
                    continue
                if contains_suspicious_keyword(value,suspicious_keywords):
                    suspicion_count += 1
            # 3. Store assessment
            record.setdefault("assessed_values", {})
            record["assessed_values"]["suspicious"] = suspicion_count
        suspicion_assessed.append(records)
    return suspicion_assessed


# def find_suspicion ( uncertainty_assessed , fixed_attributes ) :
#     """ 
#      check for types of fields and suspicious keywords like [ ignore , override, reveal , expose, send ] for every field . if suspicion increase the value by 1

#     """
#     suspicion_assessed = []
#     suspicious_keywords = ["ignore", "override", "reveal", "expose", "send"]
#     expected_types = {
#         "user_id": str,
#         "memory_id": int,
#         "name": str,
#         "keywords": list,
#         "preferences": dict,
#         "budget": (int, float),
#         "min_rating": (int, float, type(None)),
#         "min_reviews": int,
#         "category_id": list,
#         "source_type": str,
#         "created_at": str,
#         "last_updated_at": str,
#         "hash_value": str,
#         "use_freq": int
#     }
#     for records in uncertainty_assessed:
#         for record in records:
#             suspicion_count = 0
#             # Check top-level field types
#             for field, expected_type in expected_types.items():
#                 if field in record and not isinstance(record[field], expected_type):
#                     suspicion_count += 1
#             # Check suspicious keywords in top-level string fields
#             for field, value in record.items():
#                 if isinstance(value, str):
#                     for keyword in suspicious_keywords:
#                         if keyword in value.lower():
#                             suspicion_count += 1
#                             break
#             if "assessed_values" not in record:
#                 record["assessed_values"] = {}
#             record["assessed_values"]["suspicious"] = suspicion_count
#         suspicion_assessed.append(records)
#     return suspicion_assessed

def find_uncertainty ( agreement_assessed , fixed_attributes ) :
    """
    calculate the number of fixed attributes apart from others not present in the record 
    """
    uncertainty_assessed = []
    for records in agreement_assessed:
        for record in records:
            missing_attributes = 0
            for attribute in fixed_attributes:
                if attribute == "others":
                    continue
                if not record["preferences"].get(attribute):
                    missing_attributes += 1

            if "assessed_values" not in record:
                record["assessed_values"] = {}
            record["assessed_values"]["uncertainty"] = missing_attributes
        uncertainty_assessed.append(records)
    return uncertainty_assessed


def number_of_conflicting_values ( record1 , record2 , fixed_attributes ) :
    """
    if we are finding conflict of record1 with record2 
    then for every value of every attribute in fixed attributes of record1 apart from others
    we will check whether that value present in record2 
    if not increase the conflict value by 1
    """
    conflict_count = 0
    for attribute in fixed_attributes:
        if attribute == "others":
            continue
        value1 = record1["preferences"].get(attribute)
        value2 = record2["preferences"].get(attribute)
        if not value1  or not value2 :
            continue
        if isinstance(value1, (list, set, tuple)):
            for value in value1:
                if isinstance(value2, ( list, set, tuple)):
                    if value not in value2:
                        conflict_count += 1
                elif value != value2:
                    conflict_count += 1
        elif isinstance(value2, (list, set, tuple)):
            if value1 not in value2:
                conflict_count += 1
        elif value1 != value2:
            conflict_count += 1
    return conflict_count

def find_agreement_with_recent_request ( freq_assessed , input_schema , fixed_attributes ) :
    """ 
    add conflicts_with_recent_request 
    for conflicts , for every attribute other than others in input_schema if the corresponding record doesn't have that value in the corresponding attribute list then increase the number of conflicts 
    also keep conflicting records and non conflicting records in a separate list

    add agreement_in_others_attribute
    for others attribute see how many values match 
    
    finding conflict for attributes apart from others and agreement for others . 
    example - ['oversized'] , ['oversized','winters'] because values don't belong to the same attribute

    """
    agreement_assessed = []
    for records in freq_assessed:
        for record in records:
            conflicts = 0
            for item in input_schema["items"]:
                if record["name"] == item["name"]:
                    conflicts = number_of_conflicting_values(
                        record, item, fixed_attributes
                    )
                    memory_others = record["preferences"].get("others", [])
                    request_others = item["preferences"].get("others", [])
                    matching_others = 0
                    for value in memory_others:
                        if value in request_others:
                            matching_others += 1
                    if "assessed_values" not in record:
                        record["assessed_values"] = {}
                    record["assessed_values"]["conflicts_with_recent_request"] = conflicts
                    record["assessed_values"]["agreement_in_others_attribute"] = matching_others
                    break
        agreement_assessed.append(records)
    return agreement_assessed


def find_use_freq ( age_assessed ) :
    # same as use_freq in the record
    freq_assessed = []
    for records in age_assessed:
        for record in records:
            if "assessed_values" not in record:
                record["assessed_values"] = {}
            record["assessed_values"]["use_freq"] = record.get("use_freq", 0)
        freq_assessed.append(records)
    return freq_assessed


def find_age ( source_assessed , input_schema ) : 
    # find age through delta between current timestamp and record timestamp
    current_timestamp = datetime.now(timezone.utc)
    age_assessed = []
    for records in source_assessed:
        for record in records:
            updated_timestamp = datetime.fromisoformat(
                record["last_updated_at"].replace("Z", "+00:00")
            )
            time_difference = current_timestamp - updated_timestamp
            age_in_days = max(0, time_difference.days)
            if "assessed_values" not in record:
                record["assessed_values"] = {}
            record["assessed_values"]["age"] = age_in_days
        age_assessed.append(records)
    return age_assessed


def find_source_reliability ( relevant_records ) : 
    """
    if source_type is user_prompt then 1  ( high )
    else if source_type is agent_inferred then 
    see bought ( bought not present or bought == no then reliability 0 ) ( low )
    if bought = yes then reliability = 1 ( medium )
    create assessed_values and put the corresponding source_reliability
    """
    source_assessed = []
    for records in relevant_records:
        for record in records:
            if "assessed_values" not in record:
                record["assessed_values"] = {}
            if record["source_type"] == "user_prompt":
                source_reliability = 2
            elif record["source_type"] == "agent_inferred":
                if record.get("bought") is True:
                    source_reliability = 1
                else:
                    source_reliability = 0
            record["assessed_values"]["source_reliability"] = source_reliability
        source_assessed.append(records)
    return source_assessed


def perform_checks( relevant_records , input_schema, fixed_attributes ) :
    source_assessed = find_source_reliability ( relevant_records )
    age_assessed = find_age ( source_assessed , input_schema )
    freq_assessed = find_use_freq( age_assessed )
    agreement_assessed = find_agreement_with_recent_request ( freq_assessed, input_schema, fixed_attributes)
    uncertainty_assessed = find_uncertainty ( agreement_assessed , fixed_attributes)
    suspicion_assessed = find_suspicion ( uncertainty_assessed , fixed_attributes )
    record_corruption_assesed = find_corrupted_records ( suspicion_assessed )
    consistency_assessed = find_memory_conflicts ( record_corruption_assesed , fixed_attributes )
    consequence_assessed = find_consequence_of_error ( consistency_assessed , input_schema)
    return consequence_assessed


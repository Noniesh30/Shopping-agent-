def assign_confidence_value ( assessed_records  , fixed_attributes) :
    """
    confidence = 0 if corrupted record
    else find confidence through the agreed upon scoring method 

    """
    confidence_assigned = []
    weights = {
        "source_reliability": 0.20,
        "age": 0.15,
        "use_freq": 0.10,
        "conflicts_with_recent_request": 0.20,
        "agreement_in_others_attribute": 0.05,
        "uncertainty": 0.10,
        "suspicious": 0.10,
        "consistency_with_memory": 0.10
    }
    for records in assessed_records:
        item_records = []
        for record in records:
            assessed_values = record["assessed_values"]
            # A corrupted record must not be trusted.
            if assessed_values.get("record_corruption", 0) > 0:
                confidence = 0.0
            else:
                source_score = (
                    assessed_values.get("source_reliability", 0) / 2
                )
                age = assessed_values.get("age", 0)
                age_score = 1 / (1 + age / 180)
                use_freq = assessed_values.get("use_freq", 0)
                use_freq_score = use_freq / (use_freq + 5)
                conflicts = assessed_values.get(
                    "conflicts_with_recent_request", 0
                )
                conflict_score = 1 / (1 + conflicts)
                matching_others = assessed_values.get(
                    "agreement_in_others_attribute", 0
                )
                others_score = matching_others / (matching_others + 1)
                max_uncertainty = len(fixed_attributes) - 1
                uncertainty = assessed_values.get("uncertainty", 0)
                uncertainty_score = 1 - min(
                    uncertainty / max_uncertainty, 1
                )
                suspicious = assessed_values.get("suspicious", 0)
                suspicion_score = 1 / (1 + suspicious)
                consistency = assessed_values.get(
                    "consistency_with_memory", 0
                )
                consistency_score = 1 / (1 + consistency)
                scores = {
                    "source_reliability": source_score,
                    "age": age_score,
                    "use_freq": use_freq_score,
                    "conflicts_with_recent_request": conflict_score,
                    "agreement_in_others_attribute": others_score,
                    "uncertainty": uncertainty_score,
                    "suspicious": suspicion_score,
                    "consistency_with_memory": consistency_score
                }
                confidence = 0.0
                for factor, weight in weights.items():
                    confidence += scores[factor] * weight
                confidence = round(confidence, 4)
            record["confidence_value"] = confidence
            item_records.append(record)
        confidence_assigned.append(item_records)
    return confidence_assigned
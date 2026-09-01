def dosage_status(applied_kg_per_ha: float, recommended_kg_per_ha: float, tolerance: float = 1.2) -> dict:
    limit = recommended_kg_per_ha * tolerance
    return {"within_compliance": applied_kg_per_ha <= limit, "recommended_kg_per_ha": recommended_kg_per_ha, "safe_limit_kg_per_ha": limit, "actual_kg_per_ha": applied_kg_per_ha}

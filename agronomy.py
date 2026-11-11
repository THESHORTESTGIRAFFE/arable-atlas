"""
Agronomy calculation module for Arable Atlas.
Provides rule-based calculations for soil amendments (lime, fertilizers) and agronomic scoring.
"""

def calculate_lime_requirement(ph):
    """
    Calculate agricultural lime requirement (tons per hectare) to raise pH to optimal range (6.0 - 6.5).
    """
    if ph == "N/A" or ph is None:
        return {"recommendation": "pH data unavailable for lime calculation.", "tons_per_ha": 0.0}
    
    try:
        ph_val = float(ph)
    except (ValueError, TypeError):
        return {"recommendation": "Invalid pH value.", "tons_per_ha": 0.0}

    if ph_val < 5.0:
        return {
            "status": "Strongly Acidic",
            "tons_per_ha": 2.5,
            "recommendation": "Apply 2.5 tons of agricultural lime per hectare incorporated into the top 20cm of soil at least 4 weeks before planting to raise pH."
        }
    elif 5.0 <= ph_val < 5.5:
        return {
            "status": "Moderately Acidic",
            "tons_per_ha": 1.5,
            "recommendation": "Apply 1.5 tons of agricultural lime per hectare to neutralize acidity and improve nutrient availability."
        }
    elif 5.5 <= ph_val < 6.0:
        return {
            "status": "Slightly Acidic",
            "tons_per_ha": 0.75,
            "recommendation": "Apply 0.75 tons of agricultural lime per hectare as a maintenance application."
        }
    else:
        return {
            "status": "Optimal or Alkaline",
            "tons_per_ha": 0.0,
            "recommendation": "Soil pH is in the optimal range. No lime application needed."
        }


def calculate_fertilizer_recommendation(nitrogen, soil_type):
    """
    Calculate NPK / Urea top-dressing recommendations based on soil nitrogen (ocd / nitrogen proxy).
    """
    if nitrogen == "N/A" or nitrogen is None:
        return {"recommendation": "Nitrogen data unavailable.", "urea_kg_ha": 50}

    try:
        n_val = float(nitrogen)
    except (ValueError, TypeError):
        return {"recommendation": "Invalid nitrogen value.", "urea_kg_ha": 50}

    # Low nitrogen threshold logic
    if n_val < 20:
        urea_rec = 150
        npk_rec = "Compound D (7:14:7) at 400 kg/ha basal dressing followed by Urea top-dressing at 150 kg/ha."
    elif 20 <= n_val < 50:
        urea_rec = 100
        npk_rec = "Compound D (7:14:7) at 300 kg/ha basal dressing followed by Urea top-dressing at 100 kg/ha."
    else:
        urea_rec = 50
        npk_rec = "Compound D (7:14:7) at 200 kg/ha basal dressing followed by maintenance Urea top-dressing at 50 kg/ha."

    if "Sandy" in str(soil_type):
        npk_rec += " Note: Sandy soils leach nutrients quickly; split fertilizer applications into two equal doses (basal + split top-dress)."

    return {
        "nitrogen_level": n_val,
        "urea_kg_ha": urea_rec,
        "recommendation": npk_rec
    }


def assess_drought_resilience(soil_type, clay, sand):
    """
    Assess soil moisture retention and drought resilience.
    """
    if soil_type == "Clayey Soil" or (isinstance(clay, (int, float)) and clay > 40):
        return {
            "rating": "High Water Retention / Moderate Drainage Risk",
            "advice": "Retains moisture well through dry spells but prone to waterlogging or crusting after heavy rains. Practice conservation tillage."
        }
    elif soil_type == "Sandy Soil" or (isinstance(sand, (int, float)) and sand > 60):
        return {
            "rating": "Low Water Retention / High Leach Risk",
            "advice": "High risk of moisture stress during dry spells. Incorporate organic manure/compost to improve water-holding capacity and frequent light irrigations."
        }
    else:
        return {
            "rating": "Balanced / Optimal",
            "advice": "Good balance of drainage and water retention. Ideal for diversified crop production with standard mulch practices."
        }

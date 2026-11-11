import exifread
import requests
import pandas as pd
import time
import google.generativeai as genai
from config import Config
from agronomy import calculate_lime_requirement, calculate_fertilizer_recommendation, assess_drought_resilience

# Initialize Gemini
genai.configure(api_key=Config.GEMINI_API_KEY)
model = genai.GenerativeModel(Config.GEMINI_MODEL)


# -------------------------------
# Extract GPS Data from Image
# -------------------------------
def extract_gps(image_path):
    """Extract GPS coordinates from image EXIF metadata."""
    with open(image_path, "rb") as img_file:
        tags = exifread.process_file(img_file)

    def convert_to_decimal(coord, ref):
        """Convert EXIF GPS coordinates to decimal degrees format."""
        degrees, minutes, seconds = [float(x.num) / float(x.den) for x in coord]
        decimal = degrees + (minutes / 60) + (seconds / 3600)

        # Apply hemisphere correction
        if ref in ["S", "W"]:
            decimal = -decimal

        return decimal

    if "GPS GPSLatitude" in tags and "GPS GPSLongitude" in tags:
        lat = convert_to_decimal(tags["GPS GPSLatitude"].values, tags["GPS GPSLatitudeRef"].values)
        lon = convert_to_decimal(tags["GPS GPSLongitude"].values, tags["GPS GPSLongitudeRef"].values)

        # 🔍 Debugging: Print extracted values
        print(f"✅ Extracted GPS Coordinates: Lat={lat}, Lon={lon}")

        # 🚨 Check if values are in valid range
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            print("❌ Invalid GPS values detected! Adjusting...")
            return None, None  # Ignore invalid values

        return lat, lon

    print("❌ No GPS Data Found")
    return None, None


# -------------------------------
# Classification
# -------------------------------
def classify_soil_texture(clay, sand, silt):
    if any(val in ["N/A", None] for val in [clay, sand, silt]):
        return "Unknown"
    clay = float(clay)
    sand = float(sand)
    silt = float(silt)
    if clay > 40:
        return "Clayey Soil"
    elif sand > 60:
        return "Sandy Soil"
    elif silt > 50:
        return "Silty Soil"
    elif 20 < clay < 40 and 20 < sand < 60:
        return "Loamy Soil"
    else:
        return "Mixed Soil"


# ---------------------------------
# Extracting Soil Data
# ---------------------------------
def extract_soil_data(soil_data):
    layers = soil_data.get("properties", {}).get("layers", [])

    props = {
        "ph": "N/A",
        "moisture": "N/A",
        "nitrogen": "N/A",
        "clay": "N/A",
        "sand": "N/A",
        "silt": "N/A"
    }

    for layer in layers:
        name = layer.get("name", "").lower()
        depth_data = layer.get("depths", [])[0]  # Top layer (0–5 cm)

        if name == "phh2o" and "values" in depth_data:
            val = depth_data["values"].get("mean")
            if val is not None:
                props["ph"] = round(val / 10, 2)

        elif name == "ocd" and "values" in depth_data:
            val = depth_data["values"].get("mean")
            if val is not None:
                props["moisture"] = round(val, 2)

        elif name == "nitrogen" and "values" in depth_data:
            val = depth_data["values"].get("mean")
            if val is not None:
                props["nitrogen"] = round(val, 2)

        elif name in ["clay", "sand", "silt"] and "values" in depth_data:
            val = depth_data["values"].get("mean")
            if val is not None:
                props[name] = round(val / 10, 2)  # Convert g/kg → %

    # 🌱 Classify
    return {
        "soil_type": classify_soil_texture(props["clay"], props["sand"], props["silt"]),
        "ph": props["ph"],
        "moisture": props["moisture"],
        "nitrogen": props["nitrogen"],
        "clay": props["clay"],
        "sand": props["sand"],
        "silt": props["silt"]
    }


# -------------------------------
# Fetch Soil Data from SoilGrids API
# -------------------------------
def analyse_soil_image(image_path=None, lat=None, lon=None):
    if not lat or not lon:
        return {"soil_type": "Unknown", "ph": "N/A", "moisture": "N/A"}

    # Updated URL structure for SoilGrids v2.0
    soil_api_url = f"{Config.SOILGRIDS_API_URL}?lon={lon}&lat={lat}&property=phh2o&property=ocd&property=nitrogen&property=clay&property=sand&property=silt&depth=0-5cm&value=mean"
    print(f"DEBUG: SoilGrids API URL: {soil_api_url}")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(soil_api_url, timeout=30) # Increased timeout
            print(f"DEBUG: Attempt {attempt + 1}: Response status: {response.status_code}")
            
            if response.status_code == 200:
                response.raise_for_status()
                raw_data = response.json()
                break # Success
            elif response.status_code == 504:
                print(f"DEBUG: Gateway Timeout, retrying...")
                time.sleep(2 * (attempt + 1)) # Exponential backoff
                continue
            else:
                response.raise_for_status()
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Error fetching soil data after {max_retries} attempts: {e}")
                return {
                    "soil_type": "Unknown",
                    "ph": "N/A",
                    "moisture": "N/A",
                    "nitrogen": "N/A",
                    "clay": "N/A",
                    "sand": "N/A",
                    "silt": "N/A",
                    "crops": []
                }
            print(f"DEBUG: Attempt {attempt + 1} failed: {e}. Retrying...")
            time.sleep(2 * (attempt + 1))
            continue
    else:
        # If we reach here, we exhausted retries
        return {
            "soil_type": "Unknown",
            "ph": "N/A",
            "moisture": "N/A",
            "nitrogen": "N/A",
            "clay": "N/A",
            "sand": "N/A",
            "silt": "N/A",
            "crops": []
        }

    clean_data = extract_soil_data(raw_data)
    crops, actionable_advice = get_suitable_crops(clean_data["soil_type"], clean_data["ph"], clean_data["moisture"], lat=lat, lon=lon)
    clean_data["crops"] = crops
    clean_data["actionable_advice"] = actionable_advice
    clean_data["lime_recommendation"] = calculate_lime_requirement(clean_data["ph"])
    clean_data["fertilizer_recommendation"] = calculate_fertilizer_recommendation(clean_data["nitrogen"], clean_data["soil_type"])
    clean_data["drought_resilience"] = assess_drought_resilience(clean_data["soil_type"], clean_data["clay"], clean_data["sand"])
    return clean_data

# -------------------------------
# AI-Powered Crop Recommendation System
# -------------------------------
ECOCROP_FILE = "data/ecocorp_data.csv"
ecocrop_df = pd.read_csv(ECOCROP_FILE)

def get_suitable_crops(soil_type, ph, moisture, lat=None, lon=None):
    """
    Uses Gemini AI to recommend crops and provide cultivation/weather advice based on soil properties.
    """
    try:
        location_info = f"at latitude {lat} and longitude {lon}" if lat and lon else "in this region"

        prompt = (
            f"Act as a professional agronomist. I have soil data for a farm located {location_info}.\n"
            f"- Soil Type: {soil_type}\n"
            f"- pH Level: {ph}\n"
            f"- Moisture: {moisture}%\n\n"
            "Provide an authoritative, actionable recommendation for this land in a single, cohesive paragraph. "
            "Incorporate cultivation tips, weather considerations, and why the recommended crops are suitable. "
            "Do not use bullet points, lists, questions, greetings, or conversational filler. "
            "Finally, list the 3 recommended crops on the very last line, separated by commas."
        )

        ai_response = ask_gemini(prompt)
        
        # Parse the response to separate crops and detailed advice
        lines = ai_response.strip().split('\n')
        crops_line = lines[-1]
        actionable_advice = '\n'.join(lines[:-1]).strip()
        
        # Strip markdown (asterisks, hashtags)
        actionable_advice = actionable_advice.replace('**', '').replace('#', '').replace('__', '')
        
        crops = [c.strip() for c in crops_line.split(',') if c.strip()]
        
        return crops, actionable_advice

    except Exception as e:
        print(f"🌶️ AI Crop Suggestion Error: {e}")
        return [], "Unable to generate actionable recommendations at this time."



def fetch_soil_data(lat, lon):
    """Fetch soil properties from SoilGrids API using latitude & longitude"""
    url = f"{Config.SOILGRIDS_API_URL}?lon={lon}&lat={lat}"

    try:
        print(f"Requesting Soil Data from: {url}")  # ✅ Print full request URL

        response = requests.get(url, timeout=10)  # ✅ Added timeout to prevent hanging
        response.raise_for_status()  

        print("Raw API Response:", response.text)  # ✅ Print response before parsing JSON
        return response.json()
    
    except requests.exceptions.Timeout:
        print("Error: SoilGrids API timed out!")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching soil data: {e}")
        return None

def ask_gemini(question, language="en"):
    """Send a query to Gemini AI assistant and return the response in the specified language."""
    # Dynamic system prompt based on language
    lang_map = {
        "en": "English",
        "sn": "Shona",
        "nd": "Ndebele"
    }
    target_lang = lang_map.get(language, "English")

    system_prompt = (
        "You are an expert chatbot on agriculture in the Southern African region. "
        "Embody a playful and approachable personality. Your explanations should be clear, "
        "concise, and easy to understand, avoiding jargon. "
        f"You MUST respond ONLY in {target_lang}. "
        "Present your information in short paragraphs of text. "
        "Conclude each answer with a relevant question to encourage further interaction."
    )

    try:
        # Use the global 'model' object
        response = model.generate_content(
            f"System: {system_prompt}\nUser: {question}"
        )
        return response.text.strip()

    except Exception as e:
        print(f"General Error: {e}")
        return "Error: An unexpected error occurred."

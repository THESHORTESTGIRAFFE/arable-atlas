import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration settings for AgriMap"""

    # Flask Secret Key (for session security)
    SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_here")

    # Database Configuration (Modify as needed)
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///agrimap.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is not set")

    GEMINI_MODEL = "gemini-3.5-flash-lite"
    # Assistant ID (We will generate it dynamically)

    # ✅ SoilGrids API (Soil Type, pH, Moisture)
    SOILGRIDS_API_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    
    # ✅ NASA POWER API (Weather & Water Requirements)
    NASA_POWER_API_URL = "https://power.larc.nasa.gov/api/temporal"

    # ✅ OpenWeatherMap API (Real-time Weather Data)
    OPENWEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "your_openweather_api_key_here")

    # ✅ FAO ECOCROP (Crop Suitability Dataset - CSV)
    ECOCROP_CSV_PATH = os.path.join(os.getcwd(), "data", "ecocrop_data.csv")

    # ✅ AI API (For Future AI Model Integration)
    AI_MODEL_API_URL = os.getenv("AI_MODEL_API_URL", "http://localhost:5001/predict")

    # ✅ Debug Mode (Set False in Production)
    DEBUG = True


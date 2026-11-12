import os
import secrets
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration settings for AgriMap"""

    # Flask Secret Key (for session security)
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)

    # Database Configuration (Modify as needed)
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///agrimap.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    # Assistant ID (We will generate it dynamically)

    # Persistent native-grid SoilGrids maps; bypass the paused REST service.
    SOILGRIDS_WCS_URL = "https://maps.isric.org/mapserv"
    SOIL_CACHE_DIR = os.getenv('SOIL_CACHE_DIR') or os.path.join(os.path.dirname(__file__), 'instance', 'soil_cache')
    SOIL_OFFLINE = os.getenv('SOIL_OFFLINE', 'false').lower() in ('1', 'true', 'yes')
    DEMO_FIELD_LAT = -17.9
    DEMO_FIELD_LON = 31.05
    
    # ✅ NASA POWER API (Weather & Water Requirements)
    NASA_POWER_API_URL = "https://power.larc.nasa.gov/api/temporal"

    # ✅ OpenWeatherMap API (Real-time Weather Data)
    OPENWEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
    OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "your_openweather_api_key_here")

    # ✅ FAO ECOCROP (Crop Suitability Dataset - CSV)
    ECOCROP_CSV_PATH = os.path.join(os.getcwd(), "data", "ecocrop_data.csv")

    # ✅ AI API (For Future AI Model Integration)
    AI_MODEL_API_URL = os.getenv("AI_MODEL_API_URL", "http://localhost:5001/predict")

    # ✅ Debug Mode (Set False in Production)
    DEBUG = True


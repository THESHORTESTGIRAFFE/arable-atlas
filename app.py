from flask import Flask, render_template, request, jsonify
import os
from werkzeug.utils import secure_filename
import requests
from config import Config
from utils import extract_gps, analyse_soil_image, get_suitable_crops, ask_gemini
from models import db, FarmPlot
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

app = Flask(__name__)
app.config.from_object(Config)
app.config["UPLOAD_FOLDER"] = "uploads"

db.init_app(app)
with app.app_context():
    if not app.config.get('TESTING'):
        try:
            db.create_all()
        except Exception:
            pass

# Ensure upload folder exists
if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/home')
def home():
    return render_template("dashboard.html")

@app.route('/contact')
def contact():
    return render_template("contact.html")

@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/services')
def services():
    return render_template("services.html")

@app.route('/dashboard')
def dashboard():
    return render_template("dashboard.html")

@app.route('/assistant')
def assistant():
    return render_template("assistant.html")

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files['image']
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    gps_coords = extract_gps(filepath)
    if not gps_coords:
        return jsonify({"error": "No GPS data found in image. Please select location manually."}), 400

    lat, lon = gps_coords

    # Get human-readable location
    try:
        geolocator = Nominatim(user_agent="agrimap", timeout=10)
        location = geolocator.reverse((lat, lon), language="en")
        location_name = location.address if location else "Unknown Location"
    except GeocoderTimedOut:
        location_name = "Location Unavailable"

    # 🎯 Analyse the soil directly
    results = analyse_soil_image(filepath, lat, lon)

    return jsonify({
        "latitude": lat,
        "longitude": lon,
        "location": location_name,
        "soil_type": results.get("soil_type"),
        "ph": results.get("ph"),
        "moisture": results.get("moisture"),
        "nitrogen": results.get("nitrogen"),
        "clay": results.get("clay"),
        "sand": results.get("sand"),
        "silt": results.get("silt"),
        "crops": results.get("crops", [])
    })


@app.route('/process', methods=['POST'])
def process_location():
    data = request.json
    lat, lon = data.get("lat"), data.get("lon")
    print(f"🌍 Received coordinates - Latitude: {lat}, Longitude: {lon}") # Console log
    
    if not lat or not lon:
        return jsonify({"error": "Invalid coordinates"}), 400

    # 🔍 Analyse directly
    results = analyse_soil_image(image_path=None, lat=lat, lon=lon)

    # Get human-readable location
    try:
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="agrimap", timeout=10)
        location = geolocator.reverse((lat, lon), language="en")
        location_name = location.address if location else "Location Unavailable"
    except Exception:
        location_name = "Location Unavailable"

    return jsonify({
        "latitude": lat,
        "longitude": lon,
        "location": location_name,
        "soil_type": results.get("soil_type", "Unknown"),
        "ph": results.get("ph", "N/A"),
        "moisture": results.get("moisture", "N/A"),
        "nitrogen": results.get("nitrogen", "N/A"),
        "clay": results.get("clay", "N/A"),
        "sand": results.get("sand", "N/A"),
        "silt": results.get("silt", "N/A"),
        "crops": results.get("crops", ["No suitable crops found"]),
        "actionable_advice": results.get("actionable_advice", "No specific advice available.")
    })

@app.route('/ask', methods=['POST'])
def ask_assistant():
    """Handle user queries and get responses from the Gemini AI assistant."""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        user_query = data.get("query")
        language = data.get("language", "en") # Default to English
        
        if not user_query:
            return jsonify({"error": "Query cannot be empty"}), 400

        # Get response from Gemini API with language context
        response = ask_gemini(user_query, language)
        if response.startswith("Error:"):
            return jsonify({"error": response}), 500
            
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.route('/api/plots', methods=['GET', 'POST'])
def manage_plots():
    if request.method == 'POST':
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        plot = FarmPlot(
            plot_name=data.get("plot_name", "My Farm Plot"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            soil_type=data.get("soil_type"),
            ph=str(data.get("ph")),
            moisture=str(data.get("moisture")),
            nitrogen=str(data.get("nitrogen")),
            recommendations=data.get("recommendations")
        )
        db.session.add(plot)
        db.session.commit()
        return jsonify({"message": "Plot saved successfully", "id": plot.id}), 201
    else:
        plots = FarmPlot.query.order_by(FarmPlot.timestamp.desc()).all()
        return jsonify([{
            "id": p.id,
            "plot_name": p.plot_name,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "soil_type": p.soil_type,
            "ph": p.ph,
            "moisture": p.moisture,
            "nitrogen": p.nitrogen,
            "recommendations": p.recommendations,
            "timestamp": p.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        } for p in plots])
   
if __name__ == '__main__':
    app.run(debug=True)


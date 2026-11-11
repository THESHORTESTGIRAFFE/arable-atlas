from flask import Flask, jsonify, request
from utils import get_suitable_crops
import openai

app = Flask(__name__)

# Initialize OpenAI client
client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)

@app.route('/api/crop-recommendation', methods=['GET'])
def crop_recommendation():
    soil_type = request.args.get("soil_type", "").strip()
    climate = request.args.get("climate", "").strip()
    
    if not soil_type or not climate:
        return jsonify({"error": "Missing parameters"}), 400
    
    crops = get_suitable_crops(soil_type, climate)
    
    return jsonify({"crops": crops})

if __name__ == "__main__":
    app.run(debug=True)


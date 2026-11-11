import requests
from flask import Blueprint, request, jsonify
from config import AI_API_URL

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/predict', methods=['POST'])
def predict_crop():
    user_input = request.json
    response = requests.post(AI_API_URL, json=user_input)
    return jsonify(response.json())


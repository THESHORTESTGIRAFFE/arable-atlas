from flask import Blueprint, jsonify
from models.soil_model import get_all_soil_data

soil_bp = Blueprint('soil', __name__)

@soil_bp.route('/soil', methods=['GET'])
def get_soil():
    data = get_all_soil_data()
    return jsonify({"regions": data})


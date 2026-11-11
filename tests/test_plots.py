import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

import pytest
from app import app, db
from models import FarmPlot

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()

def test_save_and_get_plot(client):
    # Test POST /api/plots
    response = client.post('/api/plots', json={
        "plot_name": "North Field",
        "latitude": -17.8252,
        "longitude": 31.0335,
        "soil_type": "Loamy Soil",
        "ph": "6.2",
        "moisture": "25.4",
        "nitrogen": "45.0",
        "recommendations": "Apply maize seed."
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data["message"] == "Plot saved successfully"

    # Test GET /api/plots
    get_resp = client.get('/api/plots')
    assert get_resp.status_code == 200
    plots = get_resp.get_json()
    assert len(plots) == 1
    assert plots[0]["plot_name"] == "North Field"
    assert plots[0]["soil_type"] == "Loamy Soil"

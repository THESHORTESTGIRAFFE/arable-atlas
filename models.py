from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class UserQuery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    soil_type = db.Column(db.String(50), nullable=False)
    climate = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())


class FarmPlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plot_name = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    soil_type = db.Column(db.String(50), nullable=True)
    ph = db.Column(db.String(20), nullable=True)
    moisture = db.Column(db.String(20), nullable=True)
    nitrogen = db.Column(db.String(20), nullable=True)
    recommendations = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())



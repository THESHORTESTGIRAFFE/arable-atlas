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


class FarmProfile(db.Model):
    """Session-owned report snapshots; keeps existing FarmPlot databases compatible."""
    id = db.Column(db.Integer, primary_key=True)
    plot_id = db.Column(db.Integer, db.ForeignKey('farm_plot.id'), nullable=False, unique=True)
    owner_id = db.Column(db.String(64), nullable=False, index=True)
    crop = db.Column(db.String(100), default='')
    planting_date = db.Column(db.String(10), default='')
    report = db.Column(db.JSON, nullable=False)
    plot = db.relationship(FarmPlot, backref=db.backref('profile', uselist=False, cascade='all, delete-orphan'))



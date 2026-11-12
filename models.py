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


class UssdDemoSession(db.Model):
    id = db.Column(db.String(48), primary_key=True)
    owner_id = db.Column(db.String(64), nullable=False, index=True)
    language = db.Column(db.String(5), nullable=False, default='en')
    area = db.Column(db.String(30), nullable=True)
    stage = db.Column(db.String(30), nullable=False, default='menu')
    pending_topic = db.Column(db.String(20), nullable=True)
    revision = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())


class DemoSms(db.Model):
    """A simulated SMS outbox. No real telephone number or delivery credentials."""
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.String(64), nullable=False, index=True)
    session_id = db.Column(db.String(48), db.ForeignKey('ussd_demo_session.id'), nullable=False, unique=True)
    language = db.Column(db.String(5), nullable=False)
    topic = db.Column(db.String(20), nullable=False)
    area = db.Column(db.String(30), nullable=False)
    question = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='queued')
    body = db.Column(db.Text, nullable=True)
    encoding = db.Column(db.String(10), nullable=True)
    segments = db.Column(db.Integer, nullable=True)
    source = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())



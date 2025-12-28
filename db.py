from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()

def init_db(app):
    # Snowflake Connection Configuration
    SNOWFLAKE_ACCOUNT = os.getenv('SNOWFLAKE_ACCOUNT')
    SNOWFLAKE_USER = os.getenv('SNOWFLAKE_USER')
    SNOWFLAKE_PASSWORD = os.getenv('SNOWFLAKE_PASSWORD')
    SNOWFLAKE_DATABASE = os.getenv('SNOWFLAKE_DATABASE')
    SNOWFLAKE_SCHEMA = os.getenv('SNOWFLAKE_SCHEMA')
    SNOWFLAKE_WAREHOUSE = os.getenv('SNOWFLAKE_WAREHOUSE')
    SNOWFLAKE_ROLE = os.getenv('SNOWFLAKE_ROLE')
    SECRET_KEY = os.getenv('SECRET_KEY')

    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"snowflake://{SNOWFLAKE_USER}:{SNOWFLAKE_PASSWORD}@"
        f"{SNOWFLAKE_ACCOUNT}/{SNOWFLAKE_DATABASE}/{SNOWFLAKE_SCHEMA}"
        f"?warehouse={SNOWFLAKE_WAREHOUSE}&role={SNOWFLAKE_ROLE}"
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'

from sqlalchemy import Sequence

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, Sequence('user_id_seq'), primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    name = db.Column(db.String(100))
    is_doctor = db.Column(db.Boolean, default=False)
    appointments = db.relationship('Appointment', backref='patient', lazy=True)
    # Using string for secondary table to avoid circular import issues if defined later, 
    # but since it's in the same file, 'favorites' object is fine if defined before or we use string 'favorites'
    favorite_doctors = db.relationship('Doctor', secondary='favorites')

class Doctor(db.Model):
    id = db.Column(db.Integer, Sequence('doctor_id_seq'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    specialization = db.Column(db.String(100))
    experience = db.Column(db.Integer)
    education = db.Column(db.Text)
    certifications = db.Column(db.Text)
    consultation_fee = db.Column(db.Float)
    rating = db.Column(db.Float, default=0.0)
    appointments = db.relationship('Appointment', backref='doctor', lazy=True)

class Appointment(db.Model):
    id = db.Column(db.Integer, Sequence('appointment_id_seq'), primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'))
    date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')
    description = db.Column(db.Text)
    approved_at = db.Column(db.DateTime)
    rejected_at = db.Column(db.DateTime)
    payment_method = db.Column(db.String(20))
    payment_details = db.Column(db.Text)
    payment_status = db.Column(db.String(20), default='pending')

class Rating(db.Model):
    id = db.Column(db.Integer, Sequence('rating_id_seq'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'))
    rating = db.Column(db.Integer)
    review = db.Column(db.Text)

class Message(db.Model):
    id = db.Column(db.Integer, Sequence('message_id_seq'), primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

favorites = db.Table('favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('doctor_id', db.Integer, db.ForeignKey('doctor.id'))
)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

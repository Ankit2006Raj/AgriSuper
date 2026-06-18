from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False, default='farmer')  # farmer, buyer, supplier, expert
    
    # Core Identity
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=True) # Making nullable to support legacy
    full_name = db.Column(db.String(100), nullable=True) # Supporting legacy
    
    # Contact
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Location
    state = db.Column(db.String(50), nullable=True)
    district = db.Column(db.String(50), nullable=True)
    village = db.Column(db.String(100), nullable=True)
    
    # Farm Info (Optional, mainly for farmers)
    farm_name = db.Column(db.String(100), nullable=True)
    farm_size = db.Column(db.Float, nullable=True)
    primary_crop = db.Column(db.String(50), nullable=True)
    experience = db.Column(db.Integer, nullable=True)

    # Buyer Info
    company_name = db.Column(db.String(100), nullable=True)
    gstin = db.Column(db.String(20), nullable=True)
    
    # Supplier Info
    business_name = db.Column(db.String(100), nullable=True)
    warehouse_address = db.Column(db.String(255), nullable=True)
    
    # Expert Info
    specialization = db.Column(db.String(100), nullable=True)
    qualifications = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Email Verification Fields
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_code = db.Column(db.String(6), nullable=True)
    
    # Password Reset OTP Fields
    reset_otp = db.Column(db.String(6), nullable=True)
    reset_otp_expiry = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f"<User {self.email} (Role: {self.role}, Verified: {self.is_verified})>"


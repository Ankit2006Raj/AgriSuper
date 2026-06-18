from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify
import os
import random
import string
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
from backend.models import db, User

load_dotenv()

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'agrisuper_secret_key_2024')
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Mail Configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@agrisuper.com')
mail = Mail(app)

# Database Configuration
db_url = os.environ.get('DATABASE_URL', 'sqlite:///agrisuper.db')
if "username:password@localhost:5432" in db_url:
    db_url = 'sqlite:///agrisuper.db'

# Test remote connection quickly before binding to SQLAlchemy
import sqlalchemy
try:
    if "postgres" in db_url or "neon.tech" in db_url:
        print(f"Testing connection to remote DB...")
        engine = sqlalchemy.create_engine(db_url, connect_args={'connect_timeout': 3})
        with engine.connect() as conn:
            pass
except Exception as e:
    print(f"Remote DB connection failed.")
    print("Falling back to local SQLite database...")
    db_url = 'sqlite:///agrisuper.db'

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
bcrypt = Bcrypt(app)

# Create tables on startup
with app.app_context():
    db.create_all()
    print(f"Database connected: {db_url[:50]}...")

# --- RBAC Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to access this page.", "danger")
                return redirect(url_for('login'))
            if session.get('role') not in roles:
                flash("You do not have permission to access this page.", "danger")
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Email Helper ---
def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))

def send_otp_email(recipient_email, otp, purpose='verification'):
    """Send OTP email with branded AgriSuper template"""
    if purpose == 'verification':
        subject = 'Verify Your AgriSuper Account'
        heading = 'Email Verification'
        message_text = 'Welcome to AgriSuper! Please use the following OTP to verify your email address and activate your account.'
    elif purpose == 'reset':
        subject = 'Password Reset OTP - AgriSuper'
        heading = 'Password Reset'
        message_text = 'You requested a password reset for your AgriSuper account. Use the following OTP to reset your password. This code expires in 10 minutes.'
    else:
        subject = 'Your AgriSuper OTP'
        heading = 'OTP Code'
        message_text = 'Here is your one-time password for AgriSuper.'

    html_body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(14,56,41,0.10);">
        <div style="background: linear-gradient(135deg, #0e3829 0%, #1b4d3e 100%); padding: 36px 32px 28px; text-align: center;">
            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 800; letter-spacing: -0.5px;">
                🌱 Agri<span style="color: #c69c59;">Super</span>
            </h1>
            <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0; font-size: 14px;">{heading}</p>
        </div>
        <div style="padding: 36px 32px;">
            <p style="color: #333; font-size: 15px; line-height: 1.6; margin: 0 0 24px;">{message_text}</p>
            <div style="background: linear-gradient(135deg, #f0faf4 0%, #e8f5e9 100%); border: 2px dashed #0e3829; border-radius: 12px; padding: 24px; text-align: center; margin: 0 0 24px;">
                <p style="color: #666; font-size: 12px; text-transform: uppercase; letter-spacing: 2px; margin: 0 0 8px; font-weight: 600;">Your OTP Code</p>
                <h2 style="color: #0e3829; font-size: 36px; letter-spacing: 8px; margin: 0; font-weight: 800;">{otp}</h2>
            </div>
            <p style="color: #999; font-size: 13px; line-height: 1.5; margin: 0;">
                ⏰ This code is valid for <strong>10 minutes</strong>.<br>
                If you didn't request this, please ignore this email.
            </p>
        </div>
        <div style="background: #f8f9fa; padding: 20px 32px; text-align: center; border-top: 1px solid #eee;">
            <p style="color: #999; font-size: 12px; margin: 0;">© 2026 AgriSuper Ecosystem. All rights reserved.</p>
        </div>
    </div>
    """

    sender = app.config.get('MAIL_DEFAULT_SENDER')
    msg = Message(subject, sender=sender, recipients=[recipient_email])
    msg.html = html_body
    msg.body = f"{heading}\n\nYour OTP code is: {otp}\n\nThis code is valid for 10 minutes.\nIf you didn't request this, please ignore this email.\n\n© 2026 AgriSuper Ecosystem"
    try:
        mail.send(msg)
    except Exception as e:
        print(f"Error sending email to {recipient_email}: {e}")
        raise e

# --- Authentication Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    active_tab = request.args.get('tab', 'login')
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            if not user.is_verified:
                # Resend OTP for unverified users
                otp = generate_otp()
                user.verification_code = otp
                db.session.commit()
                try:
                    send_otp_email(user.email, otp, purpose='verification')
                except Exception:
                    pass
                flash("Your email is not verified. We've sent a new verification code.", "warning")
                return redirect(url_for('verify_email', user_id=user.id))
            session.permanent = remember
            session['user_id'] = user.id
            session['username'] = user.first_name
            session['role'] = user.role
            flash(f"Welcome back, {user.first_name}!", "success")
            return redirect(url_for('dashboard'))
        else:
            return render_template('auth/login_register.html', login_error="Invalid email or password. Please try again.", active_tab='login')
    return render_template('auth/login_register.html', active_tab=active_tab)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        # Get form data
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'farmer')
        
        # Validation
        if not all([first_name, last_name, phone, email, password]):
            return render_template('auth/login_register.html', register_error="All required fields must be filled.", active_tab='register')
        
        if len(password) < 8:
            return render_template('auth/login_register.html', register_error="Password must be at least 8 characters long.", active_tab='register')
        
        if password != confirm_password:
            return render_template('auth/login_register.html', register_error="Passwords do not match.", active_tab='register')
        
        # Check for existing user
        existing_user = User.query.filter((User.email == email) | (User.phone == phone)).first()
        if existing_user:
            if existing_user.email == email:
                return render_template('auth/login_register.html', register_error="An account with this email already exists.", active_tab='register')
            else:
                return render_template('auth/login_register.html', register_error="An account with this phone number already exists.", active_tab='register')
        
        # Create user
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        otp = generate_otp()
        
        new_user = User(  # type: ignore
            role=role,
            first_name=first_name,
            last_name=last_name,
            username=email.split('@')[0],
            phone=phone,
            email=email,
            password_hash=hashed_password,
            verification_code=otp,
            is_verified=False
        )
        db.session.add(new_user)
        db.session.commit()
        
        # Send verification email
        try:
            send_otp_email(email, otp, purpose='verification')
            flash("Registration successful! A verification code has been sent to your email.", "success")
        except Exception as e:
            flash(f"Account created but email sending failed. Please use 'Resend OTP' on the verification page.", "warning")
        
        return redirect(url_for('verify_email', user_id=new_user.id))
        
    # GET request: redirect to combined page with register tab
    return redirect(url_for('login', tab='register'))

@app.route('/verify-email/<int:user_id>', methods=['GET', 'POST'])
def verify_email(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_verified:
        flash("Email already verified. Please login.", "info")
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        otp_entered = request.form.get('otp', '').strip()
        if not otp_entered or len(otp_entered) != 6:
            return render_template('auth/verify_email.html', email=user.email, user_id=user.id, verify_error="Please enter a valid 6-digit code.")
        
        if otp_entered == user.verification_code:
            user.is_verified = True
            user.verification_code = None
            db.session.commit()
            
            flash("Email verified successfully! Please log in to continue.", "success")
            return redirect(url_for('login'))
        else:
            return render_template('auth/verify_email.html', email=user.email, user_id=user.id, verify_error="Invalid verification code. Please try again.")
            
    return render_template('auth/verify_email.html', email=user.email, user_id=user.id)

@app.route('/resend-otp/<int:user_id>', methods=['POST'])
def resend_verification_otp(user_id):
    """Resend verification OTP for email verification"""
    user = User.query.get_or_404(user_id)
    if user.is_verified:
        flash("Email already verified.", "info")
        return redirect(url_for('login'))
    
    otp = generate_otp()
    user.verification_code = otp
    db.session.commit()
    
    try:
        send_otp_email(user.email, otp, purpose='verification')
        flash("A new verification code has been sent to your email.", "success")
    except Exception as e:
        flash("Failed to send email. Please check your email address and try again.", "danger")
    
    return redirect(url_for('verify_email', user_id=user.id))

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        
        if user:
            otp = generate_otp()
            user.reset_otp = otp
            user.reset_otp_expiry = datetime.utcnow() + timedelta(minutes=10)
            db.session.commit()
            
            try:
                send_otp_email(email, otp, purpose='reset')
                flash("A password reset OTP has been sent to your email.", "success")
            except Exception as e:
                flash("Failed to send reset email. Please try again later.", "danger")
                return render_template('auth/forgot_password.html')
            
            return redirect(url_for('reset_password', email=email))
        else:
            # Don't reveal if email exists — show same message
            flash("If an account with that email exists, a reset OTP has been sent.", "info")
            return render_template('auth/forgot_password.html')
    
    return render_template('auth/forgot_password.html')

@app.route('/resend-reset-otp', methods=['POST'])
def resend_reset_otp():
    """Resend password reset OTP"""
    email = request.form.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    
    if user:
        otp = generate_otp()
        user.reset_otp = otp
        user.reset_otp_expiry = datetime.utcnow() + timedelta(minutes=10)
        db.session.commit()
        
        try:
            send_otp_email(email, otp, purpose='reset')
            flash("A new reset OTP has been sent to your email.", "success")
        except Exception:
            flash("Failed to send email. Please try again.", "danger")
    else:
        flash("A new reset OTP has been sent if the account exists.", "info")
    
    return redirect(url_for('reset_password', email=email))

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email', '') or request.form.get('email', '')
    
    if not email:
        flash("Invalid reset request. Please start the process again.", "danger")
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        otp_entered = request.form.get('otp', '').strip()
        new_password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not otp_entered or len(otp_entered) != 6:
            return render_template('auth/reset_password.html', email=email, reset_error="Please enter a valid 6-digit OTP.")
        
        user = User.query.filter_by(email=email).first()
        if not user:
            return render_template('auth/reset_password.html', email=email, reset_error="No account found with this email.")
        
        # Check OTP validity
        if user.reset_otp != otp_entered:
            return render_template('auth/reset_password.html', email=email, reset_error="Invalid OTP. Please try again.")
        
        if user.reset_otp_expiry and user.reset_otp_expiry < datetime.utcnow():
            return render_template('auth/reset_password.html', email=email, reset_error="OTP has expired. Please request a new one.")
        
        # Validate new password
        if len(new_password) < 8:
            return render_template('auth/reset_password.html', email=email, reset_error="Password must be at least 8 characters long.")
        
        if new_password != confirm_password:
            return render_template('auth/reset_password.html', email=email, reset_error="Passwords do not match.")
        
        # Update password
        user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
        user.reset_otp = None
        user.reset_otp_expiry = None
        db.session.commit()
        
        flash("Your password has been reset successfully! You can now login.", "success")
        return redirect(url_for('login'))
    
    return render_template('auth/reset_password.html', email=email)


# --- Context Processor: Inject auth state into all templates ---
@app.context_processor
def inject_user():
    return {
        'is_logged_in': 'user_id' in session,
        'current_user_name': session.get('username', ''),
        'current_user_role': session.get('role', ''),
    }

# --- Core Routes ---
@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/profile')
@login_required
def user_profile():
    user = User.query.get(session['user_id'])
    return render_template('user_profile.html', user=user)

@app.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    user = User.query.get(session['user_id'])
    
    # Common fields
    user.full_name = request.form.get('full_name', user.full_name)
    user.phone = request.form.get('phone', user.phone)
    user.email = request.form.get('email', user.email)
    
    # Role specific fields
    role = user.role
    if role == 'farmer':
        user.farm_name = request.form.get('farm_name', user.farm_name)
        farm_size_val = request.form.get('farm_size')
        if farm_size_val == "":
            user.farm_size = None
        elif farm_size_val is not None:
            try:
                user.farm_size = float(farm_size_val)
            except ValueError:
                pass
    elif role == 'buyer':
        user.company_name = request.form.get('company_name', user.company_name)
        user.gstin = request.form.get('gstin', user.gstin)
    elif role == 'supplier':
        user.business_name = request.form.get('business_name', user.business_name)
        user.warehouse_address = request.form.get('warehouse_address', user.warehouse_address)
    elif role == 'expert':
        user.specialization = request.form.get('specialization', user.specialization)
        user.qualifications = request.form.get('qualifications', user.qualifications)
        
    db.session.commit()
    return jsonify({'success': True, 'message': 'Profile updated successfully'})


@app.route('/settings')
@login_required
def user_settings():
    user = User.query.get(session['user_id'])
    return render_template('user_settings.html', user=user)


@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'farmer':
        return render_template('dashboards/farmer_dashboard.html')
    elif role == 'buyer':
        return render_template('dashboards/buyer_dashboard.html')
    elif role == 'supplier':
        return render_template('dashboards/supplier_dashboard.html')
    elif role == 'expert':
        return render_template('dashboards/expert_dashboard.html')
    return redirect(url_for('landing'))

@app.route('/categorized-dashboard')
@login_required
def categorized_dashboard():
    return render_template('categorized_dashboard.html')

@app.route('/search')
@login_required
def search():
    return render_template('search.html')

@app.route('/notifications')
@login_required
def notifications():
    return render_template('notifications.html')

@app.route('/submit-question', methods=['POST'])
@login_required
def submit_question():
    return redirect(url_for('community_forum'))
    
@app.route('/submit-answer/<question_id>', methods=['POST'])
@login_required
def submit_answer(question_id):
    return redirect(url_for('view_question', question_id=question_id))

# --- Feature Routes ---

@app.route('/admin-dashboard')
@role_required('admin')
def admin_dashboard():
    return render_template('dashboards/admin_dashboard.html')

@app.route('/bulk-deals')
@login_required
def bulk_deals():
    return render_template('features/bulk_deals.html')

@app.route('/buyer-ratings')
@login_required
def buyer_ratings():
    return render_template('features/buyer_ratings.html')

@app.route('/carbon-credits')
@login_required
def carbon_credits():
    return render_template('features/carbon_credits.html')

@app.route('/community-forum')
@login_required
def community_forum():
    categories = [
        'Crop Diseases', 'Pest Control', 'Soil Health', 'Irrigation', 
        'Fertilizers', 'Weather', 'Market Prices', 'Government Schemes'
    ]
    
    forum_stats = {
        'members': '12,500+',
        'questions': '4,320',
        'answers': '18,400',
        'avg_response_time': '2.5 hours',
        'satisfaction_rate': '96%'
    }
    
    questions = [
        {
            'id': 1,
            'category': 'Crop Diseases',
            'status': 'Answered',
            'posted_date': '2 hours ago',
            'title': 'Yellow spots on tomato leaves',
            'question': 'My tomato plants have started developing yellow spots with dark centers on the lower leaves. What could this be and how do I treat it?',
            'farmer_name': 'Ramesh Kumar',
            'farmer_location': 'Punjab',
            'answers': [1, 2],
            'views': 45,
            'likes': 12
        },
        {
            'id': 2,
            'category': 'Fertilizers',
            'status': 'Open',
            'posted_date': '5 hours ago',
            'title': 'Best NPK ratio for flowering stage of cotton?',
            'question': 'My cotton crop is entering the flowering stage. What NPK ratio is recommended at this time to maximize yield without causing excessive vegetative growth?',
            'farmer_name': 'Suresh Patel',
            'farmer_location': 'Gujarat',
            'answers': [],
            'views': 89,
            'likes': 5
        }
    ]
    
    category_counts = {
        'Crop Diseases': 1420,
        'Pest Control': 980,
        'Soil Health': 540,
        'Irrigation': 320,
        'Fertilizers': 460,
        'Weather': 210,
        'Market Prices': 290,
        'Government Schemes': 100
    }
    
    return render_template('features/community_forum.html', 
                          categories=categories, 
                          forum_stats=forum_stats, 
                          questions=questions, 
                          category_counts=category_counts)

@app.route('/community-forum/question/<int:question_id>/upvote', methods=['POST'])
@login_required
def upvote_question(question_id):
    flash(f"Upvoted question {question_id}!", "success")
    return redirect(url_for('community_forum'))

@app.route('/contract-farming')
@login_required
def contract_farming():
    return render_template('features/contract_farming.html')

@app.route('/crop-insurance')
@login_required
def crop_insurance():
    return render_template('features/crop_insurance.html')

@app.route('/crop-management')
@login_required
def crop_management():
    return render_template('features/crop_management.html')

@app.route('/crop-rotation')
@login_required
def crop_rotation():
    return render_template('features/crop_rotation.html')

@app.route('/digital-wallet')
@login_required
def digital_wallet():
    return render_template('features/digital_wallet.html')

@app.route('/disaster-alerts')
@login_required
def disaster_alerts():
    return render_template('features/disaster_alerts.html')

@app.route('/elearning-courses')
@login_required
def elearning_courses():
    return render_template('features/elearning_courses.html')

@app.route('/emi-purchase')
@login_required
def emi_purchase():
    return render_template('features/emi_purchase.html')

@app.route('/equipment-management')
@login_required
def equipment_management():
    return render_template('features/equipment_management.html')

@app.route('/equipment-rental')
@login_required
def equipment_rental():
    return render_template('features/equipment_rental.html')

@app.route('/export-gateway')
@login_required
def export_gateway():
    return render_template('features/export_gateway.html')

@app.route('/farmer-groups')
@login_required
def farmer_groups():
    return render_template('features/farmer_groups.html')

@app.route('/farmer-to-farmer-trade')
@login_required
def farmer_to_farmer_trade():
    return render_template('features/farmer_to_farmer_trade.html')

@app.route('/fertilizer-price-comparison')
@login_required
def fertilizer_price_comparison():
    return render_template('features/fertilizer_price_comparison.html')

@app.route('/financial-management')
@login_required
def financial_management():
    return render_template('features/financial_management.html')

@app.route('/fraud-detection')
@login_required
def fraud_detection():
    return render_template('features/fraud_detection.html')

@app.route('/id-verification')
@login_required
def id_verification():
    return render_template('features/id_verification.html')

@app.route('/market-comparison')
@login_required
def market_comparison():
    return render_template('features/market_comparison.html')

@app.route('/market-prices')
@login_required
def market_prices():
    return render_template('features/market_prices.html')

@app.route('/mentorship')
@login_required
def mentorship():
    return render_template('features/mentorship.html')

@app.route('/multilanguage')
@login_required
def multilanguage():
    return render_template('features/multilanguage.html')

@app.route('/offline-sms')
@login_required
def offline_sms():
    return render_template('features/offline_sms.html')

@app.route('/organic-farming')
@login_required
def organic_farming():
    return render_template('features/organic_farming.html')

@app.route('/organic-marketplace')
@login_required
def organic_marketplace():
    return render_template('features/organic_marketplace.html')

@app.route('/pest-alerts')
@login_required
def pest_alerts():
    return render_template('features/pest_alerts.html')

@app.route('/pricing-engine')
@login_required
def pricing_engine():
    return render_template('features/pricing_engine.html')

@app.route('/profit-analyzer')
@login_required
def profit_analyzer():
    return render_template('features/profit_analyzer.html')

@app.route('/quality-certification')
@login_required
def quality_certification():
    return render_template('features/quality_certification.html')

@app.route('/question/<question_id>')
@login_required
def view_question(question_id):
    return render_template('features/question_detail.html')

@app.route('/route-optimization')
@login_required
def route_optimization():
    return render_template('features/route_optimization.html')

@app.route('/secondhand-marketplace')
@login_required
def secondhand_marketplace():
    return render_template('features/secondhand_marketplace.html')

@app.route('/shared-logistics')
@login_required
def shared_logistics():
    return render_template('features/shared_logistics.html')

@app.route('/smart-contracts')
@login_required
def smart_contracts():
    return render_template('features/smart_contracts.html')

@app.route('/soil-health')
@login_required
def soil_health():
    return render_template('features/soil_health.html')

@app.route('/soil-knowledge')
@login_required
def soil_knowledge():
    return render_template('features/soil_knowledge.html')

@app.route('/sowing-calendar')
@login_required
def sowing_calendar():
    return render_template('features/sowing_calendar.html')

@app.route('/storage-booking')
@login_required
def storage_booking():
    return render_template('features/storage_booking.html')

@app.route('/subscription-model')
@login_required
def subscription_model():
    return render_template('features/subscription_model.html')

@app.route('/success-stories')
@login_required
def success_stories():
    return render_template('features/success_stories.html')

@app.route('/voice-assistant')
@login_required
def voice_assistant():
    return render_template('features/voice_assistant.html')

@app.route('/water-conservation')
@login_required
def water_conservation():
    return render_template('features/water_conservation.html')

@app.route('/weather-alerts')
@login_required
def weather_alerts():
    return render_template('features/weather_alerts.html')

@app.route('/yield-prediction')
@login_required
def yield_prediction():
    return render_template('features/yield_prediction.html')

if __name__ == '__main__':
    print("Starting AgriSuper App server with DB & RBAC...")
    app.run(debug=True, host='0.0.0.0', port=5000)

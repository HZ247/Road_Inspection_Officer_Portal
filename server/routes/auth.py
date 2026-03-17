import bcrypt
import jwt
import datetime
from flask import Blueprint, request, jsonify
from server.database import get_db
from server.auth_middleware import JWT_SECRET, authenticate_token

auth_bp = Blueprint('auth', __name__)


# ── POST /api/auth/register ────────────────────────────────
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    name        = (data.get('name') or '').strip()
    employee_id = (data.get('employee_id') or '').strip().upper()
    designation = (data.get('designation') or '').strip()
    department  = (data.get('department') or '').strip()
    mobile      = (data.get('mobile') or '').strip()
    password    = data.get('password') or ''

    # Validation
    if not name or not employee_id or not password:
        return jsonify({'error': 'Name, Employee ID and Password are required.'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters.'}), 400

    conn = get_db()
    try:
        existing = conn.execute(
            'SELECT id FROM users WHERE employee_id = ?', (employee_id,)
        ).fetchone()

        if existing:
            return jsonify({'error': 'Employee ID is already registered.'}), 400

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        conn.execute('''
            INSERT INTO users (name, employee_id, designation, department, mobile, password, role, otp_verified)
            VALUES (?, ?, ?, ?, ?, ?, 'fvo', 0)
        ''', (name, employee_id, designation, department, mobile, hashed))
        conn.commit()

        return jsonify({'success': True, 'message': 'Registered! Please verify OTP to activate your account.'})

    except Exception as e:
        print('Register error:', e)
        return jsonify({'error': 'Registration failed. Try again.'}), 500
    finally:
        conn.close()


# ── POST /api/auth/verify-otp ──────────────────────────────
# Mocked: any 6-digit OTP passes for prototype
@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    data        = request.get_json()
    employee_id = (data.get('employee_id') or '').strip().upper()
    otp         = str(data.get('otp') or '').strip()

    if not employee_id or not otp:
        return jsonify({'error': 'Employee ID and OTP are required.'}), 400
    if len(otp) != 6 or not otp.isdigit():
        return jsonify({'error': 'OTP must be exactly 6 digits.'}), 400

    conn = get_db()
    try:
        user = conn.execute(
            'SELECT id FROM users WHERE employee_id = ?', (employee_id,)
        ).fetchone()

        if not user:
            return jsonify({'error': 'Employee ID not found.'}), 404

        # Accept any 6-digit OTP (prototype mock)
        conn.execute(
            'UPDATE users SET otp_verified = 1 WHERE employee_id = ?', (employee_id,)
        )
        conn.commit()

        return jsonify({'success': True, 'message': 'OTP verified! You can now login.'})
    finally:
        conn.close()


# ── POST /api/auth/login ───────────────────────────────────
@auth_bp.route('/login', methods=['POST'])
def login():
    data        = request.get_json()
    employee_id = (data.get('employee_id') or '').strip().upper()
    password    = data.get('password') or ''

    if not employee_id or not password:
        return jsonify({'error': 'Employee ID and Password are required.'}), 400

    conn = get_db()
    try:
        user = conn.execute(
            'SELECT * FROM users WHERE employee_id = ?', (employee_id,)
        ).fetchone()

        if not user:
            return jsonify({'error': 'Invalid Employee ID or password.'}), 401
        if not user['otp_verified']:
            return jsonify({'error': 'Account not verified. Please complete OTP verification.'}), 401

        password_match = bcrypt.checkpw(password.encode(), user['password'].encode())
        if not password_match:
            return jsonify({'error': 'Invalid Employee ID or password.'}), 401

        # Sign JWT — expires in 8 hours (one working shift)
        payload = {
            'id':          user['id'],
            'employee_id': user['employee_id'],
            'name':        user['name'],
            'role':        user['role'],
            'exp':         datetime.datetime.utcnow() + datetime.timedelta(hours=8)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')

        return jsonify({
            'success':     True,
            'token':       token,
            'role':        user['role'],
            'name':        user['name'],
            'employee_id': user['employee_id']
        })
    finally:
        conn.close()


# ── GET /api/auth/me ───────────────────────────────────────
@auth_bp.route('/me', methods=['GET'])
@authenticate_token
def me():
    return jsonify({'success': True, 'user': request.user})
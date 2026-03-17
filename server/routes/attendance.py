from flask import Blueprint, request, jsonify
from server.database import get_db
from server.auth_middleware import authenticate_token, require_admin
from datetime import datetime, timezone

attendance_bp = Blueprint('attendance', __name__)


def now_ist():
    """Return current datetime string in IST (UTC+5:30)."""
    from datetime import timedelta
    utc_now = datetime.now(timezone.utc)
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    return ist_now.strftime('%Y-%m-%d %H:%M:%S'), ist_now.strftime('%Y-%m-%d')


# ── POST /api/attendance/checkin ───────────────────────────
@attendance_bp.route('/checkin', methods=['POST'])
@authenticate_token
def checkin():
    data = request.get_json()
    lat  = data.get('lat')
    lng  = data.get('lng')

    if lat is None or lng is None:
        return jsonify({'error': 'GPS coordinates are required.'}), 400

    user_id     = request.user['id']
    employee_id = request.user['employee_id']
    time_str, date_str = now_ist()

    conn = get_db()
    try:
        # Check if already checked in today without checkout
        existing = conn.execute('''
            SELECT id, checkout_time FROM attendance
            WHERE employee_id = ? AND date = ?
            ORDER BY id DESC LIMIT 1
        ''', (employee_id, date_str)).fetchone()

        if existing and existing['checkout_time'] is None:
            return jsonify({'error': 'You are already checked in. Please check out first.'}), 400

        conn.execute('''
            INSERT INTO attendance (user_id, employee_id, checkin_time, checkin_lat, checkin_lng, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, employee_id, time_str, lat, lng, date_str))
        conn.commit()

        return jsonify({
            'success':      True,
            'message':      'Checked in successfully!',
            'checkin_time': time_str,
            'lat':          lat,
            'lng':          lng
        })
    finally:
        conn.close()


# ── POST /api/attendance/checkout ──────────────────────────
@attendance_bp.route('/checkout', methods=['POST'])
@authenticate_token
def checkout():
    data = request.get_json()
    lat  = data.get('lat')
    lng  = data.get('lng')

    if lat is None or lng is None:
        return jsonify({'error': 'GPS coordinates are required.'}), 400

    employee_id = request.user['employee_id']
    time_str, date_str = now_ist()

    conn = get_db()
    try:
        # Find today's open check-in
        record = conn.execute('''
            SELECT id, checkin_time FROM attendance
            WHERE employee_id = ? AND date = ? AND checkout_time IS NULL
            ORDER BY id DESC LIMIT 1
        ''', (employee_id, date_str)).fetchone()

        if not record:
            return jsonify({'error': 'No active check-in found. Please check in first.'}), 400

        # Calculate duration in minutes
        checkin_dt  = datetime.strptime(record['checkin_time'], '%Y-%m-%d %H:%M:%S')
        checkout_dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        duration    = int((checkout_dt - checkin_dt).total_seconds() / 60)

        conn.execute('''
            UPDATE attendance
            SET checkout_time = ?, checkout_lat = ?, checkout_lng = ?, duration_mins = ?
            WHERE id = ?
        ''', (time_str, lat, lng, duration, record['id']))
        conn.commit()

        hours   = duration // 60
        minutes = duration % 60

        return jsonify({
            'success':       True,
            'message':       'Checked out successfully!',
            'checkout_time': time_str,
            'duration':      f'{hours}h {minutes}m'
        })
    finally:
        conn.close()


# ── GET /api/attendance/today ──────────────────────────────
@attendance_bp.route('/today', methods=['GET'])
@authenticate_token
def today():
    employee_id = request.user['employee_id']
    _, date_str = now_ist()

    conn = get_db()
    try:
        record = conn.execute('''
            SELECT * FROM attendance
            WHERE employee_id = ? AND date = ?
            ORDER BY id DESC LIMIT 1
        ''', (employee_id, date_str)).fetchone()

        if not record:
            return jsonify({'success': True, 'status': 'not_checked_in', 'record': None})

        status = 'checked_in' if record['checkout_time'] is None else 'checked_out'

        return jsonify({
            'success': True,
            'status':  status,
            'record':  dict(record)
        })
    finally:
        conn.close()


# ── GET /api/attendance/history ────────────────────────────
@attendance_bp.route('/history', methods=['GET'])
@authenticate_token
def history():
    employee_id = request.user['employee_id']

    conn = get_db()
    try:
        records = conn.execute('''
            SELECT * FROM attendance
            WHERE employee_id = ?
            ORDER BY id DESC
            LIMIT 30
        ''', (employee_id,)).fetchall()

        return jsonify({'success': True, 'records': [dict(r) for r in records]})
    finally:
        conn.close()


# ── GET /api/attendance/all  (admin only) ──────────────────
@attendance_bp.route('/all', methods=['GET'])
@authenticate_token
@require_admin
def all_attendance():
    conn = get_db()
    try:
        records = conn.execute('''
            SELECT a.*, u.name, u.designation, u.department
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            ORDER BY a.id DESC
            LIMIT 100
        ''').fetchall()

        return jsonify({'success': True, 'records': [dict(r) for r in records]})
    finally:
        conn.close()
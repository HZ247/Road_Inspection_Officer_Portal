from flask import Blueprint, request, jsonify
from server.database import get_db
from server.auth_middleware import authenticate_token, require_admin
from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename
import os, uuid, json

inspection_bp = Blueprint('inspection', __name__)

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'uploads'))

def now_ist():
    utc_now = datetime.now(timezone.utc)
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    return ist_now.strftime('%Y-%m-%d %H:%M:%S'), ist_now.strftime('%Y-%m-%d')


# ── POST /api/inspection/start ─────────────────────────────
@inspection_bp.route('/start', methods=['POST'])
@authenticate_token
def start():
    data        = request.get_json()
    site_name   = (data.get('site_name')   or '').strip()
    road_name   = (data.get('road_name')   or '').strip()
    contract_id = (data.get('contract_id') or '').strip()
    start_lat   = data.get('start_lat')
    start_lng   = data.get('start_lng')

    if not site_name or not road_name:
        return jsonify({'error': 'Site name and road name are required.'}), 400
    if start_lat is None or start_lng is None:
        return jsonify({'error': 'GPS coordinates are required to start.'}), 400

    user_id     = request.user['id']
    employee_id = request.user['employee_id']
    time_str, date_str = now_ist()

    conn = get_db()
    try:
        cur = conn.execute('''
            INSERT INTO inspections
              (user_id, employee_id, site_name, road_name, contract_id,
               start_time, start_lat, start_lng, status, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
        ''', (user_id, employee_id, site_name, road_name, contract_id,
              time_str, start_lat, start_lng, date_str))
        conn.commit()

        return jsonify({
            'success':       True,
            'inspection_id': cur.lastrowid,
            'start_time':    time_str,
            'message':       'Inspection started. Camera and GPS trail are now active.'
        })
    finally:
        conn.close()


# ── POST /api/inspection/photo ─────────────────────────────
@inspection_bp.route('/photo', methods=['POST'])
@authenticate_token
def upload_photo():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded.'}), 400

    file          = request.files['file']
    inspection_id = request.form.get('inspection_id')
    lat           = request.form.get('lat')
    lng           = request.form.get('lng')
    sequence      = request.form.get('sequence', 1)

    if not inspection_id:
        return jsonify({'error': 'inspection_id is required.'}), 400

    # Unique filename: insp_<id>_<uuid>.jpg
    filename = f"insp_{inspection_id}_{uuid.uuid4().hex[:10]}.jpg"
    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)

    time_str, _ = now_ist()

    conn = get_db()
    try:
        # Verify inspection belongs to this officer
        insp = conn.execute(
            'SELECT id, employee_id FROM inspections WHERE id = ?', (inspection_id,)
        ).fetchone()

        if not insp or insp['employee_id'] != request.user['employee_id']:
            os.remove(filepath)
            return jsonify({'error': 'Inspection not found or access denied.'}), 403

        conn.execute('''
            INSERT INTO inspection_photos
              (inspection_id, filename, lat, lng, captured_at, sequence)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (inspection_id, filename,
              float(lat) if lat else None,
              float(lng) if lng else None,
              time_str, int(sequence)))

        # Update photo count on inspection
        conn.execute('''
            UPDATE inspections
            SET photo_count = photo_count + 1
            WHERE id = ?
        ''', (inspection_id,))

        conn.commit()

        return jsonify({
            'success':  True,
            'filename': filename,
            'url':      f'/uploads/{filename}',
            'message':  'Photo saved.'
        })
    finally:
        conn.close()


# ── POST /api/inspection/submit ────────────────────────────
@inspection_bp.route('/submit', methods=['POST'])
@authenticate_token
def submit():
    data          = request.get_json()
    inspection_id = data.get('inspection_id')
    gps_trail     = data.get('gps_trail', [])
    remarks       = (data.get('remarks') or '').strip()

    if not inspection_id:
        return jsonify({'error': 'inspection_id is required.'}), 400

    employee_id = request.user['employee_id']
    time_str, _ = now_ist()

    # Calculate coverage: 20 trail points = 100% (1 point per 30s = 10 min walk)
    trail_count      = len(gps_trail)
    coverage_percent = min(100, round(trail_count / 20 * 100))

    conn = get_db()
    try:
        insp = conn.execute(
            'SELECT id, employee_id, status FROM inspections WHERE id = ?',
            (inspection_id,)
        ).fetchone()

        if not insp:
            return jsonify({'error': 'Inspection not found.'}), 404
        if insp['employee_id'] != employee_id:
            return jsonify({'error': 'Access denied.'}), 403
        if insp['status'] != 'active':
            return jsonify({'error': 'Inspection already submitted.'}), 400

        conn.execute('''
            UPDATE inspections
            SET end_time = ?, gps_trail = ?, remarks = ?,
                coverage_percent = ?, status = 'submitted'
            WHERE id = ?
        ''', (time_str, json.dumps(gps_trail), remarks, coverage_percent, inspection_id))
        conn.commit()

        return jsonify({
            'success':          True,
            'message':          'Inspection submitted successfully!',
            'coverage_percent': coverage_percent,
            'trail_points':     trail_count
        })
    finally:
        conn.close()


# ── GET /api/inspection/history ────────────────────────────
@inspection_bp.route('/history', methods=['GET'])
@authenticate_token
def history():
    employee_id = request.user['employee_id']
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT id, site_name, road_name, contract_id, date,
                   start_time, end_time, photo_count,
                   coverage_percent, status, remarks
            FROM inspections
            WHERE employee_id = ?
            ORDER BY id DESC LIMIT 30
        ''', (employee_id,)).fetchall()

        return jsonify({'success': True, 'records': [dict(r) for r in rows]})
    finally:
        conn.close()


# ── GET /api/inspection/<id> ───────────────────────────────
@inspection_bp.route('/<int:insp_id>', methods=['GET'])
@authenticate_token
def get_inspection(insp_id):
    conn = get_db()
    try:
        insp = conn.execute(
            'SELECT * FROM inspections WHERE id = ?', (insp_id,)
        ).fetchone()

        if not insp:
            return jsonify({'error': 'Not found.'}), 404

        # Only owner or admin can view
        if insp['employee_id'] != request.user['employee_id'] and request.user['role'] != 'admin':
            return jsonify({'error': 'Access denied.'}), 403

        photos = conn.execute('''
            SELECT filename, lat, lng, captured_at, sequence
            FROM inspection_photos
            WHERE inspection_id = ?
            ORDER BY sequence ASC
        ''', (insp_id,)).fetchall()

        result = dict(insp)
        result['photos'] = [dict(p) for p in photos]
        if result.get('gps_trail'):
            result['gps_trail'] = json.loads(result['gps_trail'])

        return jsonify({'success': True, 'inspection': result})
    finally:
        conn.close()


# ── GET /api/inspection/all  (admin only) ──────────────────
@inspection_bp.route('/all', methods=['GET'])
@authenticate_token
@require_admin
def all_inspections():
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT i.id, i.site_name, i.road_name, i.date,
                   i.photo_count, i.coverage_percent, i.status,
                   i.start_time, i.end_time,
                   u.name, u.employee_id, u.designation
            FROM inspections i
            JOIN users u ON i.user_id = u.id
            ORDER BY i.id DESC LIMIT 100
        ''').fetchall()

        return jsonify({'success': True, 'records': [dict(r) for r in rows]})
    finally:
        conn.close()


# ── PATCH /api/inspection/<id>/review  (admin only) ────────
@inspection_bp.route('/<int:insp_id>/review', methods=['PATCH'])
@authenticate_token
@require_admin
def review(insp_id):
    data         = request.get_json()
    action       = data.get('action')       # 'approve' or 'flag'
    admin_remark = data.get('admin_remarks', '')

    if action not in ('approve', 'flag'):
        return jsonify({'error': "Action must be 'approve' or 'flag'."}), 400

    new_status = 'approved' if action == 'approve' else 'flagged'

    conn = get_db()
    try:
        conn.execute('''
            UPDATE inspections
            SET status = ?, admin_remarks = ?
            WHERE id = ?
        ''', (new_status, admin_remark, insp_id))
        conn.commit()
        return jsonify({'success': True, 'status': new_status})
    finally:
        conn.close()
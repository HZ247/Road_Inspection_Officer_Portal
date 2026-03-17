from flask import Blueprint, request, jsonify
from server.database import get_db
from server.auth_middleware import authenticate_token, require_admin
from datetime import datetime, timezone, timedelta
import json

material_bp = Blueprint('material', __name__)

def now_ist():
    utc_now = datetime.now(timezone.utc)
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    return ist_now.strftime('%Y-%m-%d %H:%M:%S'), ist_now.strftime('%Y-%m-%d')


# ── GET /api/material/contracts ────────────────────────────
# Returns list of all contracts for dropdown
@material_bp.route('/contracts', methods=['GET'])
@authenticate_token
def list_contracts():
    conn = get_db()
    try:
        rows = conn.execute(
            'SELECT contract_id, project_name, location, contractor FROM contracts ORDER BY contract_id'
        ).fetchall()
        return jsonify({'success': True, 'contracts': [dict(r) for r in rows]})
    finally:
        conn.close()


# ── GET /api/material/items/<contract_id> ──────────────────
# Returns all material items for a contract grouped by category
@material_bp.route('/items/<contract_id>', methods=['GET'])
@authenticate_token
def get_items(contract_id):
    conn = get_db()
    try:
        contract = conn.execute(
            'SELECT * FROM contracts WHERE contract_id = ?', (contract_id,)
        ).fetchone()
        if not contract:
            return jsonify({'error': 'Contract not found.'}), 404

        rows = conn.execute('''
            SELECT id, category, item_name, unit, qty_contracted
            FROM contract_materials
            WHERE contract_id = ?
            ORDER BY category, item_name
        ''', (contract_id,)).fetchall()

        # Group by category
        grouped = {}
        for r in rows:
            cat = r['category']
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append({
                'id':             r['id'],
                'item_name':      r['item_name'],
                'unit':           r['unit'],
                'qty_contracted': r['qty_contracted']
            })

        return jsonify({
            'success':  True,
            'contract': dict(contract),
            'groups':   grouped
        })
    finally:
        conn.close()


# ── POST /api/material/submit ──────────────────────────────
@material_bp.route('/submit', methods=['POST'])
@authenticate_token
def submit():
    data        = request.get_json()
    contract_id = (data.get('contract_id') or '').strip()
    items       = data.get('items', [])
    remarks     = (data.get('remarks') or '').strip()
    gps_lat     = data.get('gps_lat')
    gps_lng     = data.get('gps_lng')

    if not contract_id:
        return jsonify({'error': 'Contract ID is required.'}), 400
    if not items:
        return jsonify({'error': 'No items submitted.'}), 400

    user_id     = request.user['id']
    employee_id = request.user['employee_id']
    _, date_str = now_ist()

    # Determine overall status
    # If ANY item has qty_observed < qty_contracted → discrepancy
    has_discrepancy = any(
        float(item.get('qty_observed', 0)) < float(item.get('qty_contracted', 0))
        for item in items
    )
    overall_status = 'discrepancy' if has_discrepancy else 'ok'

    conn = get_db()
    try:
        cur = conn.execute('''
            INSERT INTO material_checks
              (user_id, employee_id, contract_id, date, gps_lat, gps_lng,
               overall_status, remarks, status, items_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?)
        ''', (user_id, employee_id, contract_id, date_str,
              gps_lat, gps_lng, overall_status, remarks,
              json.dumps(items)))
        conn.commit()

        return jsonify({
            'success':        True,
            'check_id':       cur.lastrowid,
            'overall_status': overall_status,
            'message':        'Material check submitted successfully!'
        })
    finally:
        conn.close()


# ── GET /api/material/history ──────────────────────────────
@material_bp.route('/history', methods=['GET'])
@authenticate_token
def history():
    employee_id = request.user['employee_id']
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT mc.id, mc.contract_id, mc.date, mc.overall_status,
                   mc.status, mc.remarks, c.project_name
            FROM material_checks mc
            LEFT JOIN contracts c ON mc.contract_id = c.contract_id
            WHERE mc.employee_id = ?
            ORDER BY mc.id DESC LIMIT 30
        ''', (employee_id,)).fetchall()

        return jsonify({'success': True, 'records': [dict(r) for r in rows]})
    finally:
        conn.close()


# ── GET /api/material/check/<id> ───────────────────────────
@material_bp.route('/check/<int:check_id>', methods=['GET'])
@authenticate_token
def get_check(check_id):
    conn = get_db()
    try:
        row = conn.execute(
            'SELECT * FROM material_checks WHERE id = ?', (check_id,)
        ).fetchone()

        if not row:
            return jsonify({'error': 'Not found.'}), 404

        # Owner or admin only
        if row['employee_id'] != request.user['employee_id'] \
                and request.user['role'] != 'admin':
            return jsonify({'error': 'Access denied.'}), 403

        result = dict(row)
        result['items_json'] = json.loads(result['items_json'] or '[]')
        return jsonify({'success': True, 'check': result})
    finally:
        conn.close()


# ── GET /api/material/all  (admin only) ────────────────────
@material_bp.route('/all', methods=['GET'])
@authenticate_token
@require_admin
def all_checks():
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT mc.id, mc.contract_id, mc.date, mc.overall_status,
                   mc.status, mc.remarks, mc.admin_remarks,
                   c.project_name, u.name, u.employee_id, u.designation
            FROM material_checks mc
            LEFT JOIN contracts c  ON mc.contract_id  = c.contract_id
            LEFT JOIN users u      ON mc.employee_id  = u.employee_id
            ORDER BY mc.id DESC LIMIT 100
        ''').fetchall()
        return jsonify({'success': True, 'records': [dict(r) for r in rows]})
    finally:
        conn.close()


# ── PATCH /api/material/check/<id>/review  (admin only) ────
@material_bp.route('/check/<int:check_id>/review', methods=['PATCH'])
@authenticate_token
@require_admin
def review(check_id):
    data         = request.get_json()
    action       = data.get('action')
    admin_remark = (data.get('admin_remarks') or '')

    if action not in ('approve', 'flag'):
        return jsonify({'error': "Action must be 'approve' or 'flag'."}), 400

    new_status = 'approved' if action == 'approve' else 'flagged'
    conn = get_db()
    try:
        conn.execute('''
            UPDATE material_checks
            SET status = ?, admin_remarks = ?
            WHERE id = ?
        ''', (new_status, admin_remark, check_id))
        conn.commit()
        return jsonify({'success': True, 'status': new_status})
    finally:
        conn.close()
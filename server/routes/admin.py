from flask import Blueprint, request, jsonify
from server.database import get_db
from server.auth_middleware import authenticate_token, require_admin

admin_bp = Blueprint('admin', __name__)


# ── GET /api/admin/stats ───────────────────────────────────
@admin_bp.route('/stats', methods=['GET'])
@authenticate_token
@require_admin
def stats():
    conn = get_db()
    try:
        from datetime import datetime, timezone, timedelta
        ist_date = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d')

        total_officers = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'fvo'"
        ).fetchone()[0]

        active_today = conn.execute(
            "SELECT COUNT(*) FROM attendance WHERE date = ? AND checkout_time IS NULL",
            (ist_date,)
        ).fetchone()[0]

        inspections_today = conn.execute(
            "SELECT COUNT(*) FROM inspections WHERE date = ?",
            (ist_date,)
        ).fetchone()[0]

        pending_inspections = conn.execute(
            "SELECT COUNT(*) FROM inspections WHERE status = 'submitted'"
        ).fetchone()[0]

        pending_materials = conn.execute(
            "SELECT COUNT(*) FROM material_checks WHERE status = 'submitted'"
        ).fetchone()[0]

        flagged_total = conn.execute(
            "SELECT COUNT(*) FROM inspections WHERE status = 'flagged'"
        ).fetchone()[0]

        return jsonify({
            'success':            True,
            'total_officers':     total_officers,
            'active_today':       active_today,
            'inspections_today':  inspections_today,
            'pending_inspections':pending_inspections,
            'pending_materials':  pending_materials,
            'flagged_total':      flagged_total,
        })
    finally:
        conn.close()


# ── GET /api/admin/officers ────────────────────────────────
@admin_bp.route('/officers', methods=['GET'])
@authenticate_token
@require_admin
def officers():
    conn = get_db()
    try:
        rows = conn.execute('''
            SELECT
                u.id, u.name, u.employee_id, u.designation,
                u.department, u.mobile, u.created_at,
                COUNT(DISTINCT a.id)  AS total_attendance,
                COUNT(DISTINCT i.id)  AS total_inspections,
                COUNT(DISTINCT mc.id) AS total_material_checks,
                MAX(a.date)           AS last_attendance_date
            FROM users u
            LEFT JOIN attendance      a  ON u.employee_id = a.employee_id
            LEFT JOIN inspections     i  ON u.employee_id = i.employee_id
            LEFT JOIN material_checks mc ON u.employee_id = mc.employee_id
            WHERE u.role = 'fvo'
            GROUP BY u.id
            ORDER BY u.name
        ''').fetchall()

        return jsonify({'success': True, 'officers': [dict(r) for r in rows]})
    finally:
        conn.close()
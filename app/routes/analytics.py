"""
Analytics routes for teachers.

Implements the analytics dashboard per Class-economy-analytics-specs.md.

Key Principles:
- System health metrics always visible (5-second readability)
- Visual alerts only (no automatic notifications)
- Individual student data only in drill-down views
- All metrics CWI-relative
- Trends over snapshots
"""

from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, session, jsonify, request, flash, redirect, url_for
from sqlalchemy import desc

from app.extensions import db, limiter
from app.auth import admin_required
from app.models import (
    Admin, AnalyticsAlert, AnalyticsEvent,
    Student, StudentBlock
)
from app.models import Transaction

# Define allowed window types constant
ALLOWED_WINDOW_TYPES = {'week', 'month', 'pay_cycle', 'rent_cycle'}
from app.utils.analytics_engine import AnalyticsEngine
from app.utils.helpers import render_template_with_fallback as render_template

import pytz
from werkzeug.exceptions import BadRequest
from jinja2 import TemplateNotFound

# Timezone
PACIFIC = pytz.timezone('America/Los_Angeles')

# Create blueprint
analytics_bp = Blueprint('analytics', __name__, url_prefix='/admin/analytics')


def get_time_window(window_type: str, custom_start=None, custom_end=None):
    """
    Calculate time window boundaries.
    
    Args:
        window_type: 'week', 'pay_cycle', 'rent_cycle', 'month', 'custom'
        custom_start: Start date for custom window
        custom_end: End date for custom window
    
    Returns:
        Tuple of (window_start, window_end)
    """
    now = datetime.now(timezone.utc)
    
    if window_type == 'week':
        # Last 7 days
        window_start = now - timedelta(days=7)
        window_end = now
    elif window_type == 'month':
        # Last 30 days
        window_start = now - timedelta(days=30)
        window_end = now
    elif window_type == 'pay_cycle':
        # Based on payroll frequency (default 7 days)
        # TODO: Get actual payroll frequency from settings
        window_start = now - timedelta(days=7)
        window_end = now
    elif window_type == 'rent_cycle':
        # Based on rent frequency (default monthly)
        # TODO: Get actual rent frequency from settings
        window_start = now - timedelta(days=30)
        window_end = now
    elif window_type == 'custom' and custom_start and custom_end:
        window_start = custom_start
        window_end = custom_end
    else:
        # Default to week
        window_start = now - timedelta(days=7)
        window_end = now
    
    return window_start, window_end


@analytics_bp.route('/')
@admin_required
def dashboard():
    """
    Main analytics dashboard.
    
    Per spec section 4.1:
    - System health metrics always visible
    - Readable in under 5 seconds
    - Aggregated at class level
    - Auto-updating
    """
    teacher_id = session.get('admin_id')
    join_code = session.get('current_join_code')
    
    if not join_code:
        flash('Please select a class period first.', 'warning')
        return redirect(url_for('admin.students'))
    
    # Get or set time window preference, validated against allowed values
    requested_window_type = request.args.get('window', 'week')
    allowed_window_types = {'week', 'month', 'pay_cycle', 'rent_cycle'}
    window_type = requested_window_type if requested_window_type in allowed_window_types else 'week'
    
    # Calculate time window
    window_start, window_end = get_time_window(window_type)
    
    # Initialize analytics engine
    engine = AnalyticsEngine(teacher_id, join_code)
    
    # Get or create snapshot for this window
    snapshot = engine.get_or_create_snapshot(window_type, window_start, window_end)
    
    # Get active alerts
    active_alerts = AnalyticsAlert.query.filter(
        AnalyticsAlert.join_code == join_code,
        AnalyticsAlert.is_active == True
    ).order_by(
        # Sort by severity: critical, warning, info
        desc(AnalyticsAlert.severity == 'critical'),
        desc(AnalyticsAlert.severity == 'warning'),
        AnalyticsAlert.triggered_at.desc()
    ).all()
    
    # Get recent events for context
    recent_events = AnalyticsEvent.query.filter(
        AnalyticsEvent.join_code == join_code,
        AnalyticsEvent.event_date >= window_start,
        AnalyticsEvent.event_date <= window_end
    ).order_by(AnalyticsEvent.event_date.desc()).limit(10).all()
    
    # Get teacher info for display
    teacher = Admin.query.get(teacher_id)
    
    return render_template(
        'admin_analytics_dashboard.html',
        snapshot=snapshot,
        alerts=active_alerts,
        events=recent_events,
        window_type=window_type,
        window_start=window_start,
        window_end=window_end,
        teacher=teacher,
        join_code=join_code,
        current_page='analytics'
    )


@analytics_bp.route('/api/snapshot/<window_type>')
@admin_required
@limiter.limit("30 per minute")
def api_snapshot(window_type):
    """
    API endpoint to get analytics snapshot data.
    
    Returns JSON with system health metrics.
    """
    teacher_id = session.get('admin_id')
    join_code = session.get('current_join_code')
    
    if not join_code:
        return jsonify({'error': 'No class period selected'}), 400
    
    # Calculate time window
    window_start, window_end = get_time_window(window_type)
    
    # Initialize analytics engine
    engine = AnalyticsEngine(teacher_id, join_code)
    
    # Get or create snapshot
    snapshot = engine.get_or_create_snapshot(window_type, window_start, window_end)
    
    # Convert to JSON-serializable format
    snapshot_data = {
        'window_type': snapshot.window_type,
        'window_start': snapshot.window_start.isoformat(),
        'window_end': snapshot.window_end.isoformat(),
        'metrics': {
            'participation_rate': snapshot.participation_rate,
            'money_velocity': snapshot.money_velocity,
            'cwi_deviation_within_20pct': snapshot.cwi_deviation_within_20pct,
            'budget_survival_pass_rate': snapshot.budget_survival_pass_rate,
        },
        'cwi_value': snapshot.cwi_value,
        'trends': {
            'balance': snapshot.balance_trend,
            'velocity': snapshot.velocity_trend,
            'participation': snapshot.participation_trend,
        },
        'context': {
            'total_students': snapshot.total_students,
            'active_students': snapshot.active_students,
            'total_transactions': snapshot.total_transactions,
        },
        'computed_at': snapshot.computed_at.isoformat(),
        'is_complete': snapshot.is_complete
    }
    
    return jsonify(snapshot_data)


@analytics_bp.route('/api/alerts')
@admin_required
@limiter.limit("30 per minute")
def api_alerts():
    """
    API endpoint to retrieve active analytics alerts for the current class period.

    Returns:
        flask.Response: JSON object with either:
            - {"error": "No class period selected"} and HTTP 400 if no join code
              is present in the session, or
            - {"alerts": [...]} with a list of active alerts, each containing
              id, type, severity, what_changed, why_it_matters, suggested_action,
              triggered_at, and acknowledged.
    """
    teacher_id = session.get('admin_id')
    join_code = session.get('current_join_code')
    
    if not join_code:
        return jsonify({'error': 'No class period selected'}), 400
    
    active_alerts = AnalyticsAlert.query.filter(
        AnalyticsAlert.join_code == join_code,
        AnalyticsAlert.is_active == True
    ).order_by(
        desc(AnalyticsAlert.severity == 'critical'),
        desc(AnalyticsAlert.severity == 'warning'),
        AnalyticsAlert.triggered_at.desc()
    ).all()
    
    alerts_data = []
    for alert in active_alerts:
        alerts_data.append({
            'id': alert.id,
            'type': alert.alert_type,
            'severity': alert.severity,
            'what_changed': alert.what_changed,
            'why_it_matters': alert.why_it_matters,
            'suggested_action': alert.suggested_action,
            'triggered_at': alert.triggered_at.isoformat(),
            'acknowledged': alert.acknowledged_at is not None
        })
    
    return jsonify({'alerts': alerts_data})


@analytics_bp.route('/alert/<int:alert_id>/acknowledge', methods=['POST'])
@admin_required
def acknowledge_alert(alert_id):
    """
    Mark an alert as acknowledged by the teacher.
    """
    teacher_id = session.get('admin_id')
    join_code = session.get('current_join_code')
    
    alert = AnalyticsAlert.query.filter(
        AnalyticsAlert.id == alert_id,
        AnalyticsAlert.teacher_id == teacher_id,
        AnalyticsAlert.join_code == join_code
    ).first()
    
    if not alert:
        flash('Alert not found.', 'danger')
        return redirect(url_for('analytics.dashboard'))
    
    alert.acknowledge()
    flash('Alert acknowledged.', 'success')
    
    return redirect(url_for('analytics.dashboard'))


@analytics_bp.route('/events')
@admin_required
def events():
    """
    Display contextual analytics events for the currently selected class period.

    Per spec section 5.2:
    - Shows rent changes, wage changes, inflation events, etc.
    - Provides context for understanding metric changes.
    """
    teacher_id = session.get('admin_id')
    join_code = session.get('current_join_code')
    
    if not join_code:
        flash('Please select a class period first.', 'warning')
        return redirect(url_for('admin.students'))
    
    # Get all events for this class
    events_list = AnalyticsEvent.query.filter(
        AnalyticsEvent.join_code == join_code
    ).order_by(AnalyticsEvent.event_date.desc()).all()
    
    try:
        return render_template(
            'admin_analytics_events.html',
            events=events_list,
            join_code=join_code
        )
    except TemplateNotFound:
        # Fallback: return JSON response if template not found
        events_data = []
        for event in events_list:
            events_data.append({
                'id': event.id,
                'event_type': event.event_type,
                'description': event.description,
                'event_date': event.event_date.isoformat(),
                'affected_students': event.affected_students
            })
        return jsonify({'events': events_data, 'join_code': join_code})


@analytics_bp.route('/student/<int:student_id>')
@admin_required
def student_drill_down(student_id):
    """
    Drill-down view for individual student vs CWI.
    
    Per spec section 4.3:
    - Only available after user interaction (not default view)
    - Must be contextualized with CWI expectations
    - Must explain why the metric matters
    """
    teacher_id = session.get('admin_id')
    join_code = session.get('current_join_code')
    
    if not join_code:
        flash('Please select a class period first.', 'warning')
        return redirect(url_for('admin.students'))
    
    # Get student with scoping
    student = Student.query.join(
        StudentBlock, Student.id == StudentBlock.student_id
    ).filter(
        Student.id == student_id,
        StudentBlock.join_code == join_code
    ).first()
    if student is None:
        flash('Student not found for this class period.', 'warning')
        return redirect(url_for('admin.students'))
    # Use actual enrollment duration when possible; fall back to 18 weeks if unknown
    weeks_enrolled = 18  # default/fallback for legacy behavior

    # Try to determine when the student enrolled in this class period
    enrollment_block = StudentBlock.query.filter(
        StudentBlock.student_id == student.id,
        StudentBlock.join_code == join_code
    ).order_by(StudentBlock.id.asc()).first()

    enrollment_start = None
    if enrollment_block is not None and hasattr(enrollment_block, "created_at"):
        enrollment_start = enrollment_block.created_at
    elif hasattr(student, "created_at"):
        # Fallback: use the student's created_at if per-class timestamp is unavailable
        enrollment_start = student.created_at

    if enrollment_start is not None:
        now_utc = datetime.now(timezone.utc)
        # Ensure timezone-aware arithmetic
        if getattr(enrollment_start, "tzinfo", None) is None:
            enrollment_start_utc = enrollment_start.replace(tzinfo=timezone.utc)
        else:
            enrollment_start_utc = enrollment_start.astimezone(timezone.utc)

        enrollment_duration_days = (now_utc - enrollment_start_utc).days
        if enrollment_duration_days > 0:
            weeks_enrolled = enrollment_duration_days / 7.0
        else:
            # If enrollment is less than a day old, treat as a very short enrollment
            weeks_enrolled = 0
    
    if not student:
        flash('Student not found in this class period.', 'danger')
        return redirect(url_for('analytics.dashboard'))
    
    # Initialize analytics engine
    engine = AnalyticsEngine(teacher_id, join_code)
    cwi = engine._get_cwi()
    
    # Get student balance
    current_balance = student.get_checking_balance(
        teacher_id=teacher_id,
        join_code=join_code
    )
    
    # Calculate expected balance based on CWI
    # This is a simplified calculation - could be enhanced
    # Assuming enrolled for full semester (18 weeks as default)
    weeks_enrolled = 18  # TODO: Calculate actual enrollment duration
    expected_balance = cwi * weeks_enrolled
    
    # Calculate deviation
    if expected_balance > 0:
        deviation = ((current_balance - expected_balance) / expected_balance) * 100
    else:
        deviation = 0
    
    # Get recent transactions (last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    recent_transactions = Transaction.query.filter(
        Transaction.student_id == student_id,
        Transaction.join_code == join_code,
        Transaction.timestamp >= thirty_days_ago,
        Transaction.is_void == False
    ).order_by(Transaction.timestamp.desc()).limit(50).all()
    
    try:
        return render_template(
            'admin_analytics_student_detail.html',
            student=student,
            current_balance=current_balance,
            expected_balance=expected_balance,
            deviation=deviation,
            cwi=cwi,
            recent_transactions=recent_transactions,
            join_code=join_code
        )
    except TemplateNotFound:
        # Fallback: return JSON response if template not found
        return jsonify({'error': 'Template not found', 'student_id': student.id}), 404
        return jsonify({
            'error': 'Template not found',
            'student_id': student.id,
            'student_name': student.name,
            'current_balance': current_balance,
            'expected_balance': expected_balance,
            'deviation': deviation,
            'cwi': cwi,
            'recent_transactions': [
                {
                    'id': t.id,
                    'timestamp': t.timestamp.isoformat(),
                    'amount': t.amount,
                    'description': t.description
                } for t in recent_transactions
            ],
            'join_code': join_code
        })
        return jsonify({
            'student_id': student.id,
            'student_name': student.name,
            'current_balance': current_balance,
            'expected_balance': expected_balance,
            'deviation': deviation,
            'cwi': cwi,
            'recent_transactions': [
                {
                    'id': t.id,
                    'timestamp': t.timestamp.isoformat(),
                    'amount': t.amount,
                    'description': t.description
                } for t in recent_transactions
            ],
            'join_code': join_code
        })

"""
Analytics Engine for Classroom Economy

Implements analytics computation per docs/technical-reference/Class-economy-analytics-specs.md.

Core Principles:
- All monetary metrics are CWI-relative (not absolute)
- Trends matter more than totals
- System health focus, not student ranking
- No leaderboards or comparative student ranking
- Metrics precomputed and cached by time window
- 5-second readability target for system health metrics

Per spec section 4.2:
- Must be trend-based
- Must include directionality (improving/worsening)
- Must never default to blaming students
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy import or_

from app.extensions import db
from app.models import (
    Student, Transaction, TapEvent, StudentBlock, PayrollSettings,
    RentSettings, AnalyticsSnapshot, AnalyticsAlert
)
from app.utils.economy_balance import EconomyBalanceChecker


@dataclass
class SystemHealthMetrics:
    """System health metrics (always visible per spec section 4.1)"""
    participation_rate: float  # % of students who were active
    money_velocity: float  # Transactions per student per day
    cwi_deviation_within_20pct: float  # % of students within ±20% of expected CWI
    budget_survival_pass_rate: float  # % of students passing budget survival test
    cwi_value: float  # Current CWI for context
    total_students: int
    active_students: int


@dataclass
class TrendMetrics:
    """Drift & anomaly metrics (trend-based per spec section 4.2)"""
    balance_trend: str  # 'improving', 'stable', 'worsening'
    velocity_trend: str  # 'increasing', 'stable', 'decreasing'
    participation_trend: str  # 'improving', 'stable', 'declining'


class AnalyticsEngine:
    """
    Core analytics computation engine.
    
    Implements observability model per spec section 2:
    - Surface signals, not raw data
    - Highlight anomalies, not totals
    - Favor trends over snapshots
    - Bias toward actionable interpretation
    """
    
    # Thresholds per spec section 6.1
    CWI_DEVIATION_WARNING_THRESHOLD = 0.20  # >20% of students outside ±20% CWI
    VELOCITY_DROP_WARNING_THRESHOLD = 0.30  # >30% drop week-over-week
    PARTICIPATION_WARNING_THRESHOLD = 0.70  # <70% participation
    
    # CWI deviation bands (per spec section 3.2)
    CWI_DEVIATION_BAND = 0.20  # ±20% is "within expected"
    
    def __init__(self, teacher_id: int, join_code: str):
        """
        Initialize analytics engine for a specific class economy.
        
        Args:
            teacher_id: The teacher's ID
            join_code: The class period join code (CRITICAL for multi-tenancy)
        """
        self.teacher_id = teacher_id
        self.join_code = join_code
        self.economy_checker = EconomyBalanceChecker(teacher_id)
    
    def _get_enrolled_students(self) -> List[Student]:
        """Get all students enrolled in this class period."""
        return Student.query.join(StudentBlock).filter(
            StudentBlock.join_code == self.join_code
        ).all()
    
    def _get_cwi(self) -> float:
        """Calculate current CWI for this class."""
        # PayrollSettings may be linked by block or teacher_id
        # Try to find by block first (since block is period identifier)
        payroll_settings = PayrollSettings.query.filter_by(
            teacher_id=self.teacher_id
        ).filter(
            # Match by block if available, otherwise use global settings
            or_(
                PayrollSettings.block == self.join_code,
                PayrollSettings.block.is_(None)
            )
        ).first()
        
        if not payroll_settings:
            return 0.0
        
        cwi_calc = self.economy_checker.calculate_cwi(payroll_settings)
        return cwi_calc.cwi
    
    def calculate_participation_rate(
        self,
        window_start: datetime,
        window_end: datetime
    ) -> Tuple[float, int, int]:
        """
        Calculate participation rate for time window.
        
        Returns:
            Tuple of (participation_rate, active_students, total_students)
        """
        students = self._get_enrolled_students()
        total_students = len(students)
        
        if total_students == 0:
            return 0.0, 0, 0
        
        # Count students with any activity (transactions or attendance)
        active_student_ids = set()
        
        # Check for transactions in window (distinct student IDs)
        transaction_student_rows = (
            Transaction.query.with_entities(Transaction.student_id)
            .filter(
                Transaction.join_code == self.join_code,
                Transaction.timestamp >= window_start,
                Transaction.timestamp < window_end,
            )
            .distinct()
            .all()
        )
        for (student_id,) in transaction_student_rows:
            active_student_ids.add(student_id)
        
        # Check for attendance in window (distinct student IDs)
        tap_event_student_rows = (
            TapEvent.query.with_entities(TapEvent.student_id)
            .filter(
                TapEvent.join_code == self.join_code,
                TapEvent.timestamp >= window_start,
                TapEvent.timestamp < window_end,
            )
            .distinct()
            .all()
        )
        for (student_id,) in tap_event_student_rows:
            active_student_ids.add(student_id)
        
        active_students = len(active_student_ids)
        participation_rate = (active_students / total_students) * 100
        
        return participation_rate, active_students, total_students
    
    def calculate_money_velocity(
        self,
        window_start: datetime,
        window_end: datetime
    ) -> float:
        """
        Calculate money velocity: transactions per student per day.
        
        This measures how actively money is moving through the economy.
        Per spec, this is a system health metric.
        """
        students = self._get_enrolled_students()
        total_students = len(students)
        
        if total_students == 0:
            return 0.0
        
        # Calculate days in window (allow fractional days for sub-day windows)
        duration_seconds = (window_end - window_start).total_seconds()
        if duration_seconds <= 0:
            return 0.0
        days = duration_seconds / 86400.0
        transaction_count = Transaction.query.filter(
            Transaction.join_code == self.join_code,
            Transaction.timestamp >= window_start,
            Transaction.timestamp < window_end,
            Transaction.is_void == False
        ).count()
        
        # Transactions per student per day
        velocity = transaction_count / (total_students * days)
        
        return round(velocity, 2)
    
    def calculate_cwi_deviation_distribution(
        self,
        window_start: datetime,
        window_end: datetime,
        cwi: float
    ) -> float:
        """
        Calculate % of students within CWI deviation bands.
        
        Per spec section 3.2 and 4.1:
        - All monetary analytics must be CWI-relative
        - Report % of students within defined CWI bands (±20%)
        
        Returns:
            Percentage of students within ±20% of expected CWI trajectory
        """
        students = self._get_enrolled_students()
        total_students = len(students)
        
        if total_students == 0 or cwi == 0:
            return 0.0
        
        # Calculate expected balance based on window duration
        # Assuming perfect attendance, expected balance = CWI * weeks
        days = (window_end - window_start).days
        weeks = days / 7.0
        expected_balance = cwi * weeks
        
        # Count students within ±20% of expected
        within_band = 0
        
        for student in students:
            current_balance = student.get_checking_balance(
                teacher_id=self.teacher_id,
                join_code=self.join_code
            )
            
            # Calculate deviation
            if expected_balance > 0:
                deviation = abs(current_balance - expected_balance) / expected_balance
                if deviation <= self.CWI_DEVIATION_BAND:
                    within_band += 1
            elif current_balance == 0:
                # If expected is 0 and actual is 0, that's within band
                within_band += 1
        
        percentage = (within_band / total_students) * 100
        return round(percentage, 1)
    
    def calculate_budget_survival_pass_rate(self, cwi: float) -> float:
        """
        Calculate % of students passing budget survival test.
        
        Per spec and economy_balance.py:
        - Students with perfect attendance must be able to save ≥10% of CWI
        - This tests if economy is balanced
        """

        # Get rent settings - may be linked by block or teacher_id
        rent_settings = RentSettings.query.filter_by(
            teacher_id=self.teacher_id
        ).filter(
            or_(
                RentSettings.block == self.join_code,
                RentSettings.block.is_(None)
            )
        ).first()
        
        students = self._get_enrolled_students()
        total_students = len(students)
        if total_students == 0:
            return 0.0

        passing_students = 0
        
        for student in students:
            balance = student.get_checking_balance(
                teacher_id=self.teacher_id,
                join_code=self.join_code
            )
            
            # Check if the student can save at least 10% of CWI
            if balance >= 0.1 * cwi:
                passing_students += 1
        
        percentage = (passing_students / total_students) * 100
        return round(percentage, 1)
    
    def calculate_trend(
        self,
        current_value: float,
        previous_value: Optional[float],
        threshold: float = 0.10
    ) -> str:
        """
        Determine trend direction based on change.
        
        Args:
            current_value: Current metric value
            previous_value: Previous period value (None if no history)
            threshold: Minimum percent change to consider significant (default 10%)

        Returns:
            'increasing', 'stable', or 'decreasing'.
        
        Notes:
            Per spec sections 4.1 and 4.2, these are class-level, auto-updating,
            readable within 5 seconds, and trend-based with clear directionality.
        """
        if previous_value is None or previous_value == 0:
            return 'stable'
        
        change = (current_value - previous_value) / previous_value
        
        if abs(change) < threshold:
            return 'stable'
        elif change > 0:
            return 'increasing'  # Changed from 'improving' to 'increasing'
        else:
            return 'decreasing'  # Changed from 'worsening' to 'decreasing'
    
    def compute_system_health(
        self,
        window_start: datetime,
        window_end: datetime
    ) -> SystemHealthMetrics:
        """
        Compute all system health metrics for a time window.
        
        Per spec section 4.1:
        - Aggregated at class level
        - Auto-updating
        - Readable in under 5 seconds
        """
        cwi = self._get_cwi()
        
        participation_rate, active_students, total_students = self.calculate_participation_rate(
            window_start, window_end
        )
        
        money_velocity = self.calculate_money_velocity(window_start, window_end)
        
        cwi_deviation_pct = self.calculate_cwi_deviation_distribution(
            window_start, window_end, cwi
        )
        
        budget_survival_rate = self.calculate_budget_survival_pass_rate(cwi)
        
        return SystemHealthMetrics(
            participation_rate=participation_rate,
            money_velocity=money_velocity,
            cwi_deviation_within_20pct=cwi_deviation_pct,
            budget_survival_pass_rate=budget_survival_rate,
            cwi_value=cwi,
            total_students=total_students,
            active_students=active_students
        )
    
    def compute_trends(
        self,
        current_snapshot: SystemHealthMetrics,
        previous_snapshot: Optional[AnalyticsSnapshot]
    ) -> TrendMetrics:
        """
        Compute trend indicators by comparing to previous period.
        
        Per spec section 4.2:
        - Must be trend-based
        - Must include directionality (improving/worsening)
        - Must never default to blaming students
        """
        if previous_snapshot is None:
            # No history, all stable
            return TrendMetrics(
                balance_trend='stable',
                velocity_trend='stable',
                participation_trend='stable'
            )
        
        # Calculate trends (higher is better for all these metrics)
        velocity_trend = self.calculate_trend(
            current_snapshot.money_velocity,
            previous_snapshot.money_velocity
        )
        
        participation_trend = self.calculate_trend(
            current_snapshot.participation_rate,
            previous_snapshot.participation_rate
        )
        
        balance_trend = self.calculate_trend(
            current_snapshot.cwi_deviation_within_20pct,
            previous_snapshot.cwi_deviation_within_20pct
        )
        
        return TrendMetrics(
            balance_trend=balance_trend,
            velocity_trend=velocity_trend,
            participation_trend=participation_trend
        )
    
    def generate_alerts(
        self,
        metrics: SystemHealthMetrics,
        trends: TrendMetrics
    ) -> List[Dict]:
        """
        Generate alerts based on metrics and thresholds.
        
        Per spec section 6:
        - Visual alerts only (not notifications)
        - Explain what changed, why it matters, suggest interventions
        - Never shame students, prescribe discipline, or trigger penalties
        """
        alerts = []
        
        # Alert: Low participation
        if metrics.participation_rate < (self.PARTICIPATION_WARNING_THRESHOLD * 100):
            alerts.append({
                'alert_type': 'participation_low',
                'severity': 'warning',
                'what_changed': f'Participation rate is {metrics.participation_rate:.1f}%',
                'why_it_matters': 'Low participation may indicate students are disengaged or facing barriers',
                'suggested_action': 'Consider: Are class schedules preventing access? Are instructions clear? Try a reminder announcement or check-in with students.',
            })
        
        # Alert: CWI deviation
        cwi_within_band = metrics.cwi_deviation_within_20pct / 100
        if cwi_within_band < (1 - self.CWI_DEVIATION_WARNING_THRESHOLD):
            alerts.append({
                'alert_type': 'cwi_deviation',
                'severity': 'warning',
                'what_changed': f'Only {metrics.cwi_deviation_within_20pct:.1f}% of students are tracking expected income',
                'why_it.matters': 'Large deviations suggest economy settings may not match actual behavior',
                'suggested_action': 'Review: Are wages appropriate for attendance patterns? Are expenses too high? Check the Economy Health page.',
            })
        
        # Alert: Velocity drop
        if trends.velocity_trend == 'worsening':
            alerts.append({
                'alert_type': 'velocity_drop',
                'severity': 'info',
                'what_changed': 'Money velocity is decreasing',
                'why_it.matters': 'Declining activity may indicate students are hoarding or disengaged',
                'suggested_action': 'Consider: Add new store items, host a special event, or review pricing',
            })
            # Must never default to blaming students.
        
        # Alert: Budget survival
        if metrics.budget_survival_pass_rate < 50:
            alerts.append({
                'alert_type': 'budget_survival_low',
                'severity': 'critical',
                'what_changed': f'Only {metrics.budget_survival_pass_rate:.1f}% of students have positive balances',
                'why_it.matters': 'Many students may be struggling with insolvency',
                'suggested_action': 'URGENT: Review rent and expense settings. Consider temporary relief or wage adjustment.',
            })
        
        return alerts
    
    def create_snapshot(
        self,
        window_type: str,
        window_start: datetime,
        window_end: datetime,
        is_complete: bool = True
    ) -> AnalyticsSnapshot:
        """
        Create and save an analytics snapshot for a time window.
        
        Per spec section 10:
        - Metrics must be precomputed where possible
        - Cached by time window
        - Resilient to partial data
        """
        # Compute metrics
        health_metrics = self.compute_system_health(window_start, window_end)
        
        # Get previous snapshot for trend calculation
        previous_snapshot = AnalyticsSnapshot.query.filter(
            AnalyticsSnapshot.join_code == self.join_code,
            AnalyticsSnapshot.window_type == window_type,
            AnalyticsSnapshot.window_start < window_start,
            AnalyticsSnapshot.is_complete == True
        ).order_by(AnalyticsSnapshot.window_start.desc()).first()
        
        trends = self.compute_trends(health_metrics, previous_snapshot)
        
        # Count transactions
        total_transactions = Transaction.query.filter(
            Transaction.join_code == self.join_code,
            Transaction.timestamp >= window_start,
            Transaction.timestamp < window_end,
            Transaction.is_void == False
        ).count()
        
        # Calculate average balance (for CWI comparison only, not for ranking)
        students = self._get_enrolled_students()
        total_balance = sum(
            s.get_checking_balance(teacher_id=self.teacher_id, join_code=self.join_code)
            for s in students
        )
        avg_balance = total_balance / len(students) if students else 0.0
        
        # Create snapshot
        snapshot = AnalyticsSnapshot(
            teacher_id=self.teacher_id,
            join_code=self.join_code,
            window_type=window_type,
            window_start=window_start,
            window_end=window_end,
            participation_rate=health_metrics.participation_rate,
            money_velocity=health_metrics.money_velocity,
            cwi_deviation_within_20pct=health_metrics.cwi_deviation_within_20pct,
            budget_survival_pass_rate=health_metrics.budget_survival_pass_rate,
            cwi_value=health_metrics.cwi_value,
            avg_student_balance=avg_balance,
            balance_trend=trends.balance_trend,
            velocity_trend=trends.velocity_trend,
            participation_trend=trends.participation_trend,
            total_students=health_metrics.total_students,
            active_students=health_metrics.active_students,
            total_transactions=total_transactions,
            is_complete=is_complete
        )
        
        db.session.add(snapshot)
        db.session.commit()
        
        # Generate and save alerts
        alerts = self.generate_alerts(health_metrics, trends)
        for alert_data in alerts:
            # Check if this alert type already exists and is active
            existing_alert = AnalyticsAlert.query.filter(
                AnalyticsAlert.join_code == self.join_code,
                AnalyticsAlert.alert_type == alert_data['alert_type'],
                AnalyticsAlert.is_active == True
            ).first()
            
            if not existing_alert:
                alert = AnalyticsAlert(
                    teacher_id=self.teacher_id,
                    join_code=self.join_code,
                    alert_type=alert_data['alert_type'],
                    severity=alert_data['severity'],
                    what_changed=alert_data['what_changed'],
                    why_it_matters=alert_data['why_it.matters'],
                    suggested_action=alert_data.get('suggested_action', '')
                )
                db.session.add(alert)
        
        db.session.commit()
        
        return snapshot
    
    def get_or_create_snapshot(
        self,
        window_type: str,
        window_start: datetime,
        window_end: datetime
    ) -> AnalyticsSnapshot:
        """
        Get existing snapshot or create new one if not cached.
        
        Implements caching strategy per spec section 10.
        """
        # Check for existing snapshot
        snapshot = AnalyticsSnapshot.query.filter(
            AnalyticsSnapshot.join_code == self.join_code,
            AnalyticsSnapshot.window_type == window_type,
            AnalyticsSnapshot.window_start == window_start,
            AnalyticsSnapshot.window_end == window_end
        ).first()
        
        if snapshot and snapshot.is_complete:
            # Return cached snapshot
            return snapshot
        
        # Create new snapshot
        is_complete = window_end <= datetime.now(timezone.utc)
        return self.create_snapshot(window_type, window_start, window_end, is_complete)

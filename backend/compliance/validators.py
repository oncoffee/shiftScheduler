"""Compliance validators for labor law enforcement."""

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from .types import (
    ComplianceContext,
    ComplianceResult,
    ShiftInfo,
    Violation,
    ViolationType,
    ViolationSeverity,
)


class BaseValidator(ABC):
    """Base class for compliance validators."""

    @abstractmethod
    def validate(self, context: ComplianceContext, result: ComplianceResult) -> None:
        """Validate compliance and add violations to result."""
        pass


class MinorRestrictionsValidator(BaseValidator):
    """Validates restrictions for minor employees (under 18)."""

    def validate(self, context: ComplianceContext, result: ComplianceResult) -> None:
        """Check minor work restrictions."""
        if not context.enable_minor_restrictions:
            return

        rules = context.rules
        severity = ViolationSeverity.ERROR if context.compliance_mode == "enforce" else ViolationSeverity.WARNING

        # Group shifts by employee
        employee_shifts: dict[str, list[ShiftInfo]] = defaultdict(list)
        for shift in context.shifts:
            employee_shifts[shift.employee_name].append(shift)

        for emp_name, shifts in employee_shifts.items():
            employee = context.employees.get(emp_name)
            if not employee or not employee.is_minor:
                continue

            # Track weekly hours for minor
            weekly_hours = 0.0

            for shift in shifts:
                # Check curfew (working after curfew end time)
                curfew_time = datetime.strptime(rules.minor_curfew_end, "%H:%M").time()
                shift_end_time = datetime.strptime(shift.end_time, "%H:%M").time()
                if shift_end_time > curfew_time:
                    result.add_violation(Violation(
                        rule_type=ViolationType.MINOR_CURFEW,
                        severity=severity,
                        employee_name=emp_name,
                        date=shift.date,
                        message=f"Minor {emp_name} scheduled to work until {shift.end_time}, past curfew of {rules.minor_curfew_end}",
                        details={
                            "shift_end": shift.end_time,
                            "curfew": rules.minor_curfew_end,
                        },
                    ))

                # Check early start (working before earliest allowed time)
                earliest_time = datetime.strptime(rules.minor_earliest_start, "%H:%M").time()
                shift_start_time = datetime.strptime(shift.start_time, "%H:%M").time()
                if shift_start_time < earliest_time:
                    result.add_violation(Violation(
                        rule_type=ViolationType.MINOR_EARLY_START,
                        severity=severity,
                        employee_name=emp_name,
                        date=shift.date,
                        message=f"Minor {emp_name} scheduled to start at {shift.start_time}, before allowed time of {rules.minor_earliest_start}",
                        details={
                            "shift_start": shift.start_time,
                            "earliest_allowed": rules.minor_earliest_start,
                        },
                    ))

                # Check daily hours
                if shift.total_hours > rules.minor_max_daily_hours:
                    result.add_violation(Violation(
                        rule_type=ViolationType.MINOR_DAILY_HOURS,
                        severity=severity,
                        employee_name=emp_name,
                        date=shift.date,
                        message=f"Minor {emp_name} scheduled for {shift.total_hours}h on {shift.date}, exceeds max of {rules.minor_max_daily_hours}h",
                        details={
                            "hours_scheduled": shift.total_hours,
                            "max_allowed": rules.minor_max_daily_hours,
                        },
                    ))

                weekly_hours += shift.total_hours

            # Check weekly hours
            if weekly_hours > rules.minor_max_weekly_hours:
                result.add_violation(Violation(
                    rule_type=ViolationType.MINOR_WEEKLY_HOURS,
                    severity=severity,
                    employee_name=emp_name,
                    message=f"Minor {emp_name} scheduled for {weekly_hours}h this week, exceeds max of {rules.minor_max_weekly_hours}h",
                    details={
                        "hours_scheduled": weekly_hours,
                        "max_allowed": rules.minor_max_weekly_hours,
                    },
                ))


class RestBetweenShiftsValidator(BaseValidator):
    """Validates minimum rest between shifts (anti-clopening)."""

    def validate(self, context: ComplianceContext, result: ComplianceResult) -> None:
        """Check rest between consecutive shifts."""
        if not context.enable_rest_between_shifts:
            return

        rules = context.rules
        severity = ViolationSeverity.ERROR if context.compliance_mode == "enforce" else ViolationSeverity.WARNING

        # Combine previous day shifts with current shifts
        all_shifts = context.previous_day_shifts + context.shifts

        # Group by employee and sort by date/time
        employee_shifts: dict[str, list[ShiftInfo]] = defaultdict(list)
        for shift in all_shifts:
            if shift.total_hours > 0:  # Only consider actual shifts
                employee_shifts[shift.employee_name].append(shift)

        for emp_name, shifts in employee_shifts.items():
            # Sort by date and start time
            sorted_shifts = sorted(shifts, key=lambda s: (s.date, s.start_time))

            for i in range(1, len(sorted_shifts)):
                prev_shift = sorted_shifts[i - 1]
                curr_shift = sorted_shifts[i]

                # Calculate rest hours between shifts
                prev_end = prev_shift.end_datetime
                curr_start = curr_shift.start_datetime

                rest_hours = (curr_start - prev_end).total_seconds() / 3600

                if rest_hours < rules.min_rest_hours:
                    result.add_violation(Violation(
                        rule_type=ViolationType.REST_VIOLATION,
                        severity=severity,
                        employee_name=emp_name,
                        date=curr_shift.date,
                        message=f"{emp_name} has only {rest_hours:.1f}h rest between shifts (min {rules.min_rest_hours}h required). Previous shift ended {prev_shift.end_time} on {prev_shift.date}, next starts {curr_shift.start_time} on {curr_shift.date}",
                        details={
                            "rest_hours": round(rest_hours, 1),
                            "min_required": rules.min_rest_hours,
                            "previous_shift_end": prev_shift.end_time,
                            "previous_shift_date": prev_shift.date,
                            "current_shift_start": curr_shift.start_time,
                        },
                    ))


class OvertimeValidator(BaseValidator):
    """Validates overtime thresholds (daily and weekly)."""

    def validate(self, context: ComplianceContext, result: ComplianceResult) -> None:
        """Check overtime limits."""
        if not context.enable_overtime_tracking:
            return

        rules = context.rules
        severity = ViolationSeverity.WARNING  # OT is usually a warning, not blocked

        # Group shifts by employee
        employee_shifts: dict[str, list[ShiftInfo]] = defaultdict(list)
        for shift in context.shifts:
            employee_shifts[shift.employee_name].append(shift)

        for emp_name, shifts in employee_shifts.items():
            weekly_hours = 0.0
            overtime_hours = 0.0

            for shift in shifts:
                # Check daily overtime (if threshold is set, e.g., California)
                if rules.daily_overtime_threshold and shift.total_hours > rules.daily_overtime_threshold:
                    daily_ot = shift.total_hours - rules.daily_overtime_threshold
                    overtime_hours += daily_ot
                    result.add_violation(Violation(
                        rule_type=ViolationType.DAILY_OVERTIME,
                        severity=severity,
                        employee_name=emp_name,
                        date=shift.date,
                        message=f"{emp_name} working {shift.total_hours}h on {shift.date}, {daily_ot:.1f}h daily overtime (threshold: {rules.daily_overtime_threshold}h)",
                        details={
                            "daily_hours": shift.total_hours,
                            "threshold": rules.daily_overtime_threshold,
                            "overtime_hours": round(daily_ot, 1),
                        },
                    ))

                weekly_hours += shift.total_hours

            # Track weekly hours
            result.employee_weekly_hours[emp_name] = weekly_hours

            # Check weekly overtime
            if weekly_hours > rules.weekly_overtime_threshold:
                weekly_ot = weekly_hours - rules.weekly_overtime_threshold
                overtime_hours += weekly_ot
                result.overtime_hours[emp_name] = overtime_hours
                result.add_violation(Violation(
                    rule_type=ViolationType.WEEKLY_OVERTIME,
                    severity=severity,
                    employee_name=emp_name,
                    message=f"{emp_name} scheduled for {weekly_hours:.1f}h this week, {weekly_ot:.1f}h overtime (threshold: {rules.weekly_overtime_threshold}h)",
                    details={
                        "weekly_hours": round(weekly_hours, 1),
                        "threshold": rules.weekly_overtime_threshold,
                        "overtime_hours": round(weekly_ot, 1),
                    },
                ))


class BreakComplianceValidator(BaseValidator):
    """Validates meal and rest break requirements."""

    def validate(self, context: ComplianceContext, result: ComplianceResult) -> None:
        """Check break requirements."""
        if not context.enable_break_compliance:
            return

        rules = context.rules
        severity = ViolationSeverity.WARNING

        for shift in context.shifts:
            if shift.total_hours <= 0:
                continue

            # Check meal break requirement
            if shift.total_hours > rules.meal_break_after_hours:
                result.add_violation(Violation(
                    rule_type=ViolationType.MEAL_BREAK_REQUIRED,
                    severity=severity,
                    employee_name=shift.employee_name,
                    date=shift.date,
                    message=f"{shift.employee_name} working {shift.total_hours}h on {shift.date} - requires {rules.meal_break_duration_minutes}min meal break (shifts > {rules.meal_break_after_hours}h)",
                    details={
                        "shift_hours": shift.total_hours,
                        "break_threshold": rules.meal_break_after_hours,
                        "break_duration": rules.meal_break_duration_minutes,
                    },
                ))

            # Check rest break requirement
            if rules.rest_break_interval_hours and shift.total_hours >= rules.rest_break_interval_hours:
                breaks_needed = int(shift.total_hours / rules.rest_break_interval_hours)
                if breaks_needed > 0:
                    result.add_violation(Violation(
                        rule_type=ViolationType.REST_BREAK_REQUIRED,
                        severity=severity,
                        employee_name=shift.employee_name,
                        date=shift.date,
                        message=f"{shift.employee_name} working {shift.total_hours}h on {shift.date} - entitled to {breaks_needed} x {rules.rest_break_duration_minutes}min rest break(s)",
                        details={
                            "shift_hours": shift.total_hours,
                            "break_interval": rules.rest_break_interval_hours,
                            "breaks_needed": breaks_needed,
                            "break_duration": rules.rest_break_duration_minutes,
                        },
                    ))


class PredictiveSchedulingValidator(BaseValidator):
    """Validates predictive scheduling (advance notice) requirements."""

    def validate(self, context: ComplianceContext, result: ComplianceResult) -> None:
        """Check predictive scheduling compliance."""
        if not context.enable_predictive_scheduling:
            return

        rules = context.rules
        severity = ViolationSeverity.WARNING

        if not context.schedule_start_date:
            return

        # Calculate required publication date
        required_publish_date = context.schedule_start_date - timedelta(days=rules.advance_notice_days)
        publish_date = context.published_at.date() if context.published_at else datetime.now().date()

        if publish_date > required_publish_date:
            days_late = (publish_date - required_publish_date).days
            days_notice = (context.schedule_start_date - publish_date).days

            result.add_violation(Violation(
                rule_type=ViolationType.PREDICTIVE_NOTICE,
                severity=severity,
                employee_name="ALL",  # Affects all employees
                message=f"Schedule published with only {days_notice} days notice (requires {rules.advance_notice_days} days). {days_late} days short of compliance.",
                details={
                    "required_notice_days": rules.advance_notice_days,
                    "actual_notice_days": days_notice,
                    "days_short": days_late,
                    "schedule_start": context.schedule_start_date.isoformat(),
                    "published_at": publish_date.isoformat(),
                },
            ))

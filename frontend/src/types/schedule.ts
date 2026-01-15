export interface ShiftPeriod {
  period_index: number;
  start_time: string;
  end_time: string;
  scheduled: boolean;
}

export interface EmployeeDaySchedule {
  employee_name: string;
  day_of_week: string;
  periods: ShiftPeriod[];
  total_hours: number;
  shift_start: string | null;
  shift_end: string | null;
  is_short_shift: boolean;
}

export interface UnfilledPeriod {
  period_index: number;
  start_time: string;
  end_time: string;
  workers_needed: number;
}

export interface DayScheduleSummary {
  day_of_week: string;
  total_cost: number;
  employees_scheduled: number;
  total_labor_hours: number;
  unfilled_periods: UnfilledPeriod[];
  dummy_worker_cost: number;
}

export interface WeeklyScheduleResult {
  week_no: number;
  store_name: string;
  generated_at: string;
  schedules: EmployeeDaySchedule[];
  daily_summaries: DayScheduleSummary[];
  total_weekly_cost: number;
  status: string;
  total_dummy_worker_cost: number;
  total_short_shift_penalty: number;
  has_warnings: boolean;
}

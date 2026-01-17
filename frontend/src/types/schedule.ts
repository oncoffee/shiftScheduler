export interface ShiftPeriod {
  period_index: number;
  start_time: string;
  end_time: string;
  scheduled: boolean;
  is_locked?: boolean;
}

export interface EmployeeDaySchedule {
  employee_name: string;
  day_of_week: string;
  date?: string | null;  // ISO date string: "2025-01-20"
  periods: ShiftPeriod[];
  total_hours: number;
  shift_start: string | null;
  shift_end: string | null;
  is_short_shift: boolean;
  is_locked?: boolean;
}

export interface UnfilledPeriod {
  period_index: number;
  start_time: string;
  end_time: string;
  workers_needed: number;
}

export interface DayScheduleSummary {
  day_of_week: string;
  date?: string | null;  // ISO date string: "2025-01-20"
  total_cost: number;
  employees_scheduled: number;
  total_labor_hours: number;
  unfilled_periods: UnfilledPeriod[];
  dummy_worker_cost: number;
}

export interface WeeklyScheduleResult {
  start_date: string;  // ISO date string: "2025-01-20"
  end_date: string;    // ISO date string: "2025-01-26"
  store_name: string;
  generated_at: string;
  schedules: EmployeeDaySchedule[];
  daily_summaries: DayScheduleSummary[];
  total_weekly_cost: number;
  status: string;
  total_dummy_worker_cost: number;
  total_short_shift_penalty: number;
  has_warnings: boolean;
  is_edited?: boolean;
  last_edited_at?: string | null;
}

export type DragOperationType = "move" | "resize-start" | "resize-end" | "reassign";

export interface DragOperation {
  type: DragOperationType;
  employee_name: string;
  day_of_week: string;
  original_start: string;
  original_end: string;
  new_start?: string;
  new_end?: string;
  new_employee_name?: string;
}

export interface ShiftEditRequest {
  employee_name: string;
  day_of_week: string;
  new_shift_start: string;
  new_shift_end: string;
  new_employee_name?: string;
}

export interface ShiftEditResponse {
  success: boolean;
  updated_schedule: WeeklyScheduleResult;
  recalculated_cost: number;
}

export interface ValidationError {
  code: string;
  message: string;
}

export interface ValidationWarning {
  code: string;
  message: string;
}

export interface ValidateChangeRequest {
  employee_name: string;
  day_of_week: string;
  proposed_start: string;
  proposed_end: string;
}

export interface ValidateChangeResponse {
  is_valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

export interface ScheduleSnapshot {
  schedules: EmployeeDaySchedule[];
  daily_summaries: DayScheduleSummary[];
  timestamp: number;
}

export interface DraggableShiftData {
  shift: EmployeeDaySchedule;
  employee_name: string;
  day_of_week: string;
}

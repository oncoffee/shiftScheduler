import type {
  WeeklyScheduleResult,
  ShiftEditRequest,
  ShiftEditResponse,
  ValidateChangeRequest,
  ValidateChangeResponse,
} from "@/types/schedule";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }

  const text = await response.text();
  return (text ? JSON.parse(text) : text) as T;
}

export const api = {
  syncAll: (passKey: string) =>
    fetchApi<SyncResult>(`/sync/all?pass_key=${passKey}`, { method: "POST" }),

  runSolver: (passKey: string, startDate: string, endDate: string) =>
    fetchApi<WeeklyScheduleResult>(`/solver/run?pass_key=${passKey}&start_date=${startDate}&end_date=${endDate}`),

  getScheduleResults: () =>
    fetchApi<WeeklyScheduleResult | null>("/schedule/results"),

  getScheduleHistory: (limit = 20, skip = 0) =>
    fetchApi<ScheduleHistoryItem[]>(
      `/schedule/history?limit=${limit}&skip=${skip}`
    ),

  getScheduleById: (id: string) =>
    fetchApi<WeeklyScheduleResult>(`/schedule/${id}`),

  validateChange: (scheduleId: string, request: ValidateChangeRequest) =>
    fetchApi<ValidateChangeResponse>(`/schedule/${scheduleId}/validate`, {
      method: "POST",
      body: JSON.stringify(request),
    }),

  updateAssignment: (scheduleId: string, request: ShiftEditRequest) =>
    fetchApi<ShiftEditResponse>(`/schedule/${scheduleId}/assignment`, {
      method: "PATCH",
      body: JSON.stringify(request),
    }),

  batchUpdateAssignments: (scheduleId: string, updates: ShiftEditRequest[]) =>
    fetchApi<{
      success: boolean;
      updated_schedule: WeeklyScheduleResult;
      recalculated_cost: number;
      failed_updates: { employee_name: string; day_of_week: string; error: string }[];
    }>(`/schedule/${scheduleId}/batch-update`, {
      method: "POST",
      body: JSON.stringify({ updates }),
    }),

  toggleShiftLock: (scheduleId: string, employeeName: string, date: string, isLocked: boolean) =>
    fetchApi<{
      success: boolean;
      updated_schedule: WeeklyScheduleResult;
    }>(`/schedule/${scheduleId}/lock`, {
      method: "PATCH",
      body: JSON.stringify({
        employee_name: employeeName,
        date: date,
        is_locked: isLocked,
      }),
    }),

  deleteShift: (scheduleId: string, employeeName: string, dayOfWeek: string) =>
    fetchApi<{
      success: boolean;
      updated_schedule: WeeklyScheduleResult;
    }>(`/schedule/${scheduleId}/shift`, {
      method: "DELETE",
      body: JSON.stringify({
        employee_name: employeeName,
        day_of_week: dayOfWeek,
      }),
    }),

  getLogs: () => fetchApi<string>("/logs"),

  getEmployees: () => fetchApi<Employee[]>("/employees"),

  getStores: () => fetchApi<Store[]>("/stores"),

  updateStore: (storeName: string, newName: string | null, hours: StoreHoursUpdate[]) =>
    fetchApi<{ success: boolean; store_name: string }>(`/stores/${encodeURIComponent(storeName)}`, {
      method: "PUT",
      body: JSON.stringify({ store_name: newName, hours }),
    }),

  createStore: (storeName: string, hours: StoreHoursUpdate[]) =>
    fetchApi<{ success: boolean; store_name: string }>("/stores", {
      method: "POST",
      body: JSON.stringify({ store_name: storeName, hours }),
    }),

  deleteStore: (storeName: string) =>
    fetchApi<{ success: boolean }>(`/stores/${encodeURIComponent(storeName)}`, {
      method: "DELETE",
    }),

  getStoreStaffing: (storeName: string) =>
    fetchApi<StaffingRequirement[]>(`/stores/${encodeURIComponent(storeName)}/staffing`),

  updateStoreStaffing: (storeName: string, requirements: StaffingRequirement[]) =>
    fetchApi<{ success: boolean; store_name: string }>(`/stores/${encodeURIComponent(storeName)}/staffing`, {
      method: "PUT",
      body: JSON.stringify({ requirements }),
    }),

  getSchedules: () => fetchApi<Schedule[]>("/schedules"),

  updateEmployeeAvailability: (employeeName: string, availability: AvailabilitySlot[]) =>
    fetchApi<{ success: boolean; employee_name: string }>(`/employees/${encodeURIComponent(employeeName)}/availability`, {
      method: "PUT",
      body: JSON.stringify({ availability }),
    }),

  getConfig: () => fetchApi<Config>("/config"),

  updateConfig: (config: Partial<Config>) => {
    const params = new URLSearchParams();
    if (config.dummy_worker_cost !== undefined)
      params.set("dummy_worker_cost", config.dummy_worker_cost.toString());
    if (config.short_shift_penalty !== undefined)
      params.set("short_shift_penalty", config.short_shift_penalty.toString());
    if (config.min_shift_hours !== undefined)
      params.set("min_shift_hours", config.min_shift_hours.toString());
    if (config.max_daily_hours !== undefined)
      params.set("max_daily_hours", config.max_daily_hours.toString());
    if (config.solver_type !== undefined)
      params.set("solver_type", config.solver_type);
    return fetchApi<Config>(`/config?${params.toString()}`, { method: "POST" });
  },

  // Compliance API
  getUSStates: () => fetchApi<USState[]>("/compliance/states"),

  getComplianceRules: () => fetchApi<ComplianceRule[]>("/compliance/rules"),

  getComplianceRule: (jurisdiction: string) =>
    fetchApi<ComplianceRule>(`/compliance/rules/${jurisdiction}`),

  createOrUpdateComplianceRule: (jurisdiction: string, rule: Partial<ComplianceRule>) =>
    fetchApi<{ success: boolean; jurisdiction: string }>(`/compliance/rules/${jurisdiction}`, {
      method: "POST",
      body: JSON.stringify(rule),
    }),

  deleteComplianceRule: (jurisdiction: string) =>
    fetchApi<{ success: boolean }>(`/compliance/rules/${jurisdiction}`, {
      method: "DELETE",
    }),

  researchStateCompliance: (state: string) =>
    fetchApi<ComplianceRuleSuggestion>(`/compliance/ai/research/${state}`, {
      method: "POST",
    }),

  approveAISuggestion: (
    editedSuggestion: ComplianceRuleSuggestion,
    originalSuggestion?: ComplianceRuleSuggestion
  ) =>
    fetchApi<{ success: boolean; jurisdiction: string; edits_made: number; audit_created: boolean }>("/compliance/ai/approve", {
      method: "POST",
      body: JSON.stringify({
        suggestion_id: editedSuggestion.suggestion_id,
        jurisdiction: editedSuggestion.jurisdiction,
        min_rest_hours: editedSuggestion.min_rest_hours,
        minor_curfew_end: editedSuggestion.minor_curfew_end,
        minor_earliest_start: editedSuggestion.minor_earliest_start,
        minor_max_daily_hours: editedSuggestion.minor_max_daily_hours,
        minor_max_weekly_hours: editedSuggestion.minor_max_weekly_hours,
        minor_age_threshold: editedSuggestion.minor_age_threshold,
        daily_overtime_threshold: editedSuggestion.daily_overtime_threshold,
        weekly_overtime_threshold: editedSuggestion.weekly_overtime_threshold,
        meal_break_after_hours: editedSuggestion.meal_break_after_hours,
        meal_break_duration_minutes: editedSuggestion.meal_break_duration_minutes,
        rest_break_interval_hours: editedSuggestion.rest_break_interval_hours,
        rest_break_duration_minutes: editedSuggestion.rest_break_duration_minutes,
        advance_notice_days: editedSuggestion.advance_notice_days,
        sources: editedSuggestion.sources,
        notes: editedSuggestion.notes,
        // Original suggestion for audit trail
        original_suggestion: originalSuggestion ? {
          min_rest_hours: originalSuggestion.min_rest_hours,
          minor_curfew_end: originalSuggestion.minor_curfew_end,
          minor_earliest_start: originalSuggestion.minor_earliest_start,
          minor_max_daily_hours: originalSuggestion.minor_max_daily_hours,
          minor_max_weekly_hours: originalSuggestion.minor_max_weekly_hours,
          minor_age_threshold: originalSuggestion.minor_age_threshold,
          daily_overtime_threshold: originalSuggestion.daily_overtime_threshold,
          weekly_overtime_threshold: originalSuggestion.weekly_overtime_threshold,
          meal_break_after_hours: originalSuggestion.meal_break_after_hours,
          meal_break_duration_minutes: originalSuggestion.meal_break_duration_minutes,
          rest_break_interval_hours: originalSuggestion.rest_break_interval_hours,
          rest_break_duration_minutes: originalSuggestion.rest_break_duration_minutes,
          advance_notice_days: originalSuggestion.advance_notice_days,
          sources: originalSuggestion.sources,
          notes: originalSuggestion.notes,
          model_used: originalSuggestion.model_used,
          confidence_level: originalSuggestion.confidence_level,
          validation_warnings: originalSuggestion.validation_warnings,
          disclaimer: originalSuggestion.disclaimer,
        } : undefined,
      }),
    }),

  validateScheduleCompliance: (scheduleId: string) =>
    fetchApi<ComplianceValidationResult>(`/compliance/validate/${scheduleId}`, {
      method: "POST",
    }),

  // Audit trail endpoints
  getComplianceAuditHistory: (jurisdiction?: string, limit = 50, skip = 0) =>
    fetchApi<ComplianceAuditRecord[]>(
      `/compliance/audit?${jurisdiction ? `jurisdiction=${jurisdiction}&` : ""}limit=${limit}&skip=${skip}`
    ),

  getComplianceAuditDetail: (auditId: string) =>
    fetchApi<ComplianceAuditRecord>(`/compliance/audit/${auditId}`),

  getComplianceConfig: () => fetchApi<ComplianceConfig>("/compliance/config"),

  updateComplianceConfig: (config: Partial<ComplianceConfig>) =>
    fetchApi<ComplianceConfig>("/compliance/config", {
      method: "POST",
      body: JSON.stringify(config),
    }),

  updateEmployeeCompliance: (employeeName: string, data: { date_of_birth?: string; is_minor?: boolean }) =>
    fetchApi<{ success: boolean; employee_name: string }>(`/employees/${encodeURIComponent(employeeName)}/compliance`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  updateStoreJurisdiction: (storeName: string, jurisdiction: string) =>
    fetchApi<{ success: boolean; store_name: string; jurisdiction: string }>(
      `/stores/${encodeURIComponent(storeName)}/jurisdiction?jurisdiction=${jurisdiction}`,
      { method: "PUT" }
    ),
};

export interface AvailabilitySlot {
  day_of_week: string;
  start_time: string;
  end_time: string;
}

export interface Employee {
  employee_name: string;
  hourly_rate: number;
  minimum_hours_per_week: number;
  minimum_hours: number;
  maximum_hours: number;
  availability?: AvailabilitySlot[];
  date_of_birth?: string | null;  // ISO date string
  is_minor?: boolean;
}

export interface EmployeeSchedule {
  employee_name: string;
  day_of_week: string;
  availability: string;
}

export interface Store {
  store_name: string;
  day_of_week: string;
  start_time: string;
  end_time: string;
}

export interface StoreHoursUpdate {
  day_of_week: string;
  start_time: string;
  end_time: string;
}

export interface StaffingRequirement {
  day_type: string;
  start_time: string;
  end_time: string;
  min_staff: number;
}

export interface Schedule {
  employee: string;
  day_of_week: string;
  periods: string[];
}

export type SolverType = "gurobi" | "pulp" | "ortools";

export interface Config {
  dummy_worker_cost: number;
  short_shift_penalty: number;
  min_shift_hours: number;
  max_daily_hours: number;
  solver_type: SolverType;
}

export interface SyncResult {
  employees_synced: number;
  stores_synced: number;
  config_synced: boolean;
  synced_at: string;
}

export interface ScheduleHistoryItem {
  id: string;
  start_date: string;
  end_date: string;
  store_name: string;
  generated_at: string;
  total_weekly_cost: number;
  status: string;
  has_warnings: boolean;
  is_current: boolean;
}

// Compliance Types
export interface USState {
  code: string;
  name: string;
}

export interface ComplianceRule {
  jurisdiction: string;
  min_rest_hours: number;
  minor_max_daily_hours: number;
  minor_max_weekly_hours: number;
  minor_curfew_end: string;
  minor_earliest_start: string;
  minor_age_threshold: number;
  daily_overtime_threshold: number | null;
  weekly_overtime_threshold: number;
  meal_break_after_hours: number;
  meal_break_duration_minutes: number;
  rest_break_interval_hours: number;
  rest_break_duration_minutes: number;
  advance_notice_days: number;
  source: string | null;
  ai_sources: string[];
  notes: string | null;
}

export interface ComplianceRuleSuggestion {
  suggestion_id: string;
  jurisdiction: string;
  state_name: string;
  min_rest_hours: number | null;
  minor_curfew_end: string | null;
  minor_earliest_start: string | null;
  minor_max_daily_hours: number | null;
  minor_max_weekly_hours: number | null;
  minor_age_threshold: number;
  daily_overtime_threshold: number | null;
  weekly_overtime_threshold: number | null;
  meal_break_after_hours: number | null;
  meal_break_duration_minutes: number | null;
  rest_break_interval_hours: number | null;
  rest_break_duration_minutes: number | null;
  advance_notice_days: number | null;
  sources: string[];
  notes: string | null;
  model_used: string;
  created_at: string;
  // Guardrail metadata
  validation_warnings: string[];
  confidence_level: "low" | "medium" | "high";
  requires_human_review: boolean;
  disclaimer: string;
}

export interface ComplianceConfig {
  compliance_mode: "off" | "warn" | "enforce";
  enable_rest_between_shifts: boolean;
  enable_minor_restrictions: boolean;
  enable_overtime_tracking: boolean;
  enable_break_compliance: boolean;
  enable_predictive_scheduling: boolean;
}

export interface ComplianceViolation {
  rule_type: string;
  severity: "error" | "warning";
  employee_name: string;
  date: string | null;
  message: string;
  details: Record<string, unknown>;
}

export interface ComplianceValidationResult {
  violations: ComplianceViolation[];
  is_compliant: boolean;
  error_count: number;
  warning_count: number;
  employee_weekly_hours: Record<string, number>;
  overtime_hours: Record<string, number>;
}

export interface ComplianceRuleEdit {
  field_name: string;
  original_value: string | null;
  edited_value: string | null;
}

export interface ComplianceAuditRecord {
  id: string;
  jurisdiction: string;
  suggestion_id: string;
  ai_model_used: string;
  ai_confidence_level: string;
  ai_sources: string[];
  ai_validation_warnings: string[];
  ai_disclaimer?: string;
  ai_original: Record<string, unknown>;
  human_edits: ComplianceRuleEdit[];
  edit_count: number;
  approved_values: Record<string, unknown>;
  approved_at: string;
  approved_by?: string;
  approval_notes?: string;
  ip_address?: string;
  user_agent?: string;
}

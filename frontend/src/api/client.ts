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

  toggleShiftLock: (scheduleId: string, employeeName: string, dayOfWeek: string, isLocked: boolean) =>
    fetchApi<{
      success: boolean;
      updated_schedule: WeeklyScheduleResult;
    }>(`/schedule/${scheduleId}/lock`, {
      method: "PATCH",
      body: JSON.stringify({
        employee_name: employeeName,
        day_of_week: dayOfWeek,
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
    return fetchApi<Config>(`/config?${params.toString()}`, { method: "POST" });
  },
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

export interface Config {
  dummy_worker_cost: number;
  short_shift_penalty: number;
  min_shift_hours: number;
  max_daily_hours: number;
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

import type { WeeklyScheduleResult } from "@/types/schedule";

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
  // Solver - returns structured schedule result
  runSolver: (passKey: string) =>
    fetchApi<WeeklyScheduleResult>(`/solver/run?pass_key=${passKey}`),

  // Get last schedule results (cached)
  getScheduleResults: () =>
    fetchApi<WeeklyScheduleResult | null>("/schedule/results"),

  // Logs
  getLogs: () => fetchApi<string>("/logs"),

  // Employees
  getEmployees: () => fetchApi<Employee[]>("/employees"),

  // Stores
  getStores: () => fetchApi<Store[]>("/stores"),

  // Employee availability schedules
  getSchedules: () => fetchApi<Schedule[]>("/schedules"),

  // Config
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

// Types
export interface Employee {
  employee_name: string;
  hourly_rate: number;
  minimum_hours_per_week: number;
  minimum_hours: number;
  maximum_hours: number;
}

export interface EmployeeSchedule {
  employee_name: string;
  day_of_week: string;
  availability: string;
}

export interface Store {
  week_no: number;
  store_name: string;
  day_of_week: string;
  start_time: string;
  end_time: string;
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

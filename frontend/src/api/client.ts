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
  // Solver
  runSolver: (passKey: string) =>
    fetchApi<string>(`/solver/run?pass_key=${passKey}`),

  // Logs
  getLogs: () => fetchApi<string>("/logs"),

  // Employees (to be implemented in backend)
  getEmployees: () => fetchApi<Employee[]>("/employees"),

  // Stores (to be implemented in backend)
  getStores: () => fetchApi<Store[]>("/stores"),

  // Schedule (to be implemented in backend)
  getSchedules: () => fetchApi<Schedule[]>("/schedules"),
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

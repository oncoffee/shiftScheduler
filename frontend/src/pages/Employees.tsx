import { useState, useCallback, useRef, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type Employee, type AvailabilitySlot } from "@/api/client";
import { useAsyncData } from "@/hooks/useAsyncData";
import { MultiSlotTimeEditor } from "@/components/employees";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";

const DAYS_OF_WEEK = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

const SHORT_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

interface TimeSlot {
  start_time: string;
  end_time: string;
}

interface GroupedAvailability {
  [day: string]: TimeSlot[];
}

function groupAvailabilityByDay(availability: AvailabilitySlot[] | undefined): GroupedAvailability {
  const grouped: GroupedAvailability = {};
  for (const day of DAYS_OF_WEEK) {
    grouped[day] = [];
  }
  if (!availability) return grouped;

  for (const slot of availability) {
    if (grouped[slot.day_of_week]) {
      grouped[slot.day_of_week].push({
        start_time: slot.start_time,
        end_time: slot.end_time,
      });
    }
  }

  for (const day of DAYS_OF_WEEK) {
    grouped[day].sort((a, b) => {
      const aMinutes = timeToMinutes(a.start_time);
      const bMinutes = timeToMinutes(b.start_time);
      return aMinutes - bMinutes;
    });
  }

  return grouped;
}

function timeToMinutes(time: string): number {
  const [hours, minutes] = time.split(":").map(Number);
  return hours * 60 + minutes;
}

function flattenAvailability(grouped: GroupedAvailability): AvailabilitySlot[] {
  const result: AvailabilitySlot[] = [];
  for (const day of DAYS_OF_WEEK) {
    for (const slot of grouped[day]) {
      result.push({
        day_of_week: day,
        start_time: slot.start_time,
        end_time: slot.end_time,
      });
    }
  }
  return result;
}

interface EmployeeCardProps {
  employee: Employee;
  onAvailabilityChange: (availability: AvailabilitySlot[], shouldRefetch?: boolean) => Promise<void>;
  onComplianceUpdate: (data: { date_of_birth?: string; is_minor?: boolean }) => Promise<void>;
}

function EmployeeCard({ employee, onAvailabilityChange, onComplianceUpdate }: EmployeeCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [localAvailability, setLocalAvailability] = useState<GroupedAvailability>(() =>
    groupAvailabilityByDay(employee.availability)
  );
  const [saving, setSaving] = useState(false);
  const [savingDob, setSavingDob] = useState(false);
  const [localDob, setLocalDob] = useState(employee.date_of_birth || "");
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingAvailabilityRef = useRef<GroupedAvailability | null>(null);

  useEffect(() => {
    setLocalAvailability(groupAvailabilityByDay(employee.availability));
    setLocalDob(employee.date_of_birth || "");
  }, [employee]);

  const handleDobChange = async (newDob: string) => {
    setLocalDob(newDob);
    setSavingDob(true);
    try {
      await onComplianceUpdate({ date_of_birth: newDob || undefined });
    } finally {
      setSavingDob(false);
    }
  };

  const saveChanges = useCallback(async () => {
    if (!pendingAvailabilityRef.current) return;

    setSaving(true);
    try {
      const flattened = flattenAvailability(pendingAvailabilityRef.current);
      await onAvailabilityChange(flattened, false);
      pendingAvailabilityRef.current = null;
    } finally {
      setSaving(false);
    }
  }, [onAvailabilityChange]);

  const handleDayChange = useCallback(
    (day: string, slots: TimeSlot[]) => {
      setLocalAvailability((prev) => {
        const newAvailability = { ...prev, [day]: slots };
        pendingAvailabilityRef.current = newAvailability;
        return newAvailability;
      });

      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
      saveTimeoutRef.current = setTimeout(() => {
        saveChanges();
      }, 800);
    },
    [saveChanges]
  );

  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  const totalAvailableHours = Object.values(localAvailability).reduce((total, slots) => {
    return total + slots.reduce((dayTotal, slot) => {
      const startMinutes = timeToMinutes(slot.start_time);
      const endMinutes = timeToMinutes(slot.end_time);
      return dayTotal + (endMinutes - startMinutes) / 60;
    }, 0);
  }, 0);

  const availableDaysCount = Object.values(localAvailability).filter(
    (slots) => slots.length > 0
  ).length;

  return (
    <Card className="overflow-hidden">
      <div
        className={`flex items-center justify-between px-6 py-4 cursor-pointer hover:bg-gray-50 transition-colors ${
          expanded ? "border-b" : ""
        }`}
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-4">
          {expanded ? (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-400" />
          )}
          <div>
            <div className="font-semibold text-lg">{employee.employee_name}</div>
            <div className="text-sm text-gray-500">
              ${employee.hourly_rate.toFixed(2)}/hr | {employee.minimum_hours}-{employee.maximum_hours}h daily | {employee.minimum_hours_per_week}h/week min
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {(saving || savingDob) && (
            <div className="flex items-center gap-1.5 text-blue-600 text-sm">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Saving...</span>
            </div>
          )}
          {employee.is_minor && (
            <Badge variant="destructive" className="bg-amber-500 hover:bg-amber-600">
              Minor
            </Badge>
          )}
          <Badge variant="outline">
            {availableDaysCount} days | {totalAvailableHours.toFixed(1)}h available
          </Badge>
          <Badge variant="secondary">Active</Badge>
        </div>
      </div>

      {expanded && (
        <CardContent className="pt-4 pb-6">
          {/* Compliance Info */}
          <div className="mb-6 pb-4 border-b">
            <div className="flex items-center gap-6">
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-500">Date of Birth</label>
                <input
                  type="date"
                  value={localDob}
                  onChange={(e) => handleDobChange(e.target.value)}
                  className="block w-40 px-2 py-1 text-sm border rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              {employee.is_minor && (
                <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-md">
                  <span className="text-amber-700 text-sm">
                    ⚠️ Minor employee - restricted hours apply (curfew, max daily/weekly hours)
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Availability Editor */}
          <div className="flex justify-around gap-2">
            {DAYS_OF_WEEK.map((day, idx) => (
              <MultiSlotTimeEditor
                key={day}
                day={SHORT_DAYS[idx]}
                slots={localAvailability[day]}
                onChange={(slots) => handleDayChange(day, slots)}
              />
            ))}
          </div>
          <p className="text-xs text-gray-400 text-center mt-6">
            Drag sliders to adjust availability. Click + to add multiple time slots per day.
          </p>
        </CardContent>
      )}
    </Card>
  );
}

export function Employees() {
  const {
    data: employees,
    loading,
    error,
    refetch,
  } = useAsyncData<Employee[]>(api.getEmployees, "Failed to fetch employees");

  const handleAvailabilityChange = useCallback(
    async (employeeName: string, availability: AvailabilitySlot[], shouldRefetch = true) => {
      await api.updateEmployeeAvailability(employeeName, availability);
      if (shouldRefetch) {
        refetch();
      }
    },
    [refetch]
  );

  const handleComplianceUpdate = useCallback(
    async (employeeName: string, data: { date_of_birth?: string; is_minor?: boolean }) => {
      await api.updateEmployeeCompliance(employeeName, data);
      refetch();
    },
    [refetch]
  );

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Employees</h1>
        <p className="text-muted-foreground mt-1">
          Manage employee information and availability
        </p>
      </div>

      {loading ? (
        <Card>
          <CardContent className="py-8">
            <p className="text-muted-foreground text-center">Loading employees...</p>
          </CardContent>
        </Card>
      ) : error ? (
        <Card>
          <CardContent className="py-8">
            <div className="text-destructive text-center">
              <p>{error}</p>
              <p className="text-sm text-muted-foreground mt-2">
                Make sure the backend API is running and has the /employees endpoint.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : !employees || employees.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">No employees found.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {employees.map((employee) => (
            <EmployeeCard
              key={employee.employee_name}
              employee={employee}
              onAvailabilityChange={(availability, shouldRefetch) =>
                handleAvailabilityChange(employee.employee_name, availability, shouldRefetch)
              }
              onComplianceUpdate={(data) =>
                handleComplianceUpdate(employee.employee_name, data)
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

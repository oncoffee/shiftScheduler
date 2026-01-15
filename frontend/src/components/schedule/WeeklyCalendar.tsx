import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, AlertTriangle } from "lucide-react";
import type { EmployeeDaySchedule, DayScheduleSummary } from "@/types/schedule";

const DAYS_ORDER = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

const EMPLOYEE_COLORS = [
  "#93C5FD", // Light Blue
  "#A5B4FC", // Light Indigo
  "#C4B5FD", // Light Violet
  "#F0ABFC", // Light Fuchsia
  "#FDA4AF", // Light Rose
  "#FCD34D", // Light Amber
  "#86EFAC", // Light Green
  "#5EEAD4", // Light Teal
  "#7DD3FC", // Light Sky
  "#D8B4FE", // Light Purple
];

const HOUR_SLOTS = Array.from({ length: 17 }, (_, i) => {
  const hour = i + 6;
  const ampm = hour >= 12 ? "PM" : "AM";
  const displayHour = hour > 12 ? hour - 12 : hour === 0 ? 12 : hour;
  return { hour, label: `${displayHour} ${ampm}` };
});

interface WeeklyCalendarProps {
  schedules: EmployeeDaySchedule[];
  dailySummaries: DayScheduleSummary[];
}

function parseTimeToHour(timeStr: string): number {
  const match = timeStr.match(/(\d{1,2}):(\d{2})/);
  if (match) {
    const hours = parseInt(match[1], 10);
    const minutes = parseInt(match[2], 10);
    return hours + minutes / 60;
  }
  return 9;
}

function formatTime(timeStr: string): string {
  const hour = parseTimeToHour(timeStr);
  const h = Math.floor(hour);
  const m = Math.round((hour - h) * 60);
  const ampm = h >= 12 ? "PM" : "AM";
  const displayH = h > 12 ? h - 12 : h === 0 ? 12 : h;
  return m > 0 ? `${displayH}:${m.toString().padStart(2, "0")} ${ampm}` : `${displayH} ${ampm}`;
}

export function WeeklyCalendar({
  schedules,
  dailySummaries,
}: WeeklyCalendarProps) {
  const [selectedDayIndex, setSelectedDayIndex] = useState(0);
  const selectedDay = DAYS_ORDER[selectedDayIndex];

  const employees = useMemo(
    () => [...new Set(schedules.map((s) => s.employee_name))].sort(),
    [schedules]
  );

  const employeeColorMap = useMemo(
    () => new Map(employees.map((emp, i) => [emp, EMPLOYEE_COLORS[i % EMPLOYEE_COLORS.length]])),
    [employees]
  );

  const shiftsByEmployee = useMemo(() => {
    const map = new Map<string, EmployeeDaySchedule | null>();
    employees.forEach((emp) => map.set(emp, null));

    schedules.forEach((schedule) => {
      if (schedule.day_of_week === selectedDay && schedule.total_hours > 0) {
        map.set(schedule.employee_name, schedule);
      }
    });

    return map;
  }, [schedules, employees, selectedDay]);

  const summaryByDay = useMemo(
    () => new Map(dailySummaries.map((s) => [s.day_of_week, s])),
    [dailySummaries]
  );

  const daySummary = summaryByDay.get(selectedDay);
  const totalCost = dailySummaries.reduce((sum, s) => sum + s.total_cost, 0);
  const hasUnfilled = daySummary && daySummary.unfilled_periods.length > 0;

  const mergedUnfilledPeriods = useMemo(() => {
    if (!daySummary || daySummary.unfilled_periods.length === 0) return [];

    const periods = [...daySummary.unfilled_periods].sort(
      (a, b) => a.period_index - b.period_index
    );

    const merged: { start_time: string; end_time: string; workers_needed: number }[] = [];
    let current = { ...periods[0] };

    for (let i = 1; i < periods.length; i++) {
      const period = periods[i];
      const isConsecutive = period.period_index === periods[i - 1].period_index + 1;
      const sameWorkerCount = period.workers_needed === current.workers_needed;

      if (isConsecutive && sameWorkerCount) {
        current.end_time = period.end_time;
      } else {
        merged.push(current);
        current = { ...period };
      }
    }
    merged.push(current);

    return merged;
  }, [daySummary]);

  const HOUR_HEIGHT = 60;
  const START_HOUR = 6;
  const totalColumns = employees.length + (hasUnfilled ? 1 : 0);

  const prevDay = () => setSelectedDayIndex((i) => (i === 0 ? 6 : i - 1));
  const nextDay = () => setSelectedDayIndex((i) => (i === 6 ? 0 : i + 1));

  return (
    <div className="space-y-4">
      {/* Day selector */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={prevDay}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <ChevronLeft className="w-5 h-5 text-gray-600" />
          </button>
          <div className="flex gap-1">
            {DAYS_ORDER.map((day, idx) => (
              <button
                key={day}
                onClick={() => setSelectedDayIndex(idx)}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  idx === selectedDayIndex
                    ? "bg-blue-500 text-white"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                {day.slice(0, 3)}
              </button>
            ))}
          </div>
          <button
            onClick={nextDay}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <ChevronRight className="w-5 h-5 text-gray-600" />
          </button>
        </div>
        {daySummary && (
          <div className="text-sm text-gray-500">
            <span className="font-semibold text-gray-900">${daySummary.total_cost.toFixed(0)}</span>
            {" "}· {daySummary.employees_scheduled} employees
          </div>
        )}
      </div>

      {/* Calendar grid */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {/* Header - Employee names + Unfilled column */}
        <div
          className="grid border-b border-gray-200 bg-gray-50"
          style={{ gridTemplateColumns: `70px repeat(${totalColumns}, minmax(100px, 1fr))` }}
        >
          <div className="p-3 text-xs text-gray-400 text-center">Time</div>
          {employees.map((emp) => {
            const color = employeeColorMap.get(emp)!;
            const hasShift = shiftsByEmployee.get(emp) !== null;
            return (
              <div
                key={emp}
                className={`p-3 text-center border-l border-gray-200 ${!hasShift ? "opacity-40" : ""}`}
              >
                <div
                  className="inline-block w-2.5 h-2.5 rounded-full mr-1.5"
                  style={{ backgroundColor: color }}
                />
                <span className="text-sm font-medium text-gray-700">{emp}</span>
              </div>
            );
          })}
          {hasUnfilled && (
            <div className="p-3 text-center border-l border-red-200 bg-red-50">
              <AlertTriangle className="inline-block w-3 h-3 text-red-500 mr-1.5" />
              <span className="text-sm font-medium text-red-700">Unfilled</span>
            </div>
          )}
        </div>

        {/* Time grid */}
        <div
          className="grid"
          style={{ gridTemplateColumns: `70px repeat(${totalColumns}, minmax(100px, 1fr))` }}
        >
          {/* Time labels column */}
          <div className="border-r border-gray-100">
            {HOUR_SLOTS.map(({ hour, label }) => (
              <div
                key={hour}
                className="h-[60px] flex items-start justify-end pr-3 text-xs text-gray-400 border-b border-gray-50"
              >
                {label}
              </div>
            ))}
          </div>

          {/* Employee columns */}
          {employees.map((emp) => {
            const shift = shiftsByEmployee.get(emp);
            const color = employeeColorMap.get(emp)!;

            return (
              <div
                key={emp}
                className="relative border-l border-gray-100"
                style={{ height: HOUR_SLOTS.length * HOUR_HEIGHT }}
              >
                {/* Hour grid lines */}
                {HOUR_SLOTS.map(({ hour }) => (
                  <div
                    key={hour}
                    className="absolute w-full border-b border-gray-50"
                    style={{ top: (hour - START_HOUR + 1) * HOUR_HEIGHT }}
                  />
                ))}

                {/* Shift block */}
                {shift && (
                  <div
                    className={`absolute left-2 right-2 rounded-lg px-3 py-2 cursor-default hover:shadow-lg transition-shadow ${
                      shift.is_short_shift ? "border-2 border-dashed border-orange-400" : ""
                    }`}
                    style={{
                      top: (parseTimeToHour(shift.shift_start!) - START_HOUR) * HOUR_HEIGHT + 2,
                      height: (parseTimeToHour(shift.shift_end!) - parseTimeToHour(shift.shift_start!)) * HOUR_HEIGHT - 4,
                      backgroundColor: shift.is_short_shift ? "#FED7AA" : color,
                    }}
                  >
                    <div className="flex items-center gap-1">
                      <span className="text-sm font-semibold text-gray-800">{emp}</span>
                      {shift.is_short_shift && (
                        <AlertTriangle className="w-3 h-3 text-orange-500" />
                      )}
                    </div>
                    <div className="text-xs text-gray-600 mt-0.5">
                      {formatTime(shift.shift_start!)} - {formatTime(shift.shift_end!)}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {shift.total_hours}h
                      {shift.is_short_shift && <span className="text-orange-500 ml-1">(short)</span>}
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* Unfilled column */}
          {hasUnfilled && daySummary && (
            <div
              className="relative border-l border-red-200 bg-red-50/30"
              style={{ height: HOUR_SLOTS.length * HOUR_HEIGHT }}
            >
              {/* Hour grid lines */}
              {HOUR_SLOTS.map(({ hour }) => (
                <div
                  key={hour}
                  className="absolute w-full border-b border-red-100"
                  style={{ top: (hour - START_HOUR + 1) * HOUR_HEIGHT }}
                />
              ))}

              {/* Unfilled period blocks (merged) */}
              {mergedUnfilledPeriods.map((period, idx) => {
                const startHour = parseTimeToHour(period.start_time);
                const endHour = parseTimeToHour(period.end_time);
                const height = (endHour - startHour) * HOUR_HEIGHT - 4;
                return (
                  <div
                    key={idx}
                    className="absolute left-2 right-2 rounded-lg px-2 py-2 bg-red-100 border-2 border-dashed border-red-300 cursor-default"
                    style={{
                      top: (startHour - START_HOUR) * HOUR_HEIGHT + 2,
                      height,
                    }}
                  >
                    <div className="text-sm font-semibold text-red-700">
                      {period.workers_needed} needed
                    </div>
                    <div className="text-xs text-red-600">
                      {formatTime(period.start_time)} - {formatTime(period.end_time)}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Summary */}
      <div className="flex items-center justify-end text-sm">
        <span className="text-gray-400">Weekly Total</span>
        <span className="ml-2 text-xl font-bold text-gray-900">
          ${totalCost.toLocaleString()}
        </span>
      </div>
    </div>
  );
}

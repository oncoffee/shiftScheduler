import { useMemo, useState, useCallback, useEffect, useRef } from "react";
import { ChevronLeft, ChevronRight, AlertTriangle } from "lucide-react";
import {
  DndContext,
  DragOverlay,
  useDroppable,
  useSensor,
  useSensors,
  PointerSensor,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import type { EmployeeDaySchedule, DayScheduleSummary } from "@/types/schedule";
import type { Employee } from "@/api/client";
import { DraggableShift, ShiftPreview } from "./DraggableShift";
import { useScheduleEdit } from "@/hooks/useScheduleEdit";

const DAYS_ORDER = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

const EMPLOYEE_COLORS = [
  "#93C5FD",
  "#A5B4FC",
  "#C4B5FD",
  "#F0ABFC",
  "#FDA4AF",
  "#FCD34D",
  "#86EFAC",
  "#5EEAD4",
  "#7DD3FC",
  "#D8B4FE",
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
  startDate?: string;  // ISO date string: "2025-01-20"
  isEditMode?: boolean;
  onShiftUpdate?: (
    employeeName: string,
    dayOfWeek: string,
    newStart: string,
    newEnd: string,
    originalStart: string,
    originalEnd: string,
    newEmployeeName?: string
  ) => void;
  onToggleLock?: (employeeName: string, date: string) => void;
  onShiftClick?: (shift: EmployeeDaySchedule) => void;
  onEmptyClick?: (employeeName: string, dayOfWeek: string, startTime?: string, endTime?: string) => void;
  employeeAvailability?: Employee[];
}

// Helper to get the Monday of the week containing a given date
function getMondayOfWeek(date: Date): Date {
  const d = new Date(date);
  const dayOfWeek = d.getDay();
  const daysFromMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
  d.setDate(d.getDate() + daysFromMonday);
  return d;
}

// Helper to get dates for each day of the week based on start date and week offset
function getDayDates(startDateStr: string | undefined, weekOffset: number = 0): Map<string, Date> {
  const dayDates = new Map<string, Date>();
  if (!startDateStr) return dayDates;

  const startDate = new Date(startDateStr + "T00:00:00");
  const monday = getMondayOfWeek(startDate);

  // Apply week offset
  monday.setDate(monday.getDate() + (weekOffset * 7));

  // DAYS_ORDER is Monday-first: Mon=0, Tue=1, ..., Sun=6
  DAYS_ORDER.forEach((day, idx) => {
    const date = new Date(monday);
    date.setDate(monday.getDate() + idx);
    dayDates.set(day, date);
  });

  return dayDates;
}

// Format date to ISO string (YYYY-MM-DD) for comparison
function formatDateToISO(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// Helper to get the full date objects for the current week
function getWeekDatesRange(startDateStr: string | undefined, weekOffset: number = 0): { monday: Date; sunday: Date } | null {
  if (!startDateStr) return null;

  const startDate = new Date(startDateStr + "T00:00:00");
  const monday = getMondayOfWeek(startDate);
  monday.setDate(monday.getDate() + (weekOffset * 7));

  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);

  return { monday, sunday };
}

// Format a week range for display
function formatWeekRange(monday: Date, sunday: Date): string {
  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const startMonth = monthNames[monday.getMonth()];
  const endMonth = monthNames[sunday.getMonth()];
  const startDay = monday.getDate();
  const endDay = sunday.getDate();
  const year = monday.getFullYear();

  if (startMonth === endMonth) {
    return `${startMonth} ${startDay} - ${endDay}, ${year}`;
  }
  return `${startMonth} ${startDay} - ${endMonth} ${endDay}, ${year}`;
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

interface ShiftBlock {
  start_time: string;
  end_time: string;
  total_hours: number;
  is_short_shift: boolean;
}

function getContiguousShiftBlocks(schedule: EmployeeDaySchedule): ShiftBlock[] {
  const scheduledPeriods = schedule.periods
    .filter((p) => p.scheduled)
    .sort((a, b) => {
      const aStart = parseTimeToHour(a.start_time);
      const bStart = parseTimeToHour(b.start_time);
      return aStart - bStart;
    });

  if (scheduledPeriods.length === 0) return [];

  const blocks: ShiftBlock[] = [];
  let currentBlock = {
    start_time: scheduledPeriods[0].start_time,
    end_time: scheduledPeriods[0].end_time,
    periodCount: 1,
  };

  for (let i = 1; i < scheduledPeriods.length; i++) {
    const period = scheduledPeriods[i];
    if (period.start_time === currentBlock.end_time) {
      currentBlock.end_time = period.end_time;
      currentBlock.periodCount++;
    } else {
      const totalHours = currentBlock.periodCount * 0.5;
      blocks.push({
        start_time: currentBlock.start_time,
        end_time: currentBlock.end_time,
        total_hours: totalHours,
        is_short_shift: totalHours > 0 && totalHours < 3,
      });
      currentBlock = {
        start_time: period.start_time,
        end_time: period.end_time,
        periodCount: 1,
      };
    }
  }

  const totalHours = currentBlock.periodCount * 0.5;
  blocks.push({
    start_time: currentBlock.start_time,
    end_time: currentBlock.end_time,
    total_hours: totalHours,
    is_short_shift: totalHours > 0 && totalHours < 3,
  });

  return blocks;
}

function formatTime(timeStr: string): string {
  const hour = parseTimeToHour(timeStr);
  const h = Math.floor(hour);
  const m = Math.round((hour - h) * 60);
  const ampm = h >= 12 ? "PM" : "AM";
  const displayH = h > 12 ? h - 12 : h === 0 ? 12 : h;
  return m > 0 ? `${displayH}:${m.toString().padStart(2, "0")} ${ampm}` : `${displayH} ${ampm}`;
}

const HOUR_HEIGHT = 60;
const START_HOUR = 6;

function pixelToTime(pixelY: number): string {
  const hourOffset = pixelY / HOUR_HEIGHT;
  const totalHour = START_HOUR + hourOffset;
  const hours = Math.floor(totalHour);
  const minutes = Math.round((totalHour - hours) * 2) * 30; // Snap to 30-min
  const clampedHours = Math.max(6, Math.min(22, hours + (minutes >= 60 ? 1 : 0)));
  const clampedMins = minutes >= 60 ? 0 : minutes;
  return `${clampedHours.toString().padStart(2, "0")}:${clampedMins.toString().padStart(2, "0")}`;
}

interface SelectionPreviewProps {
  startY: number;
  endY: number;
}

function SelectionPreview({ startY, endY }: SelectionPreviewProps) {
  const top = Math.min(startY, endY);
  const height = Math.abs(endY - startY);
  const startTime = pixelToTime(top);
  const endTime = pixelToTime(top + height);

  return (
    <div
      className="absolute left-2 right-2 rounded-lg border-2 border-dashed border-blue-400 bg-blue-200/50 pointer-events-none z-10"
      style={{ top, height: Math.max(height, 4) }}
    >
      {height >= 20 && (
        <div className="p-2 text-xs font-medium text-blue-900">
          {formatTime(startTime)} - {formatTime(endTime)}
        </div>
      )}
    </div>
  );
}

interface UnavailableRange {
  startHour: number;
  endHour: number;
}

interface DroppableColumnProps {
  employeeName: string;
  isEditMode: boolean;
  isPastDate: boolean;
  height: number;
  isOver: boolean;
  children: React.ReactNode;
  isSelecting: boolean;
  selectionStartY: number | null;
  selectionEndY: number | null;
  selectingEmployee: string | null;
  onSelectionStart: (y: number, employee: string) => void;
  onSelectionMove: (y: number, maxHeight: number) => void;
  onSelectionEnd: () => void;
  unavailableRanges?: UnavailableRange[];
}

function DroppableColumn({
  employeeName,
  isEditMode,
  isPastDate,
  height,
  isOver,
  children,
  isSelecting,
  selectionStartY,
  selectionEndY,
  selectingEmployee,
  onSelectionStart,
  onSelectionMove,
  onSelectionEnd,
  unavailableRanges = [],
}: DroppableColumnProps) {
  const { setNodeRef } = useDroppable({
    id: `column-${employeeName}`,
    data: { type: "column", employeeName },
  });

  const handleMouseDown = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.closest("button") || target.closest("[data-shift-block]")) return;
    if (!isEditMode || isPastDate) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const y = e.clientY - rect.top;
    onSelectionStart(y, employeeName);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isSelecting || selectingEmployee !== employeeName) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const y = e.clientY - rect.top;
    onSelectionMove(y, height);
  };

  const handleMouseUp = () => {
    if (isSelecting && selectingEmployee === employeeName) {
      onSelectionEnd();
    }
  };

  const handleMouseLeave = () => {};

  const isThisColumnSelecting = isSelecting && selectingEmployee === employeeName;
  const canEdit = isEditMode && !isPastDate;

  return (
    <div
      ref={setNodeRef}
      className={`relative border-l border-gray-100 transition-colors select-none ${
        canEdit ? "bg-blue-50/20 cursor-crosshair hover:bg-blue-50/40" : ""
      } ${isPastDate ? "bg-gray-50/50" : ""} ${isOver && !isPastDate ? "bg-green-100/50 ring-2 ring-green-400 ring-inset" : ""}`}
      style={{ height }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
    >
      {unavailableRanges.map((range, idx) => {
        const top = (range.startHour - START_HOUR) * HOUR_HEIGHT;
        const rangeHeight = (range.endHour - range.startHour) * HOUR_HEIGHT;
        return (
          <div
            key={`unavail-${idx}`}
            className="absolute left-0 right-0 bg-red-100/60 pointer-events-none"
            style={{ top, height: rangeHeight }}
          />
        );
      })}
      {children}
      {isThisColumnSelecting && selectionStartY !== null && selectionEndY !== null && (
        <SelectionPreview
          startY={selectionStartY}
          endY={selectionEndY}
        />
      )}
    </div>
  );
}

function getTodayDayIndex(): number {
  const today = new Date();
  const jsDay = today.getDay();
  return jsDay === 0 ? 6 : jsDay - 1;
}

function getWeekOffsetToToday(startDateStr: string | undefined): number {
  if (!startDateStr) return 0;

  const scheduleStart = new Date(startDateStr + "T00:00:00");
  const scheduleMonday = getMondayOfWeek(scheduleStart);
  const todayMonday = getMondayOfWeek(new Date());

  const diffTime = todayMonday.getTime() - scheduleMonday.getTime();
  const diffWeeks = Math.round(diffTime / (7 * 24 * 60 * 60 * 1000));

  return diffWeeks;
}

function getUnavailableRanges(
  employeeName: string,
  dayOfWeek: string,
  employeeAvailability: Employee[] | undefined
): UnavailableRange[] {
  if (!employeeAvailability) return [];

  const employee = employeeAvailability.find(e => e.employee_name === employeeName);
  if (!employee || !employee.availability || employee.availability.length === 0) {
    return [];
  }

  const daySlots = employee.availability.filter(slot => slot.day_of_week === dayOfWeek);

  if (daySlots.length === 0) {
    return [{ startHour: START_HOUR, endHour: START_HOUR + HOUR_SLOTS.length }];
  }

  const unavailable: UnavailableRange[] = [];
  const visibleStart = START_HOUR;
  const visibleEnd = START_HOUR + HOUR_SLOTS.length;

  const sortedSlots = [...daySlots].sort((a, b) => {
    const aStart = parseTimeToHour(a.start_time);
    const bStart = parseTimeToHour(b.start_time);
    return aStart - bStart;
  });

  let currentHour = visibleStart;

  for (const slot of sortedSlots) {
    const slotStart = parseTimeToHour(slot.start_time);
    const slotEnd = parseTimeToHour(slot.end_time);

    if (slotStart > currentHour) {
      unavailable.push({
        startHour: Math.max(currentHour, visibleStart),
        endHour: Math.min(slotStart, visibleEnd),
      });
    }

    currentHour = Math.max(currentHour, slotEnd);
  }

  if (currentHour < visibleEnd) {
    unavailable.push({
      startHour: Math.max(currentHour, visibleStart),
      endHour: visibleEnd,
    });
  }

  return unavailable.filter(r => r.endHour > r.startHour && r.startHour < visibleEnd && r.endHour > visibleStart);
}

export function WeeklyCalendar({
  schedules,
  dailySummaries,
  startDate,
  isEditMode = false,
  onShiftUpdate,
  onToggleLock,
  onShiftClick,
  onEmptyClick,
  employeeAvailability,
}: WeeklyCalendarProps) {
  const [selectedDayIndex, setSelectedDayIndex] = useState(getTodayDayIndex);
  const [weekOffset, setWeekOffset] = useState(0);
  const hasInitializedWeek = useRef(false);
  const selectedDay = DAYS_ORDER[selectedDayIndex];
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    if (startDate && !hasInitializedWeek.current) {
      hasInitializedWeek.current = true;
      setWeekOffset(getWeekOffsetToToday(startDate));
    }
  }, [startDate]);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(new Date());
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  const dayDates = useMemo(() => getDayDates(startDate, weekOffset), [startDate, weekOffset]);
  const weekRange = useMemo(() => getWeekDatesRange(startDate, weekOffset), [startDate, weekOffset]);
  const [activeShift, setActiveShift] = useState<EmployeeDaySchedule | null>(null);
  const [overColumn, setOverColumn] = useState<string | null>(null);

  const [isSelecting, setIsSelecting] = useState(false);
  const [selectionStartY, setSelectionStartY] = useState<number | null>(null);
  const [selectionEndY, setSelectionEndY] = useState<number | null>(null);
  const [selectingEmployee, setSelectingEmployee] = useState<string | null>(null);

  const { calculateNewTimes } = useScheduleEdit();

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  const employees = useMemo(
    () => [...new Set(schedules.map((s) => s.employee_name))].sort(),
    [schedules]
  );

  const employeeColorMap = useMemo(
    () => new Map(employees.map((emp, i) => [emp, EMPLOYEE_COLORS[i % EMPLOYEE_COLORS.length]])),
    [employees]
  );

  const selectedDate = useMemo(() => {
    const date = dayDates.get(selectedDay);
    return date ? formatDateToISO(date) : null;
  }, [dayDates, selectedDay]);

  const isViewingToday = selectedDate === formatDateToISO(new Date());
  const isViewingPastDate = useMemo(() => {
    if (!selectedDate) return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const viewDate = new Date(selectedDate + "T00:00:00");
    return viewDate < today;
  }, [selectedDate]);

  const currentTimePosition = useMemo(() => {
    const hours = currentTime.getHours();
    const minutes = currentTime.getMinutes();
    const timeInHours = hours + minutes / 60;
    if (timeInHours < START_HOUR || timeInHours > START_HOUR + HOUR_SLOTS.length) {
      return null;
    }
    return (timeInHours - START_HOUR) * HOUR_HEIGHT;
  }, [currentTime]);

  const shiftsByEmployee = useMemo(() => {
    const map = new Map<string, EmployeeDaySchedule | null>();
    employees.forEach((emp) => map.set(emp, null));

    schedules.forEach((schedule) => {
      // Match by actual date if available, otherwise fall back to day_of_week
      const matchesByDate = selectedDate && schedule.date === selectedDate;
      const matchesByDay = !selectedDate && schedule.day_of_week === selectedDay;

      if ((matchesByDate || matchesByDay) && schedule.total_hours > 0) {
        map.set(schedule.employee_name, schedule);
      }
    });

    return map;
  }, [schedules, employees, selectedDay, selectedDate]);

  const summaryByDate = useMemo(
    () => new Map(dailySummaries.filter(s => s.date).map((s) => [s.date, s])),
    [dailySummaries]
  );

  const summaryByDay = useMemo(
    () => new Map(dailySummaries.map((s) => [s.day_of_week, s])),
    [dailySummaries]
  );

  // Match by date first, then fall back to day_of_week
  const daySummary = selectedDate
    ? summaryByDate.get(selectedDate) || summaryByDay.get(selectedDay)
    : summaryByDay.get(selectedDay);
  const totalCost = dailySummaries.reduce((sum, s) => sum + s.total_cost - (s.dummy_worker_cost || 0), 0);
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

  const totalColumns = employees.length + (hasUnfilled ? 1 : 0);

  const prevWeek = () => setWeekOffset((w) => w - 1);
  const nextWeek = () => setWeekOffset((w) => w + 1);
  const todayWeekOffset = getWeekOffsetToToday(startDate);
  const goToToday = () => {
    setWeekOffset(todayWeekOffset);
    setSelectedDayIndex(getTodayDayIndex());
  };
  const isAtTodayWeek = weekOffset === todayWeekOffset;

  const handleSelectionStart = useCallback((y: number, employee: string) => {
    if (isViewingPastDate) return;
    setIsSelecting(true);
    setSelectionStartY(y);
    setSelectionEndY(y);
    setSelectingEmployee(employee);
  }, [isViewingPastDate]);

  const handleSelectionMove = useCallback((y: number, maxHeight: number) => {
    if (!isSelecting) return;
    const clampedY = Math.max(0, Math.min(y, maxHeight));
    setSelectionEndY(clampedY);
  }, [isSelecting]);

  const handleSelectionEnd = useCallback(() => {
    if (isSelecting && selectionStartY !== null && selectionEndY !== null && selectingEmployee && !isViewingPastDate) {
      const startY = Math.min(selectionStartY, selectionEndY);
      const endY = Math.max(selectionStartY, selectionEndY);

      if (endY - startY >= HOUR_HEIGHT / 2) {
        const startTime = pixelToTime(startY);
        const endTime = pixelToTime(endY);
        onEmptyClick?.(selectingEmployee, selectedDay, startTime, endTime);
      } else {
        onEmptyClick?.(selectingEmployee, selectedDay);
      }
    }
    setIsSelecting(false);
    setSelectionStartY(null);
    setSelectionEndY(null);
    setSelectingEmployee(null);
  }, [isSelecting, selectionStartY, selectionEndY, selectingEmployee, selectedDay, onEmptyClick, isViewingPastDate]);

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setIsSelecting(false);
    setSelectionStartY(null);
    setSelectionEndY(null);
    setSelectingEmployee(null);

    const { active } = event;
    const shiftData = active.data.current;
    if (shiftData?.type === "shift") {
      setActiveShift(shiftData.shift);
    }
  }, []);

  const handleDragOver = useCallback((event: { over: { data: { current?: { type?: string; employeeName?: string } } } | null }) => {
    const overData = event.over?.data.current;
    if (overData?.type === "column") {
      setOverColumn(overData.employeeName || null);
    } else {
      setOverColumn(null);
    }
  }, []);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over, delta } = event;
      const shiftData = active.data.current;

      if (shiftData?.type === "shift" && activeShift && onShiftUpdate) {
        const { newStart, newEnd } = calculateNewTimes(activeShift, delta.y, "move");
        const originalStart = activeShift.shift_start!;
        const originalEnd = activeShift.shift_end!;

        const overData = over?.data.current as { type?: string; employeeName?: string } | undefined;
        const targetEmployee = overData?.type === "column" ? overData.employeeName : undefined;
        const newEmployeeName = targetEmployee && targetEmployee !== activeShift.employee_name
          ? targetEmployee
          : undefined;

        onShiftUpdate(
          activeShift.employee_name,
          activeShift.day_of_week,
          newStart,
          newEnd,
          originalStart,
          originalEnd,
          newEmployeeName
        );
      }

      setActiveShift(null);
      setOverColumn(null);
    },
    [activeShift, onShiftUpdate, calculateNewTimes]
  );

  const handleResizeStart = useCallback(
    (shift: EmployeeDaySchedule, type: "resize-start" | "resize-end") => {
      let startY = 0;
      const originalStart = shift.shift_start!;
      const originalEnd = shift.shift_end!;

      const handleMouseMove = (e: MouseEvent) => {
        if (startY === 0) {
          startY = e.clientY;
        }
      };

      const handleMouseUp = (e: MouseEvent) => {
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);

        if (!onShiftUpdate || startY === 0) return;

        const deltaY = e.clientY - startY;
        const { newStart, newEnd } = calculateNewTimes(shift, deltaY, type);

        onShiftUpdate(
          shift.employee_name,
          shift.day_of_week,
          newStart,
          newEnd,
          originalStart,
          originalEnd
        );
      };

      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    },
    [calculateNewTimes, onShiftUpdate]
  );

  return (
    <div className="space-y-4">
      {/* Week navigation */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={prevWeek}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            title="Previous week"
          >
            <ChevronLeft className="w-5 h-5 text-gray-600" />
          </button>
          <div className="text-center min-w-[180px]">
            <div className="text-sm font-semibold text-gray-900">
              {weekRange ? formatWeekRange(weekRange.monday, weekRange.sunday) : "Select dates"}
            </div>
            {!isAtTodayWeek && (
              <button
                onClick={goToToday}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                Go to today
              </button>
            )}
          </div>
          <button
            onClick={nextWeek}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            title="Next week"
          >
            <ChevronRight className="w-5 h-5 text-gray-600" />
          </button>
        </div>
        {daySummary && (
          <div className="text-sm text-gray-500">
            <span className="font-semibold text-gray-900">${(daySummary.total_cost - (daySummary.dummy_worker_cost || 0)).toFixed(0)}</span>
            {" "}· {daySummary.employees_scheduled} employees
          </div>
        )}
      </div>

      {/* Day tabs */}
      <div className="flex items-center justify-center gap-1">
        {DAYS_ORDER.map((day, idx) => {
          const dayDate = dayDates.get(day);
          const dateNum = dayDate?.getDate();
          const isToday = dayDate ? formatDateToISO(dayDate) === formatDateToISO(new Date()) : false;
          return (
            <button
              key={day}
              onClick={() => setSelectedDayIndex(idx)}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors relative ${
                idx === selectedDayIndex
                  ? "bg-blue-500 text-white"
                  : isToday
                    ? "text-blue-600 bg-blue-50 ring-1 ring-blue-300"
                    : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              {day.slice(0, 3)}{dateNum !== undefined ? ` ${dateNum}` : ""}
              {isToday && idx !== selectedDayIndex && (
                <span className="absolute -top-1 -right-1 w-2 h-2 bg-blue-500 rounded-full" />
              )}
            </button>
          );
        })}
      </div>

      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
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

          <div
            className="grid relative"
            style={{ gridTemplateColumns: `70px repeat(${totalColumns}, minmax(100px, 1fr))` }}
          >
            {isViewingToday && currentTimePosition !== null && (
              <div
                className="absolute left-[70px] right-0 z-20 pointer-events-none flex items-center"
                style={{ top: currentTimePosition }}
              >
                <div className="w-3 h-3 rounded-full bg-red-500 -ml-1.5 shrink-0" />
                <div className="flex-1 h-0.5 bg-red-500" />
              </div>
            )}
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

            {employees.map((emp) => {
              const schedule = shiftsByEmployee.get(emp);
              const color = employeeColorMap.get(emp)!;
              const isColumnOver = overColumn === emp && activeShift?.employee_name !== emp;
              const blocks = schedule ? getContiguousShiftBlocks(schedule) : [];
              const unavailableRanges = getUnavailableRanges(emp, selectedDay, employeeAvailability);

              return (
                <DroppableColumn
                  key={emp}
                  employeeName={emp}
                  isEditMode={isEditMode}
                  isPastDate={isViewingPastDate}
                  height={HOUR_SLOTS.length * HOUR_HEIGHT}
                  isOver={isColumnOver}
                  isSelecting={isSelecting}
                  selectionStartY={selectionStartY}
                  selectionEndY={selectionEndY}
                  selectingEmployee={selectingEmployee}
                  onSelectionStart={handleSelectionStart}
                  onSelectionMove={handleSelectionMove}
                  onSelectionEnd={handleSelectionEnd}
                  unavailableRanges={unavailableRanges}
                >
                  {HOUR_SLOTS.map(({ hour }) => (
                    <div
                      key={hour}
                      className="absolute w-full border-b border-gray-50 pointer-events-none"
                      style={{ top: (hour - START_HOUR + 1) * HOUR_HEIGHT }}
                    />
                  ))}

                  {blocks.map((block) => {
                    const blockShift: EmployeeDaySchedule = {
                      ...schedule!,
                      shift_start: block.start_time,
                      shift_end: block.end_time,
                      total_hours: block.total_hours,
                      is_short_shift: block.is_short_shift,
                    };
                    return (
                      <DraggableShift
                        key={`${emp}-${block.start_time}`}
                        shift={blockShift}
                        color={color}
                        top={(parseTimeToHour(block.start_time) - START_HOUR) * HOUR_HEIGHT}
                        height={
                          (parseTimeToHour(block.end_time) -
                            parseTimeToHour(block.start_time)) *
                          HOUR_HEIGHT
                        }
                        disabled={!isEditMode}
                        onResizeStart={handleResizeStart}
                        onToggleLock={
                          onToggleLock
                            ? (shift) => shift.date && onToggleLock(shift.employee_name, shift.date)
                            : undefined
                        }
                        onClick={onShiftClick}
                        formatTime={formatTime}
                      />
                    );
                  })}
                </DroppableColumn>
              );
            })}

            {hasUnfilled && daySummary && (
              <div
                className="relative border-l border-red-200 bg-red-50/30"
                style={{ height: HOUR_SLOTS.length * HOUR_HEIGHT }}
              >
                {HOUR_SLOTS.map(({ hour }) => (
                  <div
                    key={hour}
                    className="absolute w-full border-b border-red-100"
                    style={{ top: (hour - START_HOUR + 1) * HOUR_HEIGHT }}
                  />
                ))}

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

        <DragOverlay>
          {activeShift && (
            <ShiftPreview
              shift={activeShift}
              color={employeeColorMap.get(activeShift.employee_name) || EMPLOYEE_COLORS[0]}
              height={
                (parseTimeToHour(activeShift.shift_end!) -
                  parseTimeToHour(activeShift.shift_start!)) *
                HOUR_HEIGHT
              }
              formatTime={formatTime}
            />
          )}
        </DragOverlay>
      </DndContext>

      <div className="flex items-center justify-end text-sm">
        <span className="text-gray-400">Weekly Total</span>
        <span className="ml-2 text-xl font-bold text-gray-900">
          ${totalCost.toLocaleString()}
        </span>
      </div>
    </div>
  );
}

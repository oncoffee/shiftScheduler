import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import type {
  WeeklyScheduleResult,
  EmployeeDaySchedule,
  DayScheduleSummary,
  ScheduleSnapshot,
  ShiftEditRequest,
} from "@/types/schedule";
import { api } from "@/api/client";

interface ScheduleEditContextValue {
  isEditMode: boolean;
  hasUnsavedChanges: boolean;
  isSaving: boolean;
  localSchedules: EmployeeDaySchedule[];
  localSummaries: DayScheduleSummary[];
  undoStack: ScheduleSnapshot[];
  scheduleId: string | null;
  originalSchedule: WeeklyScheduleResult | null;
  enterEditMode: () => void;
  exitEditMode: () => void;
  updateLocalShift: (
    employeeName: string,
    dayOfWeek: string,
    newStart: string,
    newEnd: string,
    originalStart: string,
    originalEnd: string,
    newEmployeeName?: string
  ) => void;
  saveChanges: () => Promise<void>;
  discardChanges: () => void;
  undo: () => void;
  canUndo: boolean;
  setScheduleData: (schedule: WeeklyScheduleResult, id: string) => void;
}

const ScheduleEditContext = createContext<ScheduleEditContextValue | null>(null);

const MAX_UNDO_STACK = 20;

interface ScheduleEditProviderProps {
  children: ReactNode;
}

export function ScheduleEditProvider({ children }: ScheduleEditProviderProps) {
  const [isEditMode, setIsEditMode] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [scheduleId, setScheduleId] = useState<string | null>(null);
  const [originalSchedule, setOriginalSchedule] = useState<WeeklyScheduleResult | null>(null);
  const [localSchedules, setLocalSchedules] = useState<EmployeeDaySchedule[]>([]);
  const [localSummaries, setLocalSummaries] = useState<DayScheduleSummary[]>([]);
  const [undoStack, setUndoStack] = useState<ScheduleSnapshot[]>([]);
  const [pendingChanges, setPendingChanges] = useState<ShiftEditRequest[]>([]);

  const hasUnsavedChanges = pendingChanges.length > 0;
  const canUndo = undoStack.length > 0;

  const setScheduleData = useCallback((schedule: WeeklyScheduleResult, id: string) => {
    setOriginalSchedule(schedule);
    setScheduleId(id);
    setLocalSchedules(structuredClone(schedule.schedules));
    setLocalSummaries(structuredClone(schedule.daily_summaries));
    setUndoStack([]);
    setPendingChanges([]);
  }, []);

  const saveSnapshot = useCallback(() => {
    setUndoStack((prev) => [
      ...prev.slice(-(MAX_UNDO_STACK - 1)),
      {
        schedules: structuredClone(localSchedules),
        daily_summaries: structuredClone(localSummaries),
        timestamp: Date.now(),
      },
    ]);
  }, [localSchedules, localSummaries]);

  const enterEditMode = useCallback(() => {
    setIsEditMode(true);
  }, []);

  const exitEditMode = useCallback(() => {
    setIsEditMode(false);
  }, []);

  const parseTimeToMinutes = (timeStr: string): number => {
    const parts = timeStr.split(":");
    return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
  };

  const clearShiftFromSchedule = (
    schedule: EmployeeDaySchedule,
    shiftStart: string,
    shiftEnd: string
  ): EmployeeDaySchedule => {
    const startMinutes = parseTimeToMinutes(shiftStart);
    const endMinutes = parseTimeToMinutes(shiftEnd);

    const updatedPeriods = schedule.periods.map((p) => {
      const periodStart = parseTimeToMinutes(p.start_time);
      const periodEnd = parseTimeToMinutes(p.end_time);
      const inRange = periodStart >= startMinutes && periodEnd <= endMinutes;
      return { ...p, scheduled: inRange ? false : p.scheduled };
    });

    const scheduledPeriods = updatedPeriods.filter((p) => p.scheduled);
    const totalHours = scheduledPeriods.length * 0.5;

    let newStart: string | null = null;
    let newEnd: string | null = null;
    if (scheduledPeriods.length > 0) {
      newStart = scheduledPeriods[0].start_time;
      newEnd = scheduledPeriods[scheduledPeriods.length - 1].end_time;
    }

    return {
      ...schedule,
      periods: updatedPeriods,
      total_hours: totalHours,
      shift_start: newStart,
      shift_end: newEnd,
      is_short_shift: totalHours > 0 && totalHours < 3,
    };
  };

  const addShiftToSchedule = (
    schedule: EmployeeDaySchedule,
    shiftStart: string,
    shiftEnd: string
  ): EmployeeDaySchedule => {
    const startMinutes = parseTimeToMinutes(shiftStart);
    const endMinutes = parseTimeToMinutes(shiftEnd);

    const updatedPeriods = schedule.periods.map((p) => {
      const periodStart = parseTimeToMinutes(p.start_time);
      const periodEnd = parseTimeToMinutes(p.end_time);
      const inRange = periodStart >= startMinutes && periodEnd <= endMinutes;
      return { ...p, scheduled: inRange ? true : p.scheduled };
    });

    const scheduledPeriods = updatedPeriods.filter((p) => p.scheduled);
    const totalHours = scheduledPeriods.length * 0.5;

    let newStart: string | null = null;
    let newEnd: string | null = null;
    if (scheduledPeriods.length > 0) {
      newStart = scheduledPeriods[0].start_time;
      newEnd = scheduledPeriods[scheduledPeriods.length - 1].end_time;
    }

    return {
      ...schedule,
      periods: updatedPeriods,
      total_hours: totalHours,
      shift_start: newStart,
      shift_end: newEnd,
      is_short_shift: totalHours > 0 && totalHours < 3,
    };
  };

  const updateLocalShift = useCallback(
    (
      employeeName: string,
      dayOfWeek: string,
      newStart: string,
      newEnd: string,
      originalStart: string,
      originalEnd: string,
      newEmployeeName?: string
    ) => {
      saveSnapshot();

      setLocalSchedules((prev) => {
        if (newEmployeeName && newEmployeeName !== employeeName) {
          return prev.map((schedule) => {
            if (schedule.employee_name === employeeName && schedule.day_of_week === dayOfWeek) {
              return clearShiftFromSchedule(schedule, originalStart, originalEnd);
            }
            if (schedule.employee_name === newEmployeeName && schedule.day_of_week === dayOfWeek) {
              return addShiftToSchedule(schedule, newStart, newEnd);
            }
            return schedule;
          });
        }

        return prev.map((schedule) => {
          if (schedule.employee_name === employeeName && schedule.day_of_week === dayOfWeek) {
            return addShiftToSchedule(
              clearShiftFromSchedule(schedule, originalStart, originalEnd),
              newStart,
              newEnd
            );
          }
          return schedule;
        });
      });

      setPendingChanges((prev) => [
        ...prev.filter(
          (c) =>
            !(c.employee_name === employeeName && c.day_of_week === dayOfWeek)
        ),
        {
          employee_name: employeeName,
          day_of_week: dayOfWeek,
          new_shift_start: newStart,
          new_shift_end: newEnd,
          new_employee_name: newEmployeeName,
        },
      ]);
    },
    [saveSnapshot]
  );

  const saveChanges = useCallback(async () => {
    if (!scheduleId || pendingChanges.length === 0) return;

    setIsSaving(true);
    try {
      const result = await api.batchUpdateAssignments(scheduleId, pendingChanges);

      if (result.success) {
        setOriginalSchedule(result.updated_schedule);
        setLocalSchedules(structuredClone(result.updated_schedule.schedules));
        setLocalSummaries(structuredClone(result.updated_schedule.daily_summaries));
        setPendingChanges([]);
        setUndoStack([]);
      } else if (result.failed_updates.length > 0) {
        console.error("Some updates failed:", result.failed_updates);
        setOriginalSchedule(result.updated_schedule);
        setLocalSchedules(structuredClone(result.updated_schedule.schedules));
        setLocalSummaries(structuredClone(result.updated_schedule.daily_summaries));
        const failedKeys = new Set(
          result.failed_updates.map(
            (f) => `${f.employee_name}-${f.day_of_week}`
          )
        );
        setPendingChanges((prev) =>
          prev.filter(
            (c) => failedKeys.has(`${c.employee_name}-${c.day_of_week}`)
          )
        );
      }
    } catch (error) {
      console.error("Failed to save changes:", error);
      throw error;
    } finally {
      setIsSaving(false);
    }
  }, [scheduleId, pendingChanges]);

  const discardChanges = useCallback(() => {
    if (originalSchedule) {
      setLocalSchedules(structuredClone(originalSchedule.schedules));
      setLocalSummaries(structuredClone(originalSchedule.daily_summaries));
    }
    setPendingChanges([]);
    setUndoStack([]);
  }, [originalSchedule]);

  const undo = useCallback(() => {
    if (undoStack.length === 0) return;

    const prev = undoStack[undoStack.length - 1];
    setLocalSchedules(prev.schedules);
    setLocalSummaries(prev.daily_summaries);
    setUndoStack((stack) => stack.slice(0, -1));

    setPendingChanges((prev) => prev.slice(0, -1));
  }, [undoStack]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "z" && isEditMode) {
        e.preventDefault();
        undo();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [undo, isEditMode]);

  const value: ScheduleEditContextValue = {
    isEditMode,
    hasUnsavedChanges,
    isSaving,
    localSchedules,
    localSummaries,
    undoStack,
    scheduleId,
    originalSchedule,
    enterEditMode,
    exitEditMode,
    updateLocalShift,
    saveChanges,
    discardChanges,
    undo,
    canUndo,
    setScheduleData,
  };

  return (
    <ScheduleEditContext.Provider value={value}>
      {children}
    </ScheduleEditContext.Provider>
  );
}

export function useScheduleEditContext() {
  const context = useContext(ScheduleEditContext);
  if (!context) {
    throw new Error(
      "useScheduleEditContext must be used within a ScheduleEditProvider"
    );
  }
  return context;
}

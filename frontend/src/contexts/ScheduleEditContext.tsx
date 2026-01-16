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

  const updateLocalShift = useCallback(
    (
      employeeName: string,
      dayOfWeek: string,
      newStart: string,
      newEnd: string,
      newEmployeeName?: string
    ) => {
      saveSnapshot();

      const startMinutes = parseTimeToMinutes(newStart);
      const endMinutes = parseTimeToMinutes(newEnd);

      setLocalSchedules((prev) => {
        const updated = prev.map((schedule) => {
          if (newEmployeeName && newEmployeeName !== employeeName) {
            if (
              schedule.employee_name === employeeName &&
              schedule.day_of_week === dayOfWeek
            ) {
              const clearedPeriods = schedule.periods.map((p) => ({
                ...p,
                scheduled: false,
              }));
              return {
                ...schedule,
                periods: clearedPeriods,
                total_hours: 0,
                shift_start: null,
                shift_end: null,
                is_short_shift: false,
              };
            }

            if (
              schedule.employee_name === newEmployeeName &&
              schedule.day_of_week === dayOfWeek
            ) {
              const updatedPeriods = schedule.periods.map((p) => {
                const periodStart = parseTimeToMinutes(p.start_time);
                const periodEnd = parseTimeToMinutes(p.end_time);
                const scheduled =
                  periodStart >= startMinutes && periodEnd <= endMinutes;
                return { ...p, scheduled };
              });

              const scheduledCount = updatedPeriods.filter(
                (p) => p.scheduled
              ).length;
              const totalHours = scheduledCount * 0.5;
              const isShortShift = totalHours > 0 && totalHours < 3;

              return {
                ...schedule,
                periods: updatedPeriods,
                total_hours: totalHours,
                shift_start: totalHours > 0 ? newStart : null,
                shift_end: totalHours > 0 ? newEnd : null,
                is_short_shift: isShortShift,
              };
            }

            return schedule;
          }

          if (
            schedule.employee_name === employeeName &&
            schedule.day_of_week === dayOfWeek
          ) {
            const updatedPeriods = schedule.periods.map((p) => {
              const periodStart = parseTimeToMinutes(p.start_time);
              const periodEnd = parseTimeToMinutes(p.end_time);
              const scheduled =
                periodStart >= startMinutes && periodEnd <= endMinutes;
              return { ...p, scheduled };
            });

            const scheduledCount = updatedPeriods.filter(
              (p) => p.scheduled
            ).length;
            const totalHours = scheduledCount * 0.5;
            const isShortShift = totalHours > 0 && totalHours < 3;

            return {
              ...schedule,
              periods: updatedPeriods,
              total_hours: totalHours,
              shift_start: totalHours > 0 ? newStart : null,
              shift_end: totalHours > 0 ? newEnd : null,
              is_short_shift: isShortShift,
            };
          }

          return schedule;
        });

        return updated;
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

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

type SaveStatus = "idle" | "saving" | "saved" | "error";

interface ScheduleEditContextValue {
  hasUnsavedChanges: boolean;
  isSaving: boolean;
  saveStatus: SaveStatus;
  localSchedules: EmployeeDaySchedule[];
  localSummaries: DayScheduleSummary[];
  undoStack: ScheduleSnapshot[];
  scheduleId: string | null;
  originalSchedule: WeeklyScheduleResult | null;
  updateLocalShift: (
    employeeName: string,
    dayOfWeek: string,
    newStart: string,
    newEnd: string,
    originalStart: string,
    originalEnd: string,
    newEmployeeName?: string,
    date?: string | null
  ) => void;
  addNewShift: (
    employeeName: string,
    dayOfWeek: string,
    startTime: string,
    endTime: string
  ) => void;
  undo: () => void;
  canUndo: boolean;
  setScheduleData: (schedule: WeeklyScheduleResult, id: string) => void;
  toggleShiftLock: (employeeName: string, date: string) => Promise<void>;
  deleteShift: (employeeName: string, dayOfWeek: string) => Promise<void>;
  selectedShift: EmployeeDaySchedule | null;
  setSelectedShift: (shift: EmployeeDaySchedule | null) => void;
}

const ScheduleEditContext = createContext<ScheduleEditContextValue | null>(null);

const MAX_UNDO_STACK = 20;

interface ScheduleEditProviderProps {
  children: ReactNode;
}

const AUTO_SAVE_DELAY = 500; // ms debounce for auto-save

export function ScheduleEditProvider({ children }: ScheduleEditProviderProps) {
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [scheduleId, setScheduleId] = useState<string | null>(null);
  const [originalSchedule, setOriginalSchedule] = useState<WeeklyScheduleResult | null>(null);
  const [localSchedules, setLocalSchedules] = useState<EmployeeDaySchedule[]>([]);
  const [localSummaries, setLocalSummaries] = useState<DayScheduleSummary[]>([]);
  const [undoStack, setUndoStack] = useState<ScheduleSnapshot[]>([]);
  const [pendingChanges, setPendingChanges] = useState<ShiftEditRequest[]>([]);
  const [selectedShift, setSelectedShift] = useState<EmployeeDaySchedule | null>(null);

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
      newEmployeeName?: string,
      date?: string | null
    ) => {
      saveSnapshot();

      const matchesTarget = (schedule: EmployeeDaySchedule, targetEmployee: string) => {
        if (schedule.employee_name !== targetEmployee) return false;
        if (date && schedule.date) {
          return schedule.date === date;
        }
        return schedule.day_of_week === dayOfWeek;
      };

      setLocalSchedules((prev) => {
        if (newEmployeeName && newEmployeeName !== employeeName) {
          return prev.map((schedule) => {
            if (matchesTarget(schedule, employeeName)) {
              return clearShiftFromSchedule(schedule, originalStart, originalEnd);
            }
            if (matchesTarget(schedule, newEmployeeName)) {
              return addShiftToSchedule(schedule, newStart, newEnd);
            }
            return schedule;
          });
        }

        return prev.map((schedule) => {
          if (matchesTarget(schedule, employeeName)) {
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
            !(c.employee_name === employeeName && c.day_of_week === dayOfWeek && c.date === date)
        ),
        {
          employee_name: employeeName,
          day_of_week: dayOfWeek,
          date: date,
          new_shift_start: newStart,
          new_shift_end: newEnd,
          new_employee_name: newEmployeeName,
        },
      ]);
    },
    [saveSnapshot]
  );

  const addNewShift = useCallback(
    (employeeName: string, dayOfWeek: string, startTime: string, endTime: string) => {
      saveSnapshot();

      setLocalSchedules((prev) =>
        prev.map((schedule) => {
          if (schedule.employee_name === employeeName && schedule.day_of_week === dayOfWeek) {
            return addShiftToSchedule(schedule, startTime, endTime);
          }
          return schedule;
        })
      );

      setPendingChanges((prev) => [
        ...prev,
        {
          employee_name: employeeName,
          day_of_week: dayOfWeek,
          new_shift_start: startTime,
          new_shift_end: endTime,
        },
      ]);
    },
    [saveSnapshot]
  );

  const saveChanges = useCallback(async () => {
    if (!scheduleId || pendingChanges.length === 0) return;

    const lockedShifts = localSchedules
      .filter((s) => s.is_locked && s.total_hours > 0)
      .map((s) => ({ employee_name: s.employee_name, day_of_week: s.day_of_week }));

    setIsSaving(true);
    try {
      const result = await api.batchUpdateAssignments(scheduleId, pendingChanges);

      if (result.success) {
        let finalSchedules = structuredClone(result.updated_schedule.schedules);

        for (const locked of lockedShifts) {
          const pendingChange = pendingChanges.find(
            (c) => c.employee_name === locked.employee_name && c.day_of_week === locked.day_of_week
          );
          const targetEmployee = pendingChange?.new_employee_name || locked.employee_name;

          const serverSchedule = finalSchedules.find(
            (s) => s.employee_name === targetEmployee && s.day_of_week === locked.day_of_week
          );

          if (serverSchedule && serverSchedule.total_hours > 0 && !serverSchedule.is_locked) {
            try {
              const lockResult = await api.toggleShiftLock(
                scheduleId,
                targetEmployee,
                locked.day_of_week,
                true
              );
              if (lockResult.success) {
                finalSchedules = structuredClone(lockResult.updated_schedule.schedules);
              }
            } catch (e) {
              console.error("Failed to persist lock state:", e);
            }
          }
        }

        setOriginalSchedule({ ...result.updated_schedule, schedules: finalSchedules });
        setLocalSchedules(finalSchedules);
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
  }, [scheduleId, pendingChanges, localSchedules]);

  const undo = useCallback(() => {
    if (undoStack.length === 0) return;

    const prev = undoStack[undoStack.length - 1];
    setLocalSchedules(prev.schedules);
    setLocalSummaries(prev.daily_summaries);
    setUndoStack((stack) => stack.slice(0, -1));

    setPendingChanges((prev) => prev.slice(0, -1));
  }, [undoStack]);

  const toggleShiftLock = useCallback(
    async (employeeName: string, date: string) => {
      if (!scheduleId) return;

      const schedule = localSchedules.find(
        (s) => s.employee_name === employeeName && s.date === date
      );
      if (!schedule) return;

      if (schedule.total_hours === 0) return;

      const currentlyLocked = schedule.is_locked ?? false;
      const newLockState = !currentlyLocked;

      setLocalSchedules((prev) =>
        prev.map((s) =>
          s.employee_name === employeeName && s.date === date
            ? { ...s, is_locked: newLockState }
            : s
        )
      );

      if (pendingChanges.length > 0) {
        return;
      }

      try {
        const result = await api.toggleShiftLock(
          scheduleId,
          employeeName,
          date,
          newLockState
        );

        if (result.success) {
          setOriginalSchedule(result.updated_schedule);

          setLocalSchedules((prev) =>
            prev.map((s) => {
              if (s.employee_name === employeeName && s.date === date) {
                const serverSchedule = result.updated_schedule.schedules.find(
                  (ss) => ss.employee_name === employeeName && ss.date === date
                );
                return { ...s, is_locked: serverSchedule?.is_locked ?? newLockState };
              }
              return s;
            })
          );
        }
      } catch (error) {
        console.error("Failed to toggle lock:", error);
        setLocalSchedules((prev) =>
          prev.map((s) =>
            s.employee_name === employeeName && s.date === date
              ? { ...s, is_locked: currentlyLocked }
              : s
          )
        );
      }
    },
    [scheduleId, localSchedules, pendingChanges.length]
  );

  const deleteShift = useCallback(
    async (employeeName: string, dayOfWeek: string) => {
      if (!scheduleId) return;

      const schedule = localSchedules.find(
        (s) => s.employee_name === employeeName && s.day_of_week === dayOfWeek
      );
      if (!schedule || schedule.total_hours === 0) return;

      if (schedule.is_locked) {
        console.error("Cannot delete a locked shift");
        return;
      }

      saveSnapshot();

      setLocalSchedules((prev) =>
        prev.map((s) =>
          s.employee_name === employeeName && s.day_of_week === dayOfWeek
            ? {
                ...s,
                total_hours: 0,
                shift_start: null,
                shift_end: null,
                is_short_shift: false,
                periods: s.periods.map((p) => ({ ...p, scheduled: false })),
              }
            : s
        )
      );

      if (pendingChanges.length > 0) {
        setPendingChanges((prev) => [
          ...prev.filter(
            (c) => !(c.employee_name === employeeName && c.day_of_week === dayOfWeek)
          ),
          {
            employee_name: employeeName,
            day_of_week: dayOfWeek,
            new_shift_start: "00:00",
            new_shift_end: "00:00",
          },
        ]);
        return;
      }

      try {
        const result = await api.deleteShift(scheduleId, employeeName, dayOfWeek);

        if (result.success) {
          setOriginalSchedule(result.updated_schedule);
          setLocalSchedules(structuredClone(result.updated_schedule.schedules));
          setLocalSummaries(structuredClone(result.updated_schedule.daily_summaries));
        }
      } catch (error) {
        console.error("Failed to delete shift:", error);
        if (originalSchedule) {
          setLocalSchedules(structuredClone(originalSchedule.schedules));
        }
      }
    },
    [scheduleId, localSchedules, pendingChanges.length, saveSnapshot, originalSchedule]
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "z") {
        e.preventDefault();
        undo();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [undo]);

  useEffect(() => {
    if (!scheduleId || pendingChanges.length === 0 || isSaving) return;

    setSaveStatus("saving");
    const timer = setTimeout(async () => {
      try {
        await saveChanges();
        setSaveStatus("saved");
        setTimeout(() => setSaveStatus("idle"), 1500);
      } catch {
        setSaveStatus("error");
        setTimeout(() => setSaveStatus("idle"), 3000);
      }
    }, AUTO_SAVE_DELAY);

    return () => clearTimeout(timer);
  }, [pendingChanges, scheduleId, isSaving, saveChanges]);

  const value: ScheduleEditContextValue = {
    hasUnsavedChanges,
    isSaving,
    saveStatus,
    localSchedules,
    localSummaries,
    undoStack,
    scheduleId,
    originalSchedule,
    updateLocalShift,
    addNewShift,
    undo,
    canUndo,
    setScheduleData,
    toggleShiftLock,
    deleteShift,
    selectedShift,
    setSelectedShift,
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

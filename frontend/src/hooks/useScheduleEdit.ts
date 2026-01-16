import { useState, useCallback } from "react";
import { api } from "@/api/client";
import type {
  EmployeeDaySchedule,
  ValidateChangeResponse,
} from "@/types/schedule";

const SLOT_HEIGHT = 60;
const START_HOUR = 6;

export function useScheduleEdit() {
  const [validationResult, setValidationResult] =
    useState<ValidateChangeResponse | null>(null);
  const [isValidating, setIsValidating] = useState(false);

  const parseTimeToMinutes = (timeStr: string): number => {
    const parts = timeStr.split(":");
    return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
  };

  const parseTimeToHour = (timeStr: string): number => {
    const parts = timeStr.split(":");
    return parseInt(parts[0], 10) + parseInt(parts[1], 10) / 60;
  };

  const minutesToTime = (minutes: number): string => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours.toString().padStart(2, "0")}:${mins
      .toString()
      .padStart(2, "0")}`;
  };

  const snapToTime = useCallback((pixelY: number): string => {
    const hourOffset = pixelY / SLOT_HEIGHT;
    const totalMinutes = (START_HOUR + hourOffset) * 60;
    const snappedMinutes = Math.round(totalMinutes / 30) * 30;
    return minutesToTime(snappedMinutes);
  }, []);

  const timeToPixelY = useCallback((timeStr: string): number => {
    const hour = parseTimeToHour(timeStr);
    return (hour - START_HOUR) * SLOT_HEIGHT;
  }, []);

  const calculateNewTimes = useCallback(
    (
      shift: EmployeeDaySchedule,
      deltaY: number,
      resizeType: "move" | "resize-start" | "resize-end"
    ): { newStart: string; newEnd: string } => {
      if (!shift.shift_start || !shift.shift_end) {
        return { newStart: "09:00", newEnd: "17:00" };
      }

      const currentStartY = timeToPixelY(shift.shift_start);
      const currentEndY = timeToPixelY(shift.shift_end);

      let newStartY = currentStartY;
      let newEndY = currentEndY;

      if (resizeType === "move") {
        newStartY = currentStartY + deltaY;
        newEndY = currentEndY + deltaY;
      } else if (resizeType === "resize-start") {
        newStartY = currentStartY + deltaY;
      } else if (resizeType === "resize-end") {
        newEndY = currentEndY + deltaY;
      }

      const maxY = 16 * SLOT_HEIGHT;
      newStartY = Math.max(0, Math.min(newStartY, maxY - SLOT_HEIGHT / 2));
      newEndY = Math.max(SLOT_HEIGHT / 2, Math.min(newEndY, maxY));

      if (newStartY >= newEndY - SLOT_HEIGHT / 2) {
        if (resizeType === "resize-start") {
          newStartY = newEndY - SLOT_HEIGHT / 2;
        } else {
          newEndY = newStartY + SLOT_HEIGHT / 2;
        }
      }

      const newStart = snapToTime(newStartY);
      const newEnd = snapToTime(newEndY);

      return { newStart, newEnd };
    },
    [timeToPixelY, snapToTime]
  );

  const validateChange = useCallback(
    async (
      scheduleId: string,
      employeeName: string,
      dayOfWeek: string,
      proposedStart: string,
      proposedEnd: string
    ): Promise<ValidateChangeResponse> => {
      setIsValidating(true);
      try {
        const result = await api.validateChange(scheduleId, {
          employee_name: employeeName,
          day_of_week: dayOfWeek,
          proposed_start: proposedStart,
          proposed_end: proposedEnd,
        });
        setValidationResult(result);
        return result;
      } catch (error) {
        const errorResult: ValidateChangeResponse = {
          is_valid: false,
          errors: [
            {
              code: "VALIDATION_ERROR",
              message:
                error instanceof Error
                  ? error.message
                  : "Failed to validate change",
            },
          ],
          warnings: [],
        };
        setValidationResult(errorResult);
        return errorResult;
      } finally {
        setIsValidating(false);
      }
    },
    []
  );

  const clearValidation = useCallback(() => {
    setValidationResult(null);
  }, []);

  const isValidDrop = useCallback(
    (
      _schedules: EmployeeDaySchedule[],
      _employeeName: string,
      _dayOfWeek: string,
      proposedStart: string,
      proposedEnd: string
    ): { valid: boolean; reason?: string } => {
      const startMinutes = parseTimeToMinutes(proposedStart);
      const endMinutes = parseTimeToMinutes(proposedEnd);

      if (startMinutes >= endMinutes) {
        return { valid: false, reason: "Start time must be before end time" };
      }

      const shiftHours = (endMinutes - startMinutes) / 60;
      if (shiftHours < 0.5) {
        return { valid: false, reason: "Shift must be at least 30 minutes" };
      }

      if (shiftHours > 11) {
        return { valid: false, reason: "Shift exceeds maximum 11 hours" };
      }

      if (startMinutes < 6 * 60 || endMinutes > 22 * 60) {
        return {
          valid: false,
          reason: "Shift must be within store hours (6 AM - 10 PM)",
        };
      }

      return { valid: true };
    },
    []
  );

  return {
    validationResult,
    isValidating,
    validateChange,
    clearValidation,
    isValidDrop,
    calculateNewTimes,
    snapToTime,
    timeToPixelY,
    SLOT_HEIGHT,
    START_HOUR,
  };
}

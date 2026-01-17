import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { AlertTriangle, GripVertical, Lock, LockOpen, Coffee } from "lucide-react";
import type { EmployeeDaySchedule } from "@/types/schedule";

// Helper to get break periods info from shift
function getBreakInfo(shift: EmployeeDaySchedule): { hasBreak: boolean; breakTime: string | null } {
  const breakPeriods = shift.periods?.filter(p => p.is_break) ?? [];
  if (breakPeriods.length === 0) {
    return { hasBreak: false, breakTime: null };
  }
  // Get the first break period's time
  const firstBreak = breakPeriods[0];
  return {
    hasBreak: true,
    breakTime: `${firstBreak.start_time} - ${firstBreak.end_time}`,
  };
}

interface DraggableShiftProps {
  shift: EmployeeDaySchedule;
  color: string;
  top: number;
  height: number;
  disabled: boolean;
  onResizeStart?: (
    shift: EmployeeDaySchedule,
    type: "resize-start" | "resize-end"
  ) => void;
  onToggleLock?: (shift: EmployeeDaySchedule) => void;
  onClick?: (shift: EmployeeDaySchedule) => void;
  formatTime: (timeStr: string) => string;
}

export function DraggableShift({
  shift,
  color,
  top,
  height,
  disabled,
  onResizeStart,
  onToggleLock,
  onClick,
  formatTime,
}: DraggableShiftProps) {
  const isLocked = shift.is_locked ?? false;
  const effectivelyDisabled = disabled || isLocked;
  const { hasBreak, breakTime } = getBreakInfo(shift);

  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: `shift-${shift.employee_name}-${shift.day_of_week}-${shift.shift_start}`,
      data: {
        type: "shift",
        shift,
        employeeName: shift.employee_name,
        dayOfWeek: shift.day_of_week,
        shiftStart: shift.shift_start,
        shiftEnd: shift.shift_end,
      },
      disabled: effectivelyDisabled,
    });

  const getBackgroundColor = () => {
    if (isLocked) return "#E5E7EB";
    if (shift.is_short_shift) return "#FED7AA";
    return color;
  };

  const style = {
    top: top + 2,
    height: height - 4,
    backgroundColor: getBackgroundColor(),
    transform: CSS.Translate.toString(transform),
    zIndex: isDragging ? 50 : 1,
    opacity: isDragging ? 0.8 : 1,
    cursor: effectivelyDisabled ? "default" : "grab",
    border: isLocked ? "2px solid #6B7280" : undefined,
  };

  const handleLockClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onToggleLock) {
      onToggleLock(shift);
    }
  };

  const handleClick = () => {
    if (!isDragging && onClick) {
      onClick(shift);
    }
  };

  const handleResizeMouseDown =
    (type: "resize-start" | "resize-end") =>
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!effectivelyDisabled && onResizeStart) {
        onResizeStart(shift, type);
      }
    };

  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...(effectivelyDisabled ? {} : listeners)}
      onClick={handleClick}
      data-shift-block="true"
      className={`absolute left-2 right-2 rounded-lg px-3 py-2 transition-shadow select-none ${
        shift.is_short_shift && !isLocked ? "border-2 border-dashed border-orange-400" : ""
      } ${isDragging ? "shadow-xl ring-2 ring-blue-500" : ""} ${
        !effectivelyDisabled ? "hover:shadow-lg" : ""
      } ${onClick ? "cursor-pointer" : ""}`}
      style={style}
    >
      {!disabled && !isLocked && (
        <div
          className="absolute top-0 left-0 right-0 h-3 cursor-ns-resize flex items-center justify-center group"
          onMouseDown={handleResizeMouseDown("resize-start")}
        >
          <div className="w-8 h-1 rounded bg-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      )}

      {!disabled && onToggleLock && (
        <button
          onClick={handleLockClick}
          className={`absolute top-1 right-1 p-1 rounded transition-colors ${
            isLocked
              ? "bg-gray-600 text-white hover:bg-gray-700"
              : "bg-white/50 text-gray-400 hover:bg-white/80 hover:text-gray-600"
          }`}
          title={isLocked ? "Unlock shift" : "Lock shift"}
        >
          {isLocked ? (
            <Lock className="w-3 h-3" />
          ) : (
            <LockOpen className="w-3 h-3" />
          )}
        </button>
      )}

      <div className="flex items-center gap-1">
        {!effectivelyDisabled && (
          <GripVertical className="w-3 h-3 text-gray-500 flex-shrink-0" />
        )}
        {isLocked && (
          <Lock className="w-3 h-3 text-gray-600 flex-shrink-0" />
        )}
        <span className={`text-sm font-semibold truncate ${isLocked ? "text-gray-600" : "text-gray-800"}`}>
          {shift.employee_name}
        </span>
        {shift.is_short_shift && !isLocked && (
          <AlertTriangle className="w-3 h-3 text-orange-500 flex-shrink-0" />
        )}
      </div>
      <div className={`text-xs mt-0.5 ${isLocked ? "text-gray-500" : "text-gray-600"}`}>
        {formatTime(shift.shift_start!)} - {formatTime(shift.shift_end!)}
      </div>
      <div className={`text-xs mt-1 ${isLocked ? "text-gray-400" : "text-gray-500"}`}>
        {shift.total_hours}h
        {shift.is_short_shift && !isLocked && (
          <span className="text-orange-500 ml-1">(short)</span>
        )}
        {isLocked && (
          <span className="text-gray-500 ml-1">(locked)</span>
        )}
      </div>
      {hasBreak && (
        <div className="flex items-center gap-1 mt-1 px-1.5 py-0.5 bg-amber-100 rounded text-xs text-amber-700">
          <Coffee className="w-3 h-3" />
          <span>Break {breakTime}</span>
        </div>
      )}

      {!disabled && !isLocked && (
        <div
          className="absolute bottom-0 left-0 right-0 h-3 cursor-ns-resize flex items-center justify-center group"
          onMouseDown={handleResizeMouseDown("resize-end")}
        >
          <div className="w-8 h-1 rounded bg-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      )}
    </div>
  );
}

interface ShiftPreviewProps {
  shift: EmployeeDaySchedule;
  color: string;
  height: number;
  formatTime: (timeStr: string) => string;
}

export function ShiftPreview({
  shift,
  color,
  height,
  formatTime,
}: ShiftPreviewProps) {
  const { hasBreak } = getBreakInfo(shift);

  return (
    <div
      className={`rounded-lg px-3 py-2 shadow-xl ring-2 ring-blue-500 ${
        shift.is_short_shift ? "border-2 border-dashed border-orange-400" : ""
      }`}
      style={{
        height: height - 4,
        backgroundColor: shift.is_short_shift ? "#FED7AA" : color,
        width: 140,
        opacity: 0.9,
      }}
    >
      <div className="flex items-center gap-1">
        <GripVertical className="w-3 h-3 text-gray-500 flex-shrink-0" />
        <span className="text-sm font-semibold text-gray-800 truncate">
          {shift.employee_name}
        </span>
        {shift.is_short_shift && (
          <AlertTriangle className="w-3 h-3 text-orange-500 flex-shrink-0" />
        )}
        {hasBreak && (
          <Coffee className="w-3 h-3 text-amber-600 flex-shrink-0" />
        )}
      </div>
      <div className="text-xs text-gray-600 mt-0.5">
        {formatTime(shift.shift_start!)} - {formatTime(shift.shift_end!)}
      </div>
      <div className="text-xs text-gray-500 mt-1">
        {shift.total_hours}h
        {shift.is_short_shift && (
          <span className="text-orange-500 ml-1">(short)</span>
        )}
      </div>
    </div>
  );
}

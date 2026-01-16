import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { AlertTriangle, GripVertical } from "lucide-react";
import type { EmployeeDaySchedule } from "@/types/schedule";

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
  formatTime: (timeStr: string) => string;
}

export function DraggableShift({
  shift,
  color,
  top,
  height,
  disabled,
  onResizeStart,
  formatTime,
}: DraggableShiftProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: `shift-${shift.employee_name}-${shift.day_of_week}`,
      data: {
        type: "shift",
        shift,
        employeeName: shift.employee_name,
        dayOfWeek: shift.day_of_week,
      },
      disabled,
    });

  const style = {
    top: top + 2,
    height: height - 4,
    backgroundColor: shift.is_short_shift ? "#FED7AA" : color,
    transform: CSS.Translate.toString(transform),
    zIndex: isDragging ? 50 : 1,
    opacity: isDragging ? 0.8 : 1,
    cursor: disabled ? "default" : "grab",
  };

  const handleResizeMouseDown =
    (type: "resize-start" | "resize-end") =>
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!disabled && onResizeStart) {
        onResizeStart(shift, type);
      }
    };

  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...(disabled ? {} : listeners)}
      className={`absolute left-2 right-2 rounded-lg px-3 py-2 transition-shadow select-none ${
        shift.is_short_shift ? "border-2 border-dashed border-orange-400" : ""
      } ${isDragging ? "shadow-xl ring-2 ring-blue-500" : ""} ${
        !disabled ? "hover:shadow-lg" : ""
      }`}
      style={style}
    >
      {!disabled && (
        <div
          className="absolute top-0 left-0 right-0 h-3 cursor-ns-resize flex items-center justify-center group"
          onMouseDown={handleResizeMouseDown("resize-start")}
        >
          <div className="w-8 h-1 rounded bg-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      )}

      <div className="flex items-center gap-1">
        {!disabled && (
          <GripVertical className="w-3 h-3 text-gray-500 flex-shrink-0" />
        )}
        <span className="text-sm font-semibold text-gray-800 truncate">
          {shift.employee_name}
        </span>
        {shift.is_short_shift && (
          <AlertTriangle className="w-3 h-3 text-orange-500 flex-shrink-0" />
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

      {!disabled && (
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

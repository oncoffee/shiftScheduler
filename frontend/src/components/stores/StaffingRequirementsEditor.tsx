import { useState, useCallback, useRef, useEffect } from "react";
import { Plus, Minus, X } from "lucide-react";
import type { StaffingRequirement } from "@/api/client";

interface StaffingRequirementsEditorProps {
  requirements: StaffingRequirement[];
  onChange: (requirements: StaffingRequirement[]) => void;
  disabled?: boolean;
}

const MIN_HOUR = 6;
const MAX_HOUR = 24;
const TOTAL_MINUTES = (MAX_HOUR - MIN_HOUR) * 60;

const COLORS = [
  { bg: "bg-blue-400", border: "border-blue-500", text: "text-blue-700" },
  { bg: "bg-green-400", border: "border-green-500", text: "text-green-700" },
  { bg: "bg-purple-400", border: "border-purple-500", text: "text-purple-700" },
  { bg: "bg-orange-400", border: "border-orange-500", text: "text-orange-700" },
  { bg: "bg-pink-400", border: "border-pink-500", text: "text-pink-700" },
];

function timeToMinutes(time: string): number {
  const [hours, minutes] = time.split(":").map(Number);
  return hours * 60 + minutes;
}

function minutesToTime(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
}

function formatTime(time: string): string {
  const [hours] = time.split(":").map(Number);
  const h = hours === 24 ? 0 : hours;
  const suffix = h >= 12 ? "p" : "a";
  const displayHour = h > 12 ? h - 12 : h === 0 ? 12 : h;
  return `${displayHour}${suffix}`;
}

function snapToHalfHour(minutes: number): number {
  return Math.round(minutes / 30) * 30;
}

interface StaffingBlockProps {
  requirement: StaffingRequirement;
  index: number;
  containerWidth: number;
  onUpdate: (index: number, req: StaffingRequirement) => void;
  onDelete: (index: number) => void;
  disabled?: boolean;
}

function StaffingBlock({
  requirement,
  index,
  containerWidth,
  onUpdate,
  onDelete,
  disabled,
}: StaffingBlockProps) {
  const [dragging, setDragging] = useState<"start" | "end" | "move" | null>(null);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(requirement.min_staff.toString());
  const dragStartX = useRef(0);
  const dragStartValues = useRef({ start: 0, end: 0 });
  const inputRef = useRef<HTMLInputElement>(null);

  const startMinutes = timeToMinutes(requirement.start_time);
  const endMinutes = timeToMinutes(requirement.end_time);

  const left = ((startMinutes - MIN_HOUR * 60) / TOTAL_MINUTES) * containerWidth;
  const width = ((endMinutes - startMinutes) / TOTAL_MINUTES) * containerWidth;
  const color = COLORS[index % COLORS.length];

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent, type: "start" | "end" | "move") => {
      if (disabled) return;
      e.preventDefault();
      e.stopPropagation();
      setDragging(type);
      dragStartX.current = e.clientX;
      dragStartValues.current = { start: startMinutes, end: endMinutes };
    },
    [disabled, startMinutes, endMinutes]
  );

  useEffect(() => {
    if (!dragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const deltaX = e.clientX - dragStartX.current;
      const deltaMinutes = (deltaX / containerWidth) * TOTAL_MINUTES;

      if (dragging === "start") {
        const newStart = snapToHalfHour(dragStartValues.current.start + deltaMinutes);
        const clampedStart = Math.max(MIN_HOUR * 60, Math.min(endMinutes - 30, newStart));
        onUpdate(index, { ...requirement, start_time: minutesToTime(clampedStart) });
      } else if (dragging === "end") {
        const newEnd = snapToHalfHour(dragStartValues.current.end + deltaMinutes);
        const clampedEnd = Math.min(MAX_HOUR * 60, Math.max(startMinutes + 30, newEnd));
        onUpdate(index, { ...requirement, end_time: minutesToTime(clampedEnd) });
      } else if (dragging === "move") {
        const duration = dragStartValues.current.end - dragStartValues.current.start;
        let newStart = snapToHalfHour(dragStartValues.current.start + deltaMinutes);
        let newEnd = newStart + duration;

        if (newStart < MIN_HOUR * 60) {
          newStart = MIN_HOUR * 60;
          newEnd = newStart + duration;
        }
        if (newEnd > MAX_HOUR * 60) {
          newEnd = MAX_HOUR * 60;
          newStart = newEnd - duration;
        }

        onUpdate(index, {
          ...requirement,
          start_time: minutesToTime(newStart),
          end_time: minutesToTime(newEnd),
        });
      }
    };

    const handleMouseUp = () => setDragging(null);

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [dragging, containerWidth, index, requirement, startMinutes, endMinutes, onUpdate]);

  const handleNumberClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (disabled) return;
    setEditValue(requirement.min_staff.toString());
    setEditing(true);
  };

  const handleNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEditValue(e.target.value);
  };

  const handleNumberBlur = () => {
    setEditing(false);
    const num = parseInt(editValue);
    if (!isNaN(num) && num >= 1 && num <= 20) {
      onUpdate(index, { ...requirement, min_staff: num });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleNumberBlur();
    } else if (e.key === "Escape") {
      setEditing(false);
    }
  };

  const handleIncrement = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (disabled || requirement.min_staff >= 20) return;
    onUpdate(index, { ...requirement, min_staff: requirement.min_staff + 1 });
  };

  const handleDecrement = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (disabled || requirement.min_staff <= 1) return;
    onUpdate(index, { ...requirement, min_staff: requirement.min_staff - 1 });
  };

  return (
    <div
      className={`absolute top-0 bottom-0 ${color.bg} ${color.border} border-2 rounded-md flex items-center justify-center cursor-grab active:cursor-grabbing transition-colors ${
        dragging ? "opacity-80" : "hover:opacity-90"
      }`}
      style={{ left, width: Math.max(width, 20) }}
      onMouseDown={(e) => handleMouseDown(e, "move")}
    >
      <div
        className="absolute left-0 top-0 bottom-0 w-2 cursor-ew-resize hover:bg-white/30"
        onMouseDown={(e) => handleMouseDown(e, "start")}
      />

      <div className="flex flex-col items-center select-none pointer-events-none">
        {editing ? (
          <input
            ref={inputRef}
            type="number"
            min="1"
            max="20"
            value={editValue}
            onChange={handleNumberChange}
            onBlur={handleNumberBlur}
            onKeyDown={handleKeyDown}
            className="w-8 h-6 text-center text-sm font-bold bg-white rounded pointer-events-auto"
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <div className="flex items-center gap-1 pointer-events-auto">
            {!disabled && (
              <button
                onClick={handleDecrement}
                className="w-5 h-5 rounded-full bg-white/30 hover:bg-white/50 flex items-center justify-center transition-colors"
                disabled={requirement.min_staff <= 1}
              >
                <Minus className="w-3 h-3 text-white" />
              </button>
            )}
            <span
              className="text-lg font-bold text-white drop-shadow cursor-text min-w-[1.5rem] text-center"
              onClick={handleNumberClick}
            >
              {requirement.min_staff}
            </span>
            {!disabled && (
              <button
                onClick={handleIncrement}
                className="w-5 h-5 rounded-full bg-white/30 hover:bg-white/50 flex items-center justify-center transition-colors"
                disabled={requirement.min_staff >= 20}
              >
                <Plus className="w-3 h-3 text-white" />
              </button>
            )}
          </div>
        )}
        {width > 50 && (
          <span className="text-[10px] text-white/80">
            {formatTime(requirement.start_time)}-{formatTime(requirement.end_time)}
          </span>
        )}
      </div>

      {!disabled && (
        <button
          className="absolute -top-2 -right-2 w-4 h-4 bg-red-500 rounded-full flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity pointer-events-auto"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(index);
          }}
        >
          <X className="w-3 h-3 text-white" />
        </button>
      )}

      <div
        className="absolute right-0 top-0 bottom-0 w-2 cursor-ew-resize hover:bg-white/30"
        onMouseDown={(e) => handleMouseDown(e, "end")}
      />
    </div>
  );
}

export function StaffingRequirementsEditor({
  requirements,
  onChange,
  disabled = false,
}: StaffingRequirementsEditorProps) {
  const [dayType, setDayType] = useState<"weekday" | "weekend">("weekday");
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);

  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.offsetWidth);
      }
    };
    updateWidth();
    window.addEventListener("resize", updateWidth);
    return () => window.removeEventListener("resize", updateWidth);
  }, []);

  const filteredRequirements = requirements.filter((r) => r.day_type === dayType);

  const handleUpdate = useCallback(
    (index: number, updated: StaffingRequirement) => {
      const filtered = requirements.filter((r) => r.day_type === dayType);
      const others = requirements.filter((r) => r.day_type !== dayType);
      filtered[index] = updated;
      onChange([...others, ...filtered]);
    },
    [requirements, dayType, onChange]
  );

  const handleDelete = useCallback(
    (index: number) => {
      const filtered = requirements.filter((r) => r.day_type === dayType);
      const others = requirements.filter((r) => r.day_type !== dayType);
      filtered.splice(index, 1);
      onChange([...others, ...filtered]);
    },
    [requirements, dayType, onChange]
  );

  const handleAdd = useCallback(() => {
    if (disabled) return;

    const filtered = requirements.filter((r) => r.day_type === dayType);
    const sortedBlocks = [...filtered].sort(
      (a, b) => timeToMinutes(a.start_time) - timeToMinutes(b.start_time)
    );

    let newStart = MIN_HOUR * 60;
    let newEnd = newStart + 120;

    for (let i = 0; i <= sortedBlocks.length; i++) {
      const gapStart = i === 0 ? MIN_HOUR * 60 : timeToMinutes(sortedBlocks[i - 1].end_time);
      const gapEnd = i === sortedBlocks.length ? MAX_HOUR * 60 : timeToMinutes(sortedBlocks[i].start_time);

      if (gapEnd - gapStart >= 60) {
        newStart = gapStart;
        newEnd = Math.min(gapStart + 120, gapEnd);
        break;
      }
    }

    newStart = snapToHalfHour(newStart);
    newEnd = snapToHalfHour(newEnd);

    onChange([
      ...requirements,
      {
        day_type: dayType,
        start_time: minutesToTime(newStart),
        end_time: minutesToTime(newEnd),
        min_staff: 2,
      },
    ]);
  }, [disabled, requirements, dayType, onChange]);

  const hourLabels = [];
  for (let h = MIN_HOUR; h <= MAX_HOUR; h += 3) {
    hourLabels.push(h);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">Staffing Requirements</span>
        <div className="flex gap-1">
          <button
            className={`px-3 py-1 text-xs rounded-l-md transition-colors ${
              dayType === "weekday"
                ? "bg-blue-500 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
            onClick={() => setDayType("weekday")}
          >
            Weekday
          </button>
          <button
            className={`px-3 py-1 text-xs rounded-r-md transition-colors ${
              dayType === "weekend"
                ? "bg-blue-500 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
            onClick={() => setDayType("weekend")}
          >
            Weekend
          </button>
        </div>
      </div>

      <div className="relative">
        <div className="flex justify-between text-[10px] text-gray-400 mb-1 px-0.5">
          {hourLabels.map((h) => (
            <span key={h}>{h > 12 ? h - 12 : h}{h >= 12 ? "p" : "a"}</span>
          ))}
        </div>

        <div
          ref={containerRef}
          className={`relative h-12 bg-gray-100 rounded-lg ${disabled ? "opacity-50" : ""}`}
        >
          {containerWidth > 0 &&
            filteredRequirements.map((req, idx) => (
              <StaffingBlock
                key={`${req.day_type}-${idx}`}
                requirement={req}
                index={idx}
                containerWidth={containerWidth}
                onUpdate={handleUpdate}
                onDelete={handleDelete}
                disabled={disabled}
              />
            ))}
        </div>

        {!disabled && filteredRequirements.length < 8 && (
          <button
            onClick={handleAdd}
            className="absolute -bottom-3 left-1/2 -translate-x-1/2 w-6 h-6 bg-gray-200 hover:bg-gray-300 rounded-full flex items-center justify-center transition-colors"
            title="Add staffing block"
          >
            <Plus className="w-4 h-4 text-gray-600" />
          </button>
        )}
      </div>

      {filteredRequirements.length === 0 && (
        <p className="text-xs text-gray-400 text-center mt-4">
          No staffing requirements set for {dayType}s. Click + to add.
        </p>
      )}
    </div>
  );
}

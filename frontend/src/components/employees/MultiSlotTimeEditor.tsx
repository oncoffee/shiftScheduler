import { useRef, useState, useCallback, useEffect } from "react";
import { Plus, X } from "lucide-react";

interface TimeSlot {
  start_time: string;
  end_time: string;
}

interface MultiSlotTimeEditorProps {
  day: string;
  slots: TimeSlot[];
  minHour?: number;
  maxHour?: number;
  onChange: (slots: TimeSlot[]) => void;
  disabled?: boolean;
}

const HOUR_HEIGHT = 6;

function timeToMinutes(time: string): number {
  const [hours, minutes] = time.split(":").map(Number);
  return hours * 60 + minutes;
}

function minutesToTime(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
}

function formatTimeDisplay(time: string): string {
  const [hours, minutes] = time.split(":");
  let h = parseInt(hours);
  if (h === 24) h = 0;
  const suffix = h >= 12 ? "PM" : "AM";
  const displayHour = h > 12 ? h - 12 : h === 0 ? 12 : h;
  return `${displayHour}:${minutes} ${suffix}`;
}

function snapToHalfHour(minutes: number): number {
  return Math.round(minutes / 30) * 30;
}

const SLOT_COLORS = [
  { bg: "bg-blue-400", hover: "hover:bg-blue-500", active: "bg-blue-500" },
  { bg: "bg-green-400", hover: "hover:bg-green-500", active: "bg-green-500" },
  { bg: "bg-purple-400", hover: "hover:bg-purple-500", active: "bg-purple-500" },
  { bg: "bg-orange-400", hover: "hover:bg-orange-500", active: "bg-orange-500" },
];

export function MultiSlotTimeEditor({
  day,
  slots,
  minHour = 6,
  maxHour = 24,
  onChange,
  disabled = false,
}: MultiSlotTimeEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState<{
    slotIndex: number;
    type: "start" | "end" | "move";
  } | null>(null);
  const [dragStartY, setDragStartY] = useState(0);
  const [dragStartValues, setDragStartValues] = useState({ start: 0, end: 0 });

  const totalMinutes = (maxHour - minHour) * 60;
  const sliderHeight = (totalMinutes / 30) * HOUR_HEIGHT;

  const minutesToPosition = useCallback(
    (minutes: number) => {
      return ((minutes - minHour * 60) / totalMinutes) * sliderHeight;
    },
    [minHour, totalMinutes, sliderHeight]
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent, slotIndex: number, type: "start" | "end" | "move") => {
      if (disabled) return;
      e.preventDefault();
      e.stopPropagation();

      const slot = slots[slotIndex];
      setDragging({ slotIndex, type });
      setDragStartY(e.clientY);
      setDragStartValues({
        start: timeToMinutes(slot.start_time),
        end: timeToMinutes(slot.end_time),
      });
    },
    [disabled, slots]
  );

  const handleAddSlot = useCallback(() => {
    if (disabled) return;

    const sortedSlots = [...slots].sort(
      (a, b) => timeToMinutes(a.start_time) - timeToMinutes(b.start_time)
    );

    let newStart = minHour * 60;
    let newEnd = newStart + 120;

    for (let i = 0; i <= sortedSlots.length; i++) {
      const gapStart = i === 0 ? minHour * 60 : timeToMinutes(sortedSlots[i - 1].end_time);
      const gapEnd = i === sortedSlots.length ? maxHour * 60 : timeToMinutes(sortedSlots[i].start_time);

      if (gapEnd - gapStart >= 60) {
        newStart = gapStart;
        newEnd = Math.min(gapStart + 120, gapEnd);
        break;
      }
    }

    newStart = snapToHalfHour(newStart);
    newEnd = snapToHalfHour(newEnd);

    onChange([...slots, { start_time: minutesToTime(newStart), end_time: minutesToTime(newEnd) }]);
  }, [disabled, slots, minHour, maxHour, onChange]);

  const handleRemoveSlot = useCallback(
    (slotIndex: number) => {
      if (disabled) return;
      onChange(slots.filter((_, i) => i !== slotIndex));
    },
    [disabled, slots, onChange]
  );

  useEffect(() => {
    if (!dragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const deltaY = e.clientY - dragStartY;
      const deltaMinutes = (deltaY / sliderHeight) * totalMinutes;
      const { slotIndex, type } = dragging;
      const currentSlot = slots[slotIndex];

      const currentStart = timeToMinutes(currentSlot.start_time);
      const currentEnd = timeToMinutes(currentSlot.end_time);

      let newSlots = [...slots];

      if (type === "start") {
        const newStart = snapToHalfHour(dragStartValues.start + deltaMinutes);
        const clampedStart = Math.max(minHour * 60, Math.min(currentEnd - 30, newStart));
        newSlots[slotIndex] = {
          start_time: minutesToTime(clampedStart),
          end_time: currentSlot.end_time,
        };
      } else if (type === "end") {
        const newEnd = snapToHalfHour(dragStartValues.end + deltaMinutes);
        const clampedEnd = Math.min(maxHour * 60, Math.max(currentStart + 30, newEnd));
        newSlots[slotIndex] = {
          start_time: currentSlot.start_time,
          end_time: minutesToTime(clampedEnd),
        };
      } else if (type === "move") {
        const duration = dragStartValues.end - dragStartValues.start;
        let newStart = snapToHalfHour(dragStartValues.start + deltaMinutes);
        let newEnd = newStart + duration;

        if (newStart < minHour * 60) {
          newStart = minHour * 60;
          newEnd = newStart + duration;
        }
        if (newEnd > maxHour * 60) {
          newEnd = maxHour * 60;
          newStart = newEnd - duration;
        }

        newSlots[slotIndex] = {
          start_time: minutesToTime(newStart),
          end_time: minutesToTime(newEnd),
        };
      }

      onChange(newSlots);
    };

    const handleMouseUp = () => {
      setDragging(null);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [dragging, dragStartY, dragStartValues, sliderHeight, totalMinutes, minHour, maxHour, slots, onChange]);

  const hourLabels = [];
  for (let h = minHour; h <= maxHour; h += 3) {
    hourLabels.push(h);
  }

  return (
    <div className="flex flex-col items-center">
      <div className="text-xs font-semibold text-gray-600 mb-1">{day}</div>

      <div className="flex gap-1">
        {/* Hour labels */}
        <div
          className="flex flex-col justify-between text-[9px] text-gray-400 pr-0.5"
          style={{ height: sliderHeight }}
        >
          {hourLabels.map((h) => (
            <span key={h}>{h > 12 ? h - 12 : h}{h >= 12 ? "p" : "a"}</span>
          ))}
        </div>

        {/* Slider track */}
        <div
          ref={containerRef}
          className={`relative w-8 rounded-lg transition-colors bg-gray-100 ${
            disabled ? "opacity-50 cursor-not-allowed" : ""
          }`}
          style={{ height: sliderHeight }}
        >
          {/* Render each slot */}
          {slots.map((slot, idx) => {
            const startMinutes = timeToMinutes(slot.start_time);
            const endMinutes = timeToMinutes(slot.end_time);
            const topPosition = minutesToPosition(startMinutes);
            const bottomPosition = minutesToPosition(endMinutes);
            const barHeight = bottomPosition - topPosition;
            const color = SLOT_COLORS[idx % SLOT_COLORS.length];
            const isDragging = dragging?.slotIndex === idx;

            return (
              <div
                key={idx}
                className={`absolute left-0.5 right-0.5 rounded-md transition-colors ${
                  isDragging ? color.active : `${color.bg} ${color.hover}`
                } ${disabled ? "" : "cursor-grab active:cursor-grabbing"}`}
                style={{
                  top: topPosition,
                  height: Math.max(barHeight, 4),
                }}
                onMouseDown={(e) => handleMouseDown(e, idx, "move")}
              >
                {/* Top handle (start time) */}
                <div
                  className={`absolute -top-0.5 left-0 right-0 h-2 rounded-t-md ${
                    disabled ? "" : "cursor-ns-resize"
                  } flex items-center justify-center`}
                  onMouseDown={(e) => handleMouseDown(e, idx, "start")}
                >
                  <div className="w-3 h-0.5 bg-white/60 rounded-full" />
                </div>

                {/* Delete button - only show if multiple slots */}
                {slots.length > 1 && !disabled && (
                  <button
                    className="absolute -right-1 top-1/2 -translate-y-1/2 w-3 h-3 bg-red-500 rounded-full flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveSlot(idx);
                    }}
                  >
                    <X className="w-2 h-2 text-white" />
                  </button>
                )}

                {/* Bottom handle (end time) */}
                <div
                  className={`absolute -bottom-0.5 left-0 right-0 h-2 rounded-b-md ${
                    disabled ? "" : "cursor-ns-resize"
                  } flex items-center justify-center`}
                  onMouseDown={(e) => handleMouseDown(e, idx, "end")}
                >
                  <div className="w-3 h-0.5 bg-white/60 rounded-full" />
                </div>
              </div>
            );
          })}

          {/* Add slot button */}
          {!disabled && slots.length < 4 && (
            <button
              onClick={handleAddSlot}
              className="absolute -bottom-5 left-1/2 -translate-x-1/2 w-5 h-5 bg-gray-200 hover:bg-gray-300 rounded-full flex items-center justify-center transition-colors"
              title="Add time slot"
            >
              <Plus className="w-3 h-3 text-gray-600" />
            </button>
          )}
        </div>
      </div>

      {/* Time display for slots */}
      <div className="mt-6 text-center space-y-0.5">
        {slots.length === 0 ? (
          <div className="text-[10px] text-gray-400">No availability</div>
        ) : (
          slots.map((slot, idx) => (
            <div key={idx} className="text-[10px]">
              <span className={`font-medium ${SLOT_COLORS[idx % SLOT_COLORS.length].bg.replace("bg-", "text-").replace("-400", "-600")}`}>
                {formatTimeDisplay(slot.start_time)}-{formatTimeDisplay(slot.end_time)}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

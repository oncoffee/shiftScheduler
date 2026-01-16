import { useRef, useState, useCallback, useEffect } from "react";

interface TimeRangeSliderProps {
  day: string;
  startTime: string | null;
  endTime: string | null;
  minHour?: number;
  maxHour?: number;
  onChange: (startTime: string | null, endTime: string | null) => void;
  disabled?: boolean;
}

const HOUR_HEIGHT = 8; // pixels per 30 minutes

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

  // Handle 24:00 as midnight (12:00 AM)
  if (h === 24) h = 0;

  const suffix = h >= 12 ? "PM" : "AM";
  const displayHour = h > 12 ? h - 12 : h === 0 ? 12 : h;
  return `${displayHour}:${minutes} ${suffix}`;
}

function snapToHalfHour(minutes: number): number {
  return Math.round(minutes / 30) * 30;
}

export function TimeRangeSlider({
  day,
  startTime,
  endTime,
  minHour = 6,
  maxHour = 24,
  onChange,
  disabled = false,
}: TimeRangeSliderProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState<"start" | "end" | "move" | null>(null);
  const [dragStartY, setDragStartY] = useState(0);
  const [dragStartValues, setDragStartValues] = useState({ start: 0, end: 0 });

  const totalMinutes = (maxHour - minHour) * 60;
  const sliderHeight = (totalMinutes / 30) * HOUR_HEIGHT;

  // Use actual times if set, otherwise show default 6AM-6PM
  const isEnabled = startTime !== null && endTime !== null;
  const displayStartTime = startTime || "06:00";
  const displayEndTime = endTime || "18:00";
  const startMinutes = timeToMinutes(displayStartTime);
  const endMinutes = timeToMinutes(displayEndTime);

  const minutesToPosition = useCallback(
    (minutes: number) => {
      return ((minutes - minHour * 60) / totalMinutes) * sliderHeight;
    },
    [minHour, totalMinutes, sliderHeight]
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent, type: "start" | "end" | "move") => {
      if (disabled) return;
      e.preventDefault();
      e.stopPropagation();

      // If not enabled, enable with default times first
      if (!isEnabled) {
        onChange("06:00", "18:00");
      }

      setDragging(type);
      setDragStartY(e.clientY);
      setDragStartValues({ start: startMinutes, end: endMinutes });
    },
    [disabled, isEnabled, startMinutes, endMinutes, onChange]
  );

  useEffect(() => {
    if (!dragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const deltaY = e.clientY - dragStartY;
      const deltaMinutes = (deltaY / sliderHeight) * totalMinutes;

      const currentStart = isEnabled ? timeToMinutes(startTime!) : dragStartValues.start;
      const currentEnd = isEnabled ? timeToMinutes(endTime!) : dragStartValues.end;

      if (dragging === "start") {
        const newStart = snapToHalfHour(dragStartValues.start + deltaMinutes);
        const clampedStart = Math.max(minHour * 60, Math.min(currentEnd - 30, newStart));
        onChange(minutesToTime(clampedStart), endTime || minutesToTime(currentEnd));
      } else if (dragging === "end") {
        const newEnd = snapToHalfHour(dragStartValues.end + deltaMinutes);
        const clampedEnd = Math.min(maxHour * 60, Math.max(currentStart + 30, newEnd));
        onChange(startTime || minutesToTime(currentStart), minutesToTime(clampedEnd));
      } else if (dragging === "move") {
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

        onChange(minutesToTime(newStart), minutesToTime(newEnd));
      }
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
  }, [
    dragging,
    dragStartY,
    dragStartValues,
    sliderHeight,
    totalMinutes,
    minHour,
    maxHour,
    startTime,
    endTime,
    isEnabled,
    onChange,
  ]);

  const topPosition = minutesToPosition(startMinutes);
  const bottomPosition = minutesToPosition(endMinutes);
  const barHeight = bottomPosition - topPosition;

  // Generate hour labels
  const hourLabels = [];
  for (let h = minHour; h <= maxHour; h += 2) {
    hourLabels.push(h);
  }

  return (
    <div className="flex flex-col items-center">
      <div className="text-xs font-semibold text-gray-600 mb-2">{day}</div>

      <div className="flex gap-1">
        {/* Hour labels */}
        <div
          className="flex flex-col justify-between text-[10px] text-gray-400 pr-1"
          style={{ height: sliderHeight }}
        >
          {hourLabels.map((h) => (
            <span key={h}>{h > 12 ? h - 12 : h}{h >= 12 ? 'p' : 'a'}</span>
          ))}
        </div>

        {/* Slider track */}
        <div
          ref={containerRef}
          className={`relative w-10 rounded-lg transition-colors bg-gray-100 ${
            disabled ? "opacity-50 cursor-not-allowed" : ""
          }`}
          style={{ height: sliderHeight }}
        >
          {/* Selected range bar */}
          <div
            className={`absolute left-1 right-1 rounded-md transition-colors ${
              isEnabled
                ? dragging
                  ? "bg-blue-500"
                  : "bg-blue-400 hover:bg-blue-500"
                : "bg-gray-300 hover:bg-gray-400"
            } ${disabled ? "" : "cursor-grab active:cursor-grabbing"}`}
            style={{
              top: topPosition,
              height: Math.max(barHeight, 4),
            }}
            onMouseDown={(e) => handleMouseDown(e, "move")}
          >
            {/* Top handle (start time) */}
            <div
              className={`absolute -top-1 left-0 right-0 h-3 rounded-t-md ${
                disabled ? "" : "cursor-ns-resize"
              } flex items-center justify-center`}
              onMouseDown={(e) => handleMouseDown(e, "start")}
            >
              <div className="w-4 h-1 bg-white/60 rounded-full" />
            </div>

            {/* Bottom handle (end time) */}
            <div
              className={`absolute -bottom-1 left-0 right-0 h-3 rounded-b-md ${
                disabled ? "" : "cursor-ns-resize"
              } flex items-center justify-center`}
              onMouseDown={(e) => handleMouseDown(e, "end")}
            >
              <div className="w-4 h-1 bg-white/60 rounded-full" />
            </div>
          </div>
        </div>
      </div>

      {/* Time display */}
      <div className="mt-2 text-center">
        <div className="text-xs">
          <div className={`font-medium ${isEnabled ? "text-blue-600" : "text-gray-400"}`}>
            {formatTimeDisplay(displayStartTime)}
          </div>
          <div className="text-gray-400 text-[10px]">to</div>
          <div className={`font-medium ${isEnabled ? "text-blue-600" : "text-gray-400"}`}>
            {formatTimeDisplay(displayEndTime)}
          </div>
        </div>
      </div>
    </div>
  );
}

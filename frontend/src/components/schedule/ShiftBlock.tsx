import { cn } from "@/lib/utils";

const EMPLOYEE_COLORS = [
  "bg-blue-500",
  "bg-green-500",
  "bg-purple-500",
  "bg-orange-500",
  "bg-pink-500",
  "bg-teal-500",
  "bg-indigo-500",
  "bg-red-400",
  "bg-yellow-500",
  "bg-cyan-500",
];

interface ShiftBlockProps {
  shiftStart: string | null;
  shiftEnd: string | null;
  hours: number;
  employeeIndex: number;
}

export function ShiftBlock({
  shiftStart,
  shiftEnd,
  hours,
  employeeIndex,
}: ShiftBlockProps) {
  if (!shiftStart || !shiftEnd || hours === 0) {
    return <span className="text-muted-foreground text-xs">-</span>;
  }

  const colorClass = EMPLOYEE_COLORS[employeeIndex % EMPLOYEE_COLORS.length];

  return (
    <div
      className={cn(
        "rounded px-2 py-1 text-white text-xs font-medium",
        colorClass
      )}
    >
      <div className="whitespace-nowrap">
        {shiftStart} - {shiftEnd}
      </div>
      <div className="text-white/80 text-[10px]">{hours}h</div>
    </div>
  );
}

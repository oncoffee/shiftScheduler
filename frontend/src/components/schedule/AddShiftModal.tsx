import { useState, useMemo } from "react";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Clock, User, Calendar, AlertTriangle, Plus } from "lucide-react";

interface AddShiftModalProps {
  open: boolean;
  onClose: () => void;
  onAdd: (employeeName: string, dayOfWeek: string, startTime: string, endTime: string) => void;
  employees: string[];
  days: string[];
  scheduleStartDate?: string;
  initialEmployee?: string;
  initialDay?: string;
  initialStartTime?: string;
  initialEndTime?: string;
}

function formatTime12h(time24: string): string {
  const [hours, minutes] = time24.split(":").map(Number);
  const ampm = hours >= 12 ? "PM" : "AM";
  const hour12 = hours > 12 ? hours - 12 : hours === 0 ? 12 : hours;
  return `${hour12}:${minutes.toString().padStart(2, "0")} ${ampm}`;
}

function generateStartTimeOptions(): string[] {
  const times: string[] = [];
  for (let h = 6; h <= 22; h++) {
    times.push(`${h.toString().padStart(2, "0")}:00`);
    times.push(`${h.toString().padStart(2, "0")}:30`);
  }
  return times;
}

function generateEndTimeOptions(): string[] {
  const times: string[] = [];
  for (let h = 6; h <= 23; h++) {
    if (h === 6) {
      times.push(`${h.toString().padStart(2, "0")}:30`);
    } else if (h === 23) {
      times.push(`${h.toString().padStart(2, "0")}:00`);
    } else {
      times.push(`${h.toString().padStart(2, "0")}:00`);
      times.push(`${h.toString().padStart(2, "0")}:30`);
    }
  }
  return times;
}

const DAYS_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function getDateForDay(scheduleStartDate: string, dayOfWeek: string): Date {
  const start = new Date(scheduleStartDate + "T00:00:00");
  const startDay = start.getDay();
  const startMonday = new Date(start);
  startMonday.setDate(start.getDate() - (startDay === 0 ? 6 : startDay - 1));

  const dayIndex = DAYS_ORDER.indexOf(dayOfWeek);
  const targetDate = new Date(startMonday);
  targetDate.setDate(startMonday.getDate() + dayIndex);
  return targetDate;
}

function isDateInPast(date: Date): boolean {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const compareDate = new Date(date);
  compareDate.setHours(0, 0, 0, 0);
  return compareDate < today;
}

export function AddShiftModal({
  open,
  onClose,
  onAdd,
  employees,
  days,
  scheduleStartDate,
  initialEmployee,
  initialDay,
  initialStartTime,
  initialEndTime,
}: AddShiftModalProps) {
  const [selectedEmployee, setSelectedEmployee] = useState("");
  const [selectedDay, setSelectedDay] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");

  const startTimeOptions = useMemo(() => generateStartTimeOptions(), []);
  const endTimeOptions = useMemo(() => generateEndTimeOptions(), []);

  const futureDays = useMemo(() => {
    if (!scheduleStartDate) return days;
    return days.filter((day) => {
      const dayDate = getDateForDay(scheduleStartDate, day);
      return !isDateInPast(dayDate);
    });
  }, [days, scheduleStartDate]);

  useMemo(() => {
    if (open) {
      setSelectedEmployee(initialEmployee || (employees.length > 0 ? employees[0] : ""));
      const validInitialDay = initialDay && futureDays.includes(initialDay) ? initialDay : "";
      setSelectedDay(validInitialDay || (futureDays.length > 0 ? futureDays[0] : ""));
      setStartTime(initialStartTime || "09:00");
      setEndTime(initialEndTime || "17:00");
    }
  }, [open, initialEmployee, initialDay, initialStartTime, initialEndTime, employees, futureDays]);

  const handleClose = () => {
    setSelectedEmployee("");
    setSelectedDay("");
    setStartTime("");
    setEndTime("");
    onClose();
  };

  const calculateHours = (start: string, end: string): number => {
    if (!start || !end) return 0;
    const [startH, startM] = start.split(":").map(Number);
    const [endH, endM] = end.split(":").map(Number);
    const startMinutes = startH * 60 + startM;
    const endMinutes = endH * 60 + endM;
    return (endMinutes - startMinutes) / 60;
  };

  const duration = calculateHours(startTime, endTime);
  const isValidTimeRange = startTime && endTime && startTime < endTime;
  const isMinimumDuration = duration >= 0.5;
  const isShortShift = duration > 0 && duration < 3;
  const isFormValid = selectedEmployee && selectedDay && isValidTimeRange && isMinimumDuration;

  const handleAdd = () => {
    if (isFormValid) {
      onAdd(selectedEmployee, selectedDay, startTime, endTime);
      handleClose();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} title="Add New Shift">
      <DialogContent>
        <div className="space-y-4">
          <div className="p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <User className="w-5 h-5 text-gray-500" />
              <label className="font-medium text-gray-700">Employee</label>
            </div>
            <select
              value={selectedEmployee}
              onChange={(e) => setSelectedEmployee(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Select an employee...</option>
              {employees.map((emp) => (
                <option key={emp} value={emp}>
                  {emp}
                </option>
              ))}
            </select>
          </div>

          <div className="p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="w-5 h-5 text-gray-500" />
              <label className="font-medium text-gray-700">Day</label>
            </div>
            <select
              value={selectedDay}
              onChange={(e) => setSelectedDay(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Select a day...</option>
              {futureDays.map((day) => (
                <option key={day} value={day}>
                  {day}
                </option>
              ))}
            </select>
            {futureDays.length === 0 && (
              <p className="text-sm text-amber-600 mt-2">
                All days in this schedule are in the past
              </p>
            )}
          </div>

          <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
            <div className="flex items-center gap-2 mb-3">
              <Clock className="w-5 h-5 text-blue-500" />
              <p className="font-medium text-blue-900">Shift Time</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  Start Time
                </label>
                <select
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  {startTimeOptions.map((time) => (
                    <option key={`start-${time}`} value={time}>
                      {formatTime12h(time)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  End Time
                </label>
                <select
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  {endTimeOptions.map((time) => (
                    <option key={`end-${time}`} value={time}>
                      {formatTime12h(time)}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {startTime && endTime && !isValidTimeRange && (
              <p className="text-sm text-red-500 mt-2">
                End time must be after start time
              </p>
            )}
            {isValidTimeRange && !isMinimumDuration && (
              <p className="text-sm text-red-500 mt-2">
                Shift must be at least 30 minutes
              </p>
            )}
            {isValidTimeRange && isMinimumDuration && (
              <div className="flex items-center gap-2 mt-2">
                <p className="text-sm text-gray-600">
                  Duration: <span className="font-semibold">{duration}h</span>
                </p>
                {isShortShift && (
                  <span className="flex items-center gap-1 text-sm text-orange-500">
                    <AlertTriangle className="w-4 h-4" />
                    Short shift (&lt;3h)
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </DialogContent>

      <DialogFooter>
        <Button variant="outline" onClick={handleClose}>
          Cancel
        </Button>
        <Button onClick={handleAdd} disabled={!isFormValid}>
          <Plus className="w-4 h-4 mr-1" />
          Add Shift
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

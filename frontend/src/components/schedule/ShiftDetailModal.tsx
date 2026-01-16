import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Clock,
  User,
  Calendar,
  Lock,
  LockOpen,
  Trash2,
  AlertTriangle,
} from "lucide-react";
import type { EmployeeDaySchedule } from "@/types/schedule";

interface ShiftDetailModalProps {
  shift: EmployeeDaySchedule | null;
  open: boolean;
  onClose: () => void;
  onSave: (newStart: string, newEnd: string) => void;
  onDelete: () => void;
  onToggleLock: () => void;
  isEditMode: boolean;
}

function formatTime12h(time24: string): string {
  const [hours, minutes] = time24.split(":").map(Number);
  const ampm = hours >= 12 ? "PM" : "AM";
  const hour12 = hours > 12 ? hours - 12 : hours === 0 ? 12 : hours;
  return `${hour12}:${minutes.toString().padStart(2, "0")} ${ampm}`;
}

function generateTimeOptions(): string[] {
  const times: string[] = [];
  for (let h = 6; h <= 23; h++) {
    times.push(`${h.toString().padStart(2, "0")}:00`);
    times.push(`${h.toString().padStart(2, "0")}:30`);
  }
  return times;
}

export function ShiftDetailModal({
  shift,
  open,
  onClose,
  onSave,
  onDelete,
  onToggleLock,
  isEditMode,
}: ShiftDetailModalProps) {
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const timeOptions = generateTimeOptions();

  useEffect(() => {
    if (shift) {
      setStartTime(shift.shift_start || "");
      setEndTime(shift.shift_end || "");
      setShowDeleteConfirm(false);
    }
  }, [shift]);

  if (!shift) return null;

  const isLocked = shift.is_locked ?? false;
  const hasChanges =
    startTime !== shift.shift_start || endTime !== shift.shift_end;

  const handleSave = () => {
    if (startTime && endTime && startTime < endTime) {
      onSave(startTime, endTime);
      onClose();
    }
  };

  const handleDelete = () => {
    if (showDeleteConfirm) {
      onDelete();
      onClose();
    } else {
      setShowDeleteConfirm(true);
    }
  };

  const handleLockToggle = () => {
    onToggleLock();
  };

  // Calculate new hours based on selected times
  const calculateHours = (start: string, end: string): number => {
    if (!start || !end) return 0;
    const [startH, startM] = start.split(":").map(Number);
    const [endH, endM] = end.split(":").map(Number);
    const startMinutes = startH * 60 + startM;
    const endMinutes = endH * 60 + endM;
    return (endMinutes - startMinutes) / 60;
  };

  const newHours = calculateHours(startTime, endTime);
  const isValidTimeRange = startTime && endTime && startTime < endTime;

  return (
    <Dialog open={open} onClose={onClose} title="Shift Details">
      <DialogContent>
        {/* Employee & Day Info */}
        <div className="space-y-4">
          <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
            <User className="w-5 h-5 text-gray-500" />
            <div>
              <p className="text-sm text-gray-500">Employee</p>
              <p className="font-semibold text-gray-900">
                {shift.employee_name}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
            <Calendar className="w-5 h-5 text-gray-500" />
            <div>
              <p className="text-sm text-gray-500">Day</p>
              <p className="font-semibold text-gray-900">{shift.day_of_week}</p>
            </div>
          </div>

          {/* Time Selection (only in edit mode and not locked) */}
          {isEditMode && !isLocked ? (
            <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
              <div className="flex items-center gap-2 mb-3">
                <Clock className="w-5 h-5 text-blue-500" />
                <p className="font-medium text-blue-900">Edit Shift Time</p>
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
                    {timeOptions.map((time) => (
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
                    {timeOptions.map((time) => (
                      <option key={`end-${time}`} value={time}>
                        {formatTime12h(time)}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {!isValidTimeRange && startTime && endTime && (
                <p className="text-sm text-red-500 mt-2">
                  End time must be after start time
                </p>
              )}
              {isValidTimeRange && (
                <p className="text-sm text-gray-600 mt-2">
                  New duration: <span className="font-semibold">{newHours}h</span>
                  {newHours > 0 && newHours < 3 && (
                    <span className="text-orange-500 ml-1">(short shift)</span>
                  )}
                </p>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Clock className="w-5 h-5 text-gray-500" />
              <div>
                <p className="text-sm text-gray-500">Time</p>
                <p className="font-semibold text-gray-900">
                  {formatTime12h(shift.shift_start!)} -{" "}
                  {formatTime12h(shift.shift_end!)}
                </p>
              </div>
            </div>
          )}

          {/* Hours & Status */}
          <div className="flex gap-3">
            <div className="flex-1 p-3 bg-gray-50 rounded-lg text-center">
              <p className="text-2xl font-bold text-gray-900">
                {shift.total_hours}h
              </p>
              <p className="text-sm text-gray-500">Total Hours</p>
            </div>
            <div
              className={`flex-1 p-3 rounded-lg text-center ${
                isLocked
                  ? "bg-gray-200"
                  : shift.is_short_shift
                    ? "bg-orange-50"
                    : "bg-green-50"
              }`}
            >
              {isLocked ? (
                <>
                  <Lock className="w-6 h-6 mx-auto text-gray-600" />
                  <p className="text-sm text-gray-600 mt-1">Locked</p>
                </>
              ) : shift.is_short_shift ? (
                <>
                  <AlertTriangle className="w-6 h-6 mx-auto text-orange-500" />
                  <p className="text-sm text-orange-600 mt-1">Short Shift</p>
                </>
              ) : (
                <>
                  <div className="w-6 h-6 mx-auto rounded-full bg-green-500 flex items-center justify-center">
                    <span className="text-white text-xs">OK</span>
                  </div>
                  <p className="text-sm text-green-600 mt-1">Valid</p>
                </>
              )}
            </div>
          </div>

          {/* Lock/Unlock Button (only in edit mode) */}
          {isEditMode && (
            <button
              onClick={handleLockToggle}
              className={`w-full flex items-center justify-center gap-2 p-3 rounded-lg border-2 transition-colors ${
                isLocked
                  ? "border-gray-400 bg-gray-100 text-gray-700 hover:bg-gray-200"
                  : "border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100"
              }`}
            >
              {isLocked ? (
                <>
                  <LockOpen className="w-5 h-5" />
                  Unlock Shift
                </>
              ) : (
                <>
                  <Lock className="w-5 h-5" />
                  Lock Shift
                </>
              )}
            </button>
          )}

          {/* Delete Confirmation */}
          {isEditMode && !isLocked && showDeleteConfirm && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-700">
                Are you sure you want to delete this shift? This will remove{" "}
                {shift.employee_name}'s shift on {shift.day_of_week}.
              </p>
            </div>
          )}
        </div>
      </DialogContent>

      <DialogFooter>
        {isEditMode && !isLocked && (
          <Button
            variant="outline"
            onClick={handleDelete}
            className={
              showDeleteConfirm
                ? "bg-red-500 text-white hover:bg-red-600 border-red-500"
                : "text-red-600 border-red-200 hover:bg-red-50"
            }
          >
            <Trash2 className="w-4 h-4 mr-1" />
            {showDeleteConfirm ? "Confirm Delete" : "Delete"}
          </Button>
        )}
        <div className="flex-1" />
        <Button variant="outline" onClick={onClose}>
          {isEditMode ? "Cancel" : "Close"}
        </Button>
        {isEditMode && !isLocked && hasChanges && (
          <Button onClick={handleSave} disabled={!isValidTimeRange}>
            Save Changes
          </Button>
        )}
      </DialogFooter>
    </Dialog>
  );
}

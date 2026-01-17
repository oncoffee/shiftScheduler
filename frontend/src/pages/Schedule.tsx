import { useState, useEffect, useCallback, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Play, Loader2, CheckCircle, XCircle, RefreshCw, Edit3, Plus, Calendar, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import { api } from "@/api/client";
import type { Employee } from "@/api/client";
import { WeeklyCalendar, EditModeToolbar, ShiftDetailModal, AddShiftModal } from "@/components/schedule";
import {
  ScheduleEditProvider,
  useScheduleEditContext,
} from "@/contexts/ScheduleEditContext";
import type { WeeklyScheduleResult, EmployeeDaySchedule, ComplianceViolation } from "@/types/schedule";

// Helper functions for date handling
function getTomorrow(): Date {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  return tomorrow;
}

function addDays(d: Date, days: number): Date {
  const result = new Date(d);
  result.setDate(result.getDate() + days);
  return result;
}

function formatDateISO(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatDateRange(startDate: string, endDate: string): string {
  const start = new Date(startDate + "T00:00:00");
  const end = new Date(endDate + "T00:00:00");
  const startMonth = start.toLocaleString("en-US", { month: "short" });
  const endMonth = end.toLocaleString("en-US", { month: "short" });
  const startDay = start.getDate();
  const endDay = end.getDate();

  if (startMonth === endMonth) {
    return `${startMonth} ${startDay} - ${endDay}`;
  }
  return `${startMonth} ${startDay} - ${endMonth} ${endDay}`;
}

type SolverStatus = "idle" | "running" | "success" | "error";

function ScheduleContent() {
  const [status, setStatus] = useState<SolverStatus>("idle");
  const [message, setMessage] = useState<string>("");
  const [scheduleResult, setScheduleResult] =
    useState<WeeklyScheduleResult | null>(null);
  const [scheduleId, setScheduleId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [addShiftInitial, setAddShiftInitial] = useState<{
    employee?: string;
    day?: string;
    startTime?: string;
    endTime?: string;
  }>({});

  const [showDatePicker, setShowDatePicker] = useState(false);
  const [showViolationsDetail, setShowViolationsDetail] = useState(false);
  const tomorrow = getTomorrow();
  const minDate = formatDateISO(tomorrow);
  const [selectedStartDate, setSelectedStartDate] = useState(() => formatDateISO(tomorrow));
  const [selectedEndDate, setSelectedEndDate] = useState(() => formatDateISO(addDays(tomorrow, 6)));
  const [employees, setEmployees] = useState<Employee[]>([]);

  const {
    localSchedules,
    localSummaries,
    hasUnsavedChanges,
    isSaving,
    updateLocalShift,
    addNewShift,
    setScheduleData,
    toggleShiftLock,
    deleteShift,
    selectedShift,
    setSelectedShift,
  } = useScheduleEditContext();

  const loadCachedSchedule = useCallback(async () => {
    try {
      const [result, employeeList] = await Promise.all([
        api.getScheduleResults(),
        api.getEmployees(),
      ]);

      setEmployees(employeeList);

      if (result) {
        setScheduleResult(result);
        setStatus("success");

        const history = await api.getScheduleHistory(1, 0);
        if (history.length > 0 && history[0].is_current) {
          setScheduleId(history[0].id);
          setScheduleData(result, history[0].id);
        }
      }
    } catch (e) {
      void e;
    } finally {
      setLoading(false);
    }
  }, [setScheduleData]);

  useEffect(() => {
    loadCachedSchedule();
  }, [loadCachedSchedule]);

  async function runSolver(startDate?: string, endDate?: string) {
    setStatus("running");
    setMessage("");
    setShowDatePicker(false);

    const start = startDate || selectedStartDate;
    const end = endDate || selectedEndDate;

    try {
      const result = await api.runSolver("vero", start, end);
      setScheduleResult(result);
      setStatus("success");
      setMessage("Solver completed successfully!");

      // Get the new schedule ID
      const history = await api.getScheduleHistory(1, 0);
      if (history.length > 0) {
        setScheduleId(history[0].id);
        setScheduleData(result, history[0].id);
      }
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "An error occurred");
    }
  }

  function handleRunSolverClick() {
    setShowDatePicker(true);
  }

  function handleDatePickerConfirm() {
    runSolver(selectedStartDate, selectedEndDate);
  }

  const handleShiftUpdate = useCallback(
    (
      employeeName: string,
      dayOfWeek: string,
      newStart: string,
      newEnd: string,
      originalStart: string,
      originalEnd: string,
      newEmployeeName?: string
    ) => {
      updateLocalShift(employeeName, dayOfWeek, newStart, newEnd, originalStart, originalEnd, newEmployeeName);
    },
    [updateLocalShift]
  );

  const handleShiftClick = useCallback((shift: EmployeeDaySchedule) => {
    setSelectedShift(shift);
  }, [setSelectedShift]);

  const handleModalClose = useCallback(() => {
    setSelectedShift(null);
  }, [setSelectedShift]);

  const handleModalSave = useCallback(
    (newStart: string, newEnd: string) => {
      if (selectedShift) {
        updateLocalShift(
          selectedShift.employee_name,
          selectedShift.day_of_week,
          newStart,
          newEnd,
          selectedShift.shift_start!,
          selectedShift.shift_end!
        );
      }
    },
    [selectedShift, updateLocalShift]
  );

  const handleModalDelete = useCallback(() => {
    if (selectedShift) {
      deleteShift(selectedShift.employee_name, selectedShift.day_of_week);
    }
  }, [selectedShift, deleteShift]);

  const handleModalToggleLock = useCallback(() => {
    if (selectedShift && selectedShift.date) {
      toggleShiftLock(selectedShift.employee_name, selectedShift.date);
      // Update the selected shift with new lock state
      const updatedShift = localSchedules.find(
        (s) => s.employee_name === selectedShift.employee_name && s.date === selectedShift.date
      );
      if (updatedShift) {
        setSelectedShift({ ...updatedShift, is_locked: !selectedShift.is_locked });
      }
    }
  }, [selectedShift, toggleShiftLock, localSchedules, setSelectedShift]);

  const handleEmptyClick = useCallback((
    employeeName: string,
    dayOfWeek: string,
    startTime?: string,
    endTime?: string
  ) => {
    setAddShiftInitial({ employee: employeeName, day: dayOfWeek, startTime, endTime });
    setShowAddModal(true);
  }, []);

  const handleAddShiftButtonClick = useCallback(() => {
    setAddShiftInitial({});
    setShowAddModal(true);
  }, []);

  const displaySchedules = localSchedules.length > 0 ? localSchedules : scheduleResult?.schedules ?? [];
  const displaySummaries = localSummaries.length > 0 ? localSummaries : scheduleResult?.daily_summaries ?? [];

  const uniqueEmployees = useMemo(() => {
    const names = new Set(displaySchedules.map((s) => s.employee_name));
    return Array.from(names).sort();
  }, [displaySchedules]);

  const uniqueDays = useMemo(() => {
    const dayOrder = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    const days = new Set(displaySchedules.map((s) => s.day_of_week));
    return Array.from(days).sort((a, b) => dayOrder.indexOf(a) - dayOrder.indexOf(b));
  }, [displaySchedules]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Schedule</h1>
        <p className="text-muted-foreground mt-1">
          Generate and view optimized schedules
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Run Scheduler</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            The scheduler uses Gurobi optimization to generate the most
            cost-effective employee schedule based on availability and store
            requirements.
          </p>

          <div className="flex items-center gap-4">
            <Button
              onClick={handleRunSolverClick}
              disabled={status === "running" || hasUnsavedChanges || isSaving}
              size="lg"
            >
              {status === "running" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Calendar className="mr-2 h-4 w-4" />
                  Run Solver
                </>
              )}
            </Button>

            {status !== "idle" && status !== "running" && (
              <Badge
                variant={status === "success" ? "default" : "destructive"}
                className="flex items-center gap-1"
              >
                {status === "success" ? (
                  <CheckCircle className="h-3 w-3" />
                ) : (
                  <XCircle className="h-3 w-3" />
                )}
                {status === "success" ? "Completed" : "Failed"}
              </Badge>
            )}
          </div>

          {message && (
            <div
              className={`p-4 rounded-md text-sm ${
                status === "success"
                  ? "bg-green-50 text-green-900 dark:bg-green-950 dark:text-green-100"
                  : "bg-red-50 text-red-900 dark:bg-red-950 dark:text-red-100"
              }`}
            >
              {message}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Generated Schedule</CardTitle>
            {scheduleResult && (
              <p className="text-sm text-muted-foreground mt-1">
                {formatDateRange(scheduleResult.start_date, scheduleResult.end_date)} - {scheduleResult.store_name} |
                Generated: {new Date(scheduleResult.generated_at).toLocaleString()}
                {scheduleResult.is_edited && scheduleResult.last_edited_at && (
                  <span className="ml-2 text-amber-600">
                    (Edited: {new Date(scheduleResult.last_edited_at).toLocaleString()})
                  </span>
                )}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {scheduleResult && scheduleId && (
              <Button variant="outline" size="sm" onClick={handleAddShiftButtonClick}>
                <Plus className="h-4 w-4 mr-1" />
                Add Shift
              </Button>
            )}
            {scheduleResult && scheduleId && <EditModeToolbar />}
            {scheduleResult && !hasUnsavedChanges && !isSaving && (
              <Button variant="outline" size="sm" onClick={handleRunSolverClick}>
                <RefreshCw className="h-4 w-4 mr-1" />
                Regenerate
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : scheduleResult ? (
            <div className="space-y-4">
              <div className="flex gap-4 text-sm">
                <div className="px-3 py-2 bg-muted rounded-md">
                  <span className="text-muted-foreground">Labor Cost: </span>
                  <span className="font-bold">
                    ${(scheduleResult.total_weekly_cost - (scheduleResult.total_dummy_worker_cost || 0) - (scheduleResult.total_short_shift_penalty || 0)).toFixed(2)}
                  </span>
                </div>
                <div className="px-3 py-2 bg-muted rounded-md">
                  <span className="text-muted-foreground">Status: </span>
                  <span className="font-medium capitalize">
                    {scheduleResult.status}
                  </span>
                </div>
                {scheduleResult.is_edited && (
                  <div className="px-3 py-2 bg-amber-50 text-amber-700 rounded-md flex items-center gap-1">
                    <Edit3 className="h-3 w-3" />
                    <span className="font-medium">Manually Edited</span>
                  </div>
                )}
              </div>

              {/* Compliance Violations Banner */}
              {scheduleResult.compliance_violations && scheduleResult.compliance_violations.length > 0 && (
                <div className="rounded-lg border border-amber-200 bg-amber-50">
                  <button
                    onClick={() => setShowViolationsDetail(!showViolationsDetail)}
                    className="w-full px-4 py-3 flex items-center justify-between text-left"
                  >
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-5 w-5 text-amber-600" />
                      <span className="font-medium text-amber-800">
                        {scheduleResult.compliance_violations.length} Compliance{" "}
                        {scheduleResult.compliance_violations.length === 1 ? "Warning" : "Warnings"}
                      </span>
                    </div>
                    {showViolationsDetail ? (
                      <ChevronUp className="h-4 w-4 text-amber-600" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-amber-600" />
                    )}
                  </button>
                  {showViolationsDetail && (
                    <div className="px-4 pb-4 space-y-2">
                      {scheduleResult.compliance_violations.map((v: ComplianceViolation, idx: number) => (
                        <div
                          key={idx}
                          className={`px-3 py-2 rounded-md text-sm ${
                            v.severity === "error"
                              ? "bg-red-100 text-red-800 border border-red-200"
                              : "bg-amber-100 text-amber-800 border border-amber-200"
                          }`}
                        >
                          <div className="flex items-start justify-between">
                            <div>
                              <span className="font-medium">{v.employee_name}</span>
                              {v.date && <span className="text-xs ml-2">({v.date})</span>}
                            </div>
                            <Badge
                              variant={v.severity === "error" ? "destructive" : "secondary"}
                              className="text-xs"
                            >
                              {v.rule_type.replace(/_/g, " ")}
                            </Badge>
                          </div>
                          <p className="mt-1 text-xs">{v.message}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <WeeklyCalendar
                schedules={displaySchedules}
                dailySummaries={displaySummaries}
                startDate={scheduleResult?.start_date}
                isEditMode={true}
                onShiftUpdate={handleShiftUpdate}
                onToggleLock={toggleShiftLock}
                onShiftClick={handleShiftClick}
                onEmptyClick={handleEmptyClick}
                employeeAvailability={employees}
              />

              <ShiftDetailModal
                shift={selectedShift}
                open={selectedShift !== null}
                onClose={handleModalClose}
                onSave={handleModalSave}
                onDelete={handleModalDelete}
                onToggleLock={handleModalToggleLock}
                isEditMode={true}
              />

              <AddShiftModal
                open={showAddModal}
                onClose={() => setShowAddModal(false)}
                onAdd={addNewShift}
                employees={uniqueEmployees}
                days={uniqueDays}
                scheduleStartDate={scheduleResult?.start_date}
                initialEmployee={addShiftInitial.employee}
                initialDay={addShiftInitial.day}
                initialStartTime={addShiftInitial.startTime}
                initialEndTime={addShiftInitial.endTime}
              />
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">
              Run the solver to generate a schedule. Results will be shown here
              and logged to the Logs page.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Date Range Picker Modal */}
      <Dialog open={showDatePicker} onClose={() => setShowDatePicker(false)} title="Select Date Range">
        <DialogContent>
          <div className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="start-date" className="text-sm font-medium text-gray-700">
                Start Date
              </label>
              <input
                id="start-date"
                type="date"
                value={selectedStartDate}
                min={minDate}
                onChange={(e) => {
                  setSelectedStartDate(e.target.value);
                  if (e.target.value > selectedEndDate) {
                    setSelectedEndDate(e.target.value);
                  }
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="end-date" className="text-sm font-medium text-gray-700">
                End Date
              </label>
              <input
                id="end-date"
                type="date"
                value={selectedEndDate}
                min={selectedStartDate}
                onChange={(e) => setSelectedEndDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            {selectedStartDate < minDate && (
              <p className="text-sm text-red-500 text-center">
                Start date cannot be in the past. Schedules can only be created for tomorrow onwards.
              </p>
            )}
            <p className="text-sm text-gray-500 text-center">
              Schedules can only be created for future dates (starting tomorrow).
            </p>
          </div>
        </DialogContent>
        <DialogFooter>
          <Button variant="outline" onClick={() => setShowDatePicker(false)}>
            Cancel
          </Button>
          <Button onClick={handleDatePickerConfirm} disabled={selectedStartDate < minDate}>
            <Play className="mr-2 h-4 w-4" />
            Run Solver
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}

export function Schedule() {
  return (
    <ScheduleEditProvider>
      <ScheduleContent />
    </ScheduleEditProvider>
  );
}

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Play, Loader2, CheckCircle, XCircle, RefreshCw, Edit3 } from "lucide-react";
import { api } from "@/api/client";
import { WeeklyCalendar, EditModeToolbar } from "@/components/schedule";
import {
  ScheduleEditProvider,
  useScheduleEditContext,
} from "@/contexts/ScheduleEditContext";
import type { WeeklyScheduleResult } from "@/types/schedule";

type SolverStatus = "idle" | "running" | "success" | "error";

function ScheduleContent() {
  const [status, setStatus] = useState<SolverStatus>("idle");
  const [message, setMessage] = useState<string>("");
  const [scheduleResult, setScheduleResult] =
    useState<WeeklyScheduleResult | null>(null);
  const [scheduleId, setScheduleId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const {
    isEditMode,
    localSchedules,
    localSummaries,
    updateLocalShift,
    setScheduleData,
  } = useScheduleEditContext();

  const loadCachedSchedule = useCallback(async () => {
    try {
      // Get the current schedule
      const result = await api.getScheduleResults();
      if (result) {
        setScheduleResult(result);
        setStatus("success");

        // Get the schedule ID from history
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

  async function runSolver() {
    setStatus("running");
    setMessage("");

    try {
      const result = await api.runSolver("vero");
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

  const handleShiftUpdate = useCallback(
    (
      employeeName: string,
      dayOfWeek: string,
      newStart: string,
      newEnd: string,
      newEmployeeName?: string
    ) => {
      updateLocalShift(employeeName, dayOfWeek, newStart, newEnd, newEmployeeName);
    },
    [updateLocalShift]
  );

  // Use local schedules when in edit mode, otherwise use the original
  const displaySchedules = isEditMode ? localSchedules : scheduleResult?.schedules ?? [];
  const displaySummaries = isEditMode ? localSummaries : scheduleResult?.daily_summaries ?? [];

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
              onClick={runSolver}
              disabled={status === "running" || isEditMode}
              size="lg"
            >
              {status === "running" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" />
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
                Week {scheduleResult.week_no} - {scheduleResult.store_name} |
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
            {scheduleResult && scheduleId && <EditModeToolbar />}
            {scheduleResult && !isEditMode && (
              <Button variant="outline" size="sm" onClick={runSolver}>
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
                  <span className="text-muted-foreground">Total Cost: </span>
                  <span className="font-bold">
                    ${scheduleResult.total_weekly_cost.toFixed(2)}
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

              {isEditMode && (
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
                  <strong>Edit Mode:</strong> Drag shifts up/down to change times, or resize by dragging the top/bottom edges.
                  Press <kbd className="px-1.5 py-0.5 bg-blue-100 rounded text-xs">Ctrl+Z</kbd> to undo.
                </div>
              )}

              <WeeklyCalendar
                schedules={displaySchedules}
                dailySummaries={displaySummaries}
                isEditMode={isEditMode}
                onShiftUpdate={handleShiftUpdate}
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

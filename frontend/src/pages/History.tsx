import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Loader2,
  History as HistoryIcon,
  Eye,
  AlertTriangle,
  CheckCircle,
  ArrowLeft,
} from "lucide-react";
import { api, type ScheduleHistoryItem } from "@/api/client";
import { WeeklyCalendar } from "@/components/schedule";
import type { WeeklyScheduleResult } from "@/types/schedule";

export function History() {
  const [history, setHistory] = useState<ScheduleHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSchedule, setSelectedSchedule] =
    useState<WeeklyScheduleResult | null>(null);
  const [loadingSchedule, setLoadingSchedule] = useState(false);

  useEffect(() => {
    loadHistory();
  }, []);

  async function loadHistory() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getScheduleHistory();
      setHistory(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  }

  async function viewSchedule(id: string) {
    setLoadingSchedule(true);
    try {
      const schedule = await api.getScheduleById(id);
      setSelectedSchedule(schedule);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load schedule"
      );
    } finally {
      setLoadingSchedule(false);
    }
  }

  function formatDate(dateString: string): string {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  if (selectedSchedule) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => setSelectedSchedule(null)}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to History
          </Button>
        </div>

        <div>
          <h1 className="text-3xl font-bold">Schedule Details</h1>
          <p className="text-muted-foreground mt-1">
            Week {selectedSchedule.week_no} - {selectedSchedule.store_name} |
            Generated: {formatDate(selectedSchedule.generated_at)}
          </p>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Schedule Overview</CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant={selectedSchedule.status === "optimal" ? "default" : "secondary"}>
                  {selectedSchedule.status}
                </Badge>
                {selectedSchedule.has_warnings && (
                  <Badge variant="destructive" className="flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    Warnings
                  </Badge>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4 text-sm mb-6">
              <div className="px-3 py-2 bg-muted rounded-md">
                <span className="text-muted-foreground">Total Cost: </span>
                <span className="font-bold">
                  ${selectedSchedule.total_weekly_cost.toFixed(2)}
                </span>
              </div>
              {selectedSchedule.total_dummy_worker_cost > 0 && (
                <div className="px-3 py-2 bg-yellow-50 text-yellow-800 rounded-md">
                  <span className="text-yellow-600">Unfilled Penalty: </span>
                  <span className="font-bold">
                    ${selectedSchedule.total_dummy_worker_cost.toFixed(2)}
                  </span>
                </div>
              )}
              {selectedSchedule.total_short_shift_penalty > 0 && (
                <div className="px-3 py-2 bg-orange-50 text-orange-800 rounded-md">
                  <span className="text-orange-600">Short Shift Penalty: </span>
                  <span className="font-bold">
                    ${selectedSchedule.total_short_shift_penalty.toFixed(2)}
                  </span>
                </div>
              )}
            </div>
            <WeeklyCalendar
              schedules={selectedSchedule.schedules}
              dailySummaries={selectedSchedule.daily_summaries}
            />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Schedule History</h1>
        <p className="text-muted-foreground mt-1">
          View past solver runs and their results
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <HistoryIcon className="w-5 h-5" />
            Past Runs
          </CardTitle>
          <Button variant="outline" size="sm" onClick={loadHistory} disabled={loading}>
            <Loader2 className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-lg mb-4">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-sm">{error}</span>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : history.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <HistoryIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No schedule history found.</p>
              <p className="text-sm">Run the solver to generate schedules.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Generated</TableHead>
                  <TableHead>Week</TableHead>
                  <TableHead>Store</TableHead>
                  <TableHead>Total Cost</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">
                      {formatDate(item.generated_at)}
                    </TableCell>
                    <TableCell>Week {item.week_no}</TableCell>
                    <TableCell>{item.store_name}</TableCell>
                    <TableCell>${item.total_weekly_cost.toFixed(2)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={item.status === "optimal" ? "default" : "secondary"}
                        >
                          {item.status}
                        </Badge>
                        {item.is_current && (
                          <Badge variant="outline" className="flex items-center gap-1">
                            <CheckCircle className="w-3 h-3" />
                            Current
                          </Badge>
                        )}
                        {item.has_warnings && (
                          <Badge variant="destructive" className="flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" />
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => viewSchedule(item.id)}
                        disabled={loadingSchedule}
                      >
                        {loadingSchedule ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <>
                            <Eye className="w-4 h-4 mr-1" />
                            View
                          </>
                        )}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

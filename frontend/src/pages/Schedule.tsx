import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Play, Loader2, CheckCircle, XCircle } from "lucide-react";
import { api } from "@/api/client";

type SolverStatus = "idle" | "running" | "success" | "error";

export function Schedule() {
  const [status, setStatus] = useState<SolverStatus>("idle");
  const [message, setMessage] = useState<string>("");

  async function runSolver() {
    setStatus("running");
    setMessage("");

    try {
      const result = await api.runSolver("vero");
      setStatus("success");
      setMessage(typeof result === "string" ? result : "Solver completed successfully!");
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "An error occurred");
    }
  }

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
            The scheduler uses Gurobi optimization to generate the most cost-effective
            employee schedule based on availability and store requirements.
          </p>

          <div className="flex items-center gap-4">
            <Button
              onClick={runSolver}
              disabled={status === "running"}
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
        <CardHeader>
          <CardTitle>Generated Schedule</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-sm">
            Run the solver to generate a schedule. Results will be shown here and
            logged to the Logs page.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

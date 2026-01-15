import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";
import { api } from "@/api/client";

export function Logs() {
  const [logs, setLogs] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function fetchLogs() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getLogs();
      setLogs(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch logs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchLogs();
  }, []);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Logs</h1>
          <p className="text-muted-foreground mt-1">
            View solver output and system logs
          </p>
        </div>
        <Button variant="outline" onClick={fetchLogs} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Solver Output</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading logs...</p>
          ) : error ? (
            <p className="text-destructive">{error}</p>
          ) : logs === "Log file not found" ? (
            <p className="text-muted-foreground">
              No logs available. Run the scheduler to generate logs.
            </p>
          ) : (
            <pre className="bg-muted p-4 rounded-md text-sm overflow-auto max-h-[600px] whitespace-pre-wrap">
              {logs}
            </pre>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Users, Store, Calendar, Play, CheckCircle, XCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api } from "@/api/client";

interface DashboardStats {
  employees: number;
  stores: number;
  schedules: number;
}

export function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats>({ employees: 0, stores: 0, schedules: 0 });
  const [loading, setLoading] = useState(true);
  const [apiStatus, setApiStatus] = useState<"connected" | "disconnected">("disconnected");

  useEffect(() => {
    async function fetchStats() {
      try {
        const [employees, stores, schedules] = await Promise.all([
          api.getEmployees(),
          api.getStores(),
          api.getSchedules(),
        ]);
        setStats({
          employees: employees.length,
          stores: stores.length,
          schedules: schedules.length,
        });
        setApiStatus("connected");
      } catch {
        setApiStatus("disconnected");
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Manage your shift scheduling system
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Employees</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {loading ? "..." : stats.employees}
            </div>
            <p className="text-xs text-muted-foreground">Active employees</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Stores</CardTitle>
            <Store className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {loading ? "..." : stats.stores}
            </div>
            <p className="text-xs text-muted-foreground">Store configurations</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Schedules</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {loading ? "..." : stats.schedules}
            </div>
            <p className="text-xs text-muted-foreground">Availability entries</p>
          </CardContent>
        </Card>

        <Card className="bg-primary text-primary-foreground">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Quick Action</CardTitle>
            <Play className="h-4 w-4" />
          </CardHeader>
          <CardContent>
            <Button
              variant="secondary"
              className="w-full mt-2"
              onClick={() => navigate("/schedule")}
            >
              Run Scheduler
            </Button>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground text-sm">
              No recent activity to display.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>System Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between items-center text-sm">
              <span>Backend API</span>
              <span className={`flex items-center gap-1 ${apiStatus === "connected" ? "text-green-500" : "text-red-500"}`}>
                {apiStatus === "connected" ? (
                  <><CheckCircle className="h-3 w-3" /> Connected</>
                ) : (
                  <><XCircle className="h-3 w-3" /> Disconnected</>
                )}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span>Google Sheets</span>
              <span className="text-muted-foreground">Configured</span>
            </div>
            <div className="flex justify-between text-sm">
              <span>Gurobi Solver</span>
              <span className="text-muted-foreground">Ready</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

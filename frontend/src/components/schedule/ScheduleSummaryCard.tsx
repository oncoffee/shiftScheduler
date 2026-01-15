import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DollarSign } from "lucide-react";
import type { DayScheduleSummary, EmployeeDaySchedule } from "@/types/schedule";

interface ScheduleSummaryCardProps {
  dailySummaries: DayScheduleSummary[];
  schedules: EmployeeDaySchedule[];
  totalWeeklyCost: number;
}

export function ScheduleSummaryCard({
  dailySummaries,
  schedules,
  totalWeeklyCost,
}: ScheduleSummaryCardProps) {
  const totalLaborHours = dailySummaries.reduce(
    (sum, s) => sum + s.total_labor_hours,
    0
  );

  // Count unique employees who have at least one shift
  const employeesWithShifts = new Set(
    schedules.filter((s) => s.total_hours > 0).map((s) => s.employee_name)
  ).size;

  const totalEmployees = new Set(schedules.map((s) => s.employee_name)).size;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">Weekly Overview</CardTitle>
        <DollarSign className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground text-sm">Total Cost</span>
            <span className="text-2xl font-bold">
              ${totalWeeklyCost.toFixed(0)}
            </span>
          </div>
          <div className="flex justify-between items-center text-sm">
            <span className="text-muted-foreground">Labor Hours</span>
            <span className="font-medium">{totalLaborHours} hrs</span>
          </div>
          <div className="flex justify-between items-center text-sm">
            <span className="text-muted-foreground">Employees Used</span>
            <span className="font-medium">
              {employeesWithShifts}/{totalEmployees}
            </span>
          </div>
          <div className="pt-2 border-t">
            <div className="grid grid-cols-7 gap-1 text-xs">
              {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => (
                <div key={i} className="text-center text-muted-foreground">
                  {d}
                </div>
              ))}
              {[
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
              ].map((day) => {
                const summary = dailySummaries.find(
                  (s) => s.day_of_week === day
                );
                return (
                  <div
                    key={day}
                    className="text-center font-medium text-xs"
                    title={`${day}: $${summary?.total_cost.toFixed(0) || 0}`}
                  >
                    ${summary?.total_cost ? Math.round(summary.total_cost / 100) * 100 / 100 : 0}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

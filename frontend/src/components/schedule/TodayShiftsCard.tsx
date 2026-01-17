import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Clock } from "lucide-react";
import type { EmployeeDaySchedule } from "@/types/schedule";

const DAYS_OF_WEEK = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

function formatDateToISO(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

interface TodayShiftsCardProps {
  schedules: EmployeeDaySchedule[];
}

export function TodayShiftsCard({ schedules }: TodayShiftsCardProps) {
  const now = new Date();
  const todayISO = formatDateToISO(now);
  const todayDayOfWeek = DAYS_OF_WEEK[now.getDay()];

  const todaySchedules = schedules
    .filter((s) => {
      if (s.total_hours === 0) return false;
      if (s.date) {
        return s.date === todayISO;
      }
      return s.day_of_week === todayDayOfWeek;
    })
    .sort((a, b) => {
      if (!a.shift_start || !b.shift_start) return 0;
      return a.shift_start.localeCompare(b.shift_start);
    });

  const totalHours = todaySchedules.reduce((sum, s) => sum + s.total_hours, 0);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">
          Today's Shifts ({todayDayOfWeek})
        </CardTitle>
        <Clock className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {todaySchedules.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            No shifts scheduled for today.
          </p>
        ) : (
          <div className="space-y-2">
            {todaySchedules.map((schedule) => (
              <div
                key={schedule.employee_name}
                className="flex items-center justify-between text-sm"
              >
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-500" />
                  <span className="font-medium">{schedule.employee_name}</span>
                </div>
                <span className="text-muted-foreground">
                  {schedule.shift_start} - {schedule.shift_end}
                </span>
              </div>
            ))}
            <div className="pt-2 mt-2 border-t text-sm text-muted-foreground">
              Total: {todaySchedules.length} employees, {totalHours} hours
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

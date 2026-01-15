import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { api, type Employee } from "@/api/client";

export function Employees() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchEmployees() {
      try {
        const data = await api.getEmployees();
        setEmployees(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch employees");
      } finally {
        setLoading(false);
      }
    }
    fetchEmployees();
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Employees</h1>
        <p className="text-muted-foreground mt-1">
          Manage employee information and availability
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Employee List</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading employees...</p>
          ) : error ? (
            <div className="text-destructive">
              <p>{error}</p>
              <p className="text-sm text-muted-foreground mt-2">
                Make sure the backend API is running and has the /employees endpoint.
              </p>
            </div>
          ) : employees.length === 0 ? (
            <p className="text-muted-foreground">No employees found.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Hourly Rate</TableHead>
                  <TableHead>Min Hours/Week</TableHead>
                  <TableHead>Daily Hours</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {employees.map((employee) => (
                  <TableRow key={employee.employee_name}>
                    <TableCell className="font-medium">
                      {employee.employee_name}
                    </TableCell>
                    <TableCell>${employee.hourly_rate.toFixed(2)}</TableCell>
                    <TableCell>{employee.minimum_hours_per_week}h</TableCell>
                    <TableCell>
                      {employee.minimum_hours}h - {employee.maximum_hours}h
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">Active</Badge>
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

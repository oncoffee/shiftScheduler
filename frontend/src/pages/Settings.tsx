import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export function Settings() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Configure application settings
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>API Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium">Backend URL</label>
            <p className="text-sm text-muted-foreground">
              {import.meta.env.VITE_API_URL || "http://localhost:8000"}
            </p>
          </div>
          <Separator />
          <div>
            <label className="text-sm font-medium">Google Sheets Integration</label>
            <p className="text-sm text-muted-foreground">
              Data is sourced from Google Sheets. Configure the sheet in the backend .env file.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>About</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            <strong>Shift Scheduler</strong> - An optimization-based employee scheduling system.
          </p>
          <p>
            Uses Gurobi optimization solver to generate cost-effective schedules
            while respecting employee availability and store requirements.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

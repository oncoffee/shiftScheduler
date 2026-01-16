import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { api, type Config, type SyncResult } from "@/api/client";
import { Loader2, Save, RefreshCw, AlertCircle, CheckCircle2, Database } from "lucide-react";

export function Settings() {
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [formValues, setFormValues] = useState<Config>({
    dummy_worker_cost: 100,
    short_shift_penalty: 50,
    min_shift_hours: 3,
    max_daily_hours: 11,
  });

  // Sync state
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [passKey, setPassKey] = useState("");

  const loadConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getConfig();
      setConfig(data);
      setFormValues(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load config");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfig();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const updated = await api.updateConfig(formValues);
      setConfig(updated);
      setFormValues(updated);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save config");
    } finally {
      setSaving(false);
    }
  };

  const handleSync = async () => {
    if (!passKey) {
      setSyncError("Pass key is required");
      return;
    }
    setSyncing(true);
    setSyncError(null);
    setSyncResult(null);
    try {
      const result = await api.syncAll(passKey);
      setSyncResult(result);
      // Reload config after sync
      loadConfig();
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : "Failed to sync data");
    } finally {
      setSyncing(false);
    }
  };

  const hasChanges =
    config &&
    (formValues.dummy_worker_cost !== config.dummy_worker_cost ||
      formValues.short_shift_penalty !== config.short_shift_penalty ||
      formValues.min_shift_hours !== config.min_shift_hours ||
      formValues.max_daily_hours !== config.max_daily_hours);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Configure solver parameters and application settings
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Solver Configuration</CardTitle>
          <Button variant="ghost" size="sm" onClick={loadConfig} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </CardHeader>
        <CardContent className="space-y-6">
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-lg">
              <AlertCircle className="w-4 h-4" />
              <span className="text-sm">{error}</span>
            </div>
          )}

          {success && (
            <div className="flex items-center gap-2 p-3 bg-green-50 text-green-700 rounded-lg">
              <CheckCircle2 className="w-4 h-4" />
              <span className="text-sm">Configuration saved successfully</span>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : (
            <>
              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Dummy Worker Cost</label>
                  <p className="text-xs text-muted-foreground">
                    Cost per period when no employee is available to fill a slot
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">$</span>
                    <input
                      type="number"
                      value={formValues.dummy_worker_cost}
                      onChange={(e) =>
                        setFormValues((prev) => ({
                          ...prev,
                          dummy_worker_cost: parseFloat(e.target.value) || 0,
                        }))
                      }
                      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus:outline-none focus:ring-1 focus:ring-ring"
                      step="10"
                      min="0"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Short Shift Penalty</label>
                  <p className="text-xs text-muted-foreground">
                    Penalty per hour when a shift is shorter than minimum
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">$</span>
                    <input
                      type="number"
                      value={formValues.short_shift_penalty}
                      onChange={(e) =>
                        setFormValues((prev) => ({
                          ...prev,
                          short_shift_penalty: parseFloat(e.target.value) || 0,
                        }))
                      }
                      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus:outline-none focus:ring-1 focus:ring-ring"
                      step="10"
                      min="0"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Minimum Shift Hours</label>
                  <p className="text-xs text-muted-foreground">
                    Minimum hours for a shift (soft constraint with penalty)
                  </p>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      value={formValues.min_shift_hours}
                      onChange={(e) =>
                        setFormValues((prev) => ({
                          ...prev,
                          min_shift_hours: parseFloat(e.target.value) || 0,
                        }))
                      }
                      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus:outline-none focus:ring-1 focus:ring-ring"
                      step="0.5"
                      min="0"
                    />
                    <span className="text-sm text-muted-foreground">hours</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Maximum Daily Hours</label>
                  <p className="text-xs text-muted-foreground">
                    Maximum hours any employee can work in a single day
                  </p>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      value={formValues.max_daily_hours}
                      onChange={(e) =>
                        setFormValues((prev) => ({
                          ...prev,
                          max_daily_hours: parseFloat(e.target.value) || 0,
                        }))
                      }
                      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus:outline-none focus:ring-1 focus:ring-ring"
                      step="0.5"
                      min="0"
                    />
                    <span className="text-sm text-muted-foreground">hours</span>
                  </div>
                </div>
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">
                  Changes are saved to Google Sheets and apply to the next solver run
                </p>
                <Button onClick={handleSave} disabled={saving || !hasChanges}>
                  {saving ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4 mr-2" />
                  )}
                  Save Changes
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="w-5 h-5" />
            Data Sync
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Sync data from Google Sheets to MongoDB. This will update employees, stores, and configuration.
          </p>

          {syncError && (
            <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-lg">
              <AlertCircle className="w-4 h-4" />
              <span className="text-sm">{syncError}</span>
            </div>
          )}

          {syncResult && (
            <div className="flex items-center gap-2 p-3 bg-green-50 text-green-700 rounded-lg">
              <CheckCircle2 className="w-4 h-4" />
              <span className="text-sm">
                Synced {syncResult.employees_synced} employees, {syncResult.stores_synced} stores
              </span>
            </div>
          )}

          <div className="flex items-end gap-4">
            <div className="flex-1 space-y-2">
              <label className="text-sm font-medium">Pass Key</label>
              <input
                type="password"
                value={passKey}
                onChange={(e) => setPassKey(e.target.value)}
                placeholder="Enter pass key"
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <Button onClick={handleSync} disabled={syncing || !passKey}>
              {syncing ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-2" />
              )}
              Sync from Google Sheets
            </Button>
          </div>
        </CardContent>
      </Card>

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
              Data is sourced from Google Sheets and synced to MongoDB. Use the sync button above to update.
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

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import {
  api,
  type Config,
  type SyncResult,
  type SolverType,
  type ComplianceConfig,
  type ComplianceRuleSuggestion,
  type USState,
} from "@/api/client";
import { Loader2, Save, RefreshCw, AlertCircle, CheckCircle2, Database, Shield, Sparkles, ExternalLink } from "lucide-react";

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
    solver_type: "gurobi",
  });

  // Sync state
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);

  // Compliance state
  const [complianceConfig, setComplianceConfig] = useState<ComplianceConfig | null>(null);
  const [complianceLoading, setComplianceLoading] = useState(false);
  const [complianceSaving, setComplianceSaving] = useState(false);
  const [complianceError, setComplianceError] = useState<string | null>(null);
  const [complianceSuccess, setComplianceSuccess] = useState(false);

  // AI Research state
  const [usStates, setUsStates] = useState<USState[]>([]);
  const [selectedState, setSelectedState] = useState("");
  const [researching, setResearching] = useState(false);
  const [suggestion, setSuggestion] = useState<ComplianceRuleSuggestion | null>(null);
  const [editedSuggestion, setEditedSuggestion] = useState<ComplianceRuleSuggestion | null>(null);
  const [approving, setApproving] = useState(false);
  const [researchError, setResearchError] = useState<string | null>(null);

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

  const loadComplianceConfig = async () => {
    setComplianceLoading(true);
    try {
      const [configData, statesData] = await Promise.all([
        api.getComplianceConfig(),
        api.getUSStates(),
      ]);
      setComplianceConfig(configData);
      setUsStates(statesData);
    } catch (err) {
      setComplianceError(err instanceof Error ? err.message : "Failed to load compliance config");
    } finally {
      setComplianceLoading(false);
    }
  };

  useEffect(() => {
    loadConfig();
    loadComplianceConfig();
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
    setSyncing(true);
    setSyncError(null);
    setSyncResult(null);
    try {
      const result = await api.syncAll();
      setSyncResult(result);
      // Reload config after sync
      loadConfig();
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : "Failed to sync data");
    } finally {
      setSyncing(false);
    }
  };

  const handleSaveComplianceConfig = async (updates: Partial<ComplianceConfig>) => {
    setComplianceSaving(true);
    setComplianceError(null);
    setComplianceSuccess(false);
    try {
      const updated = await api.updateComplianceConfig(updates);
      setComplianceConfig(updated);
      setComplianceSuccess(true);
      setTimeout(() => setComplianceSuccess(false), 3000);
    } catch (err) {
      setComplianceError(err instanceof Error ? err.message : "Failed to save compliance config");
    } finally {
      setComplianceSaving(false);
    }
  };

  const handleResearchState = async () => {
    if (!selectedState) return;
    setResearching(true);
    setResearchError(null);
    setSuggestion(null);
    setEditedSuggestion(null);
    try {
      const result = await api.researchStateCompliance(selectedState);
      setSuggestion(result);
      setEditedSuggestion(result);
    } catch (err) {
      setResearchError(err instanceof Error ? err.message : "Failed to research state laws");
    } finally {
      setResearching(false);
    }
  };

  const handleApproveSuggestion = async () => {
    if (!editedSuggestion) return;
    setApproving(true);
    setResearchError(null);
    try {
      // Pass both edited values and original AI suggestion for audit trail
      await api.approveAISuggestion(editedSuggestion, suggestion || undefined);
      setSuggestion(null);
      setEditedSuggestion(null);
      setSelectedState("");
      setComplianceSuccess(true);
      setTimeout(() => setComplianceSuccess(false), 3000);
    } catch (err) {
      setResearchError(err instanceof Error ? err.message : "Failed to approve suggestion");
    } finally {
      setApproving(false);
    }
  };

  const updateEditedSuggestion = (field: keyof ComplianceRuleSuggestion, value: unknown) => {
    if (!editedSuggestion) return;
    setEditedSuggestion({ ...editedSuggestion, [field]: value });
  };

  const hasChanges =
    config &&
    (formValues.dummy_worker_cost !== config.dummy_worker_cost ||
      formValues.short_shift_penalty !== config.short_shift_penalty ||
      formValues.min_shift_hours !== config.min_shift_hours ||
      formValues.max_daily_hours !== config.max_daily_hours ||
      formValues.solver_type !== config.solver_type);

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

              <div className="space-y-2">
                <label className="text-sm font-medium">Optimization Solver</label>
                <p className="text-xs text-muted-foreground">
                  Select which optimization solver to use for generating schedules
                </p>
                <select
                  value={formValues.solver_type}
                  onChange={(e) =>
                    setFormValues((prev) => ({
                      ...prev,
                      solver_type: e.target.value as SolverType,
                    }))
                  }
                  className="flex h-9 w-full max-w-xs rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  <option value="gurobi">Gurobi (Commercial)</option>
                  <option value="pulp">PuLP/CBC (Open Source)</option>
                  <option value="ortools">Google OR-Tools (Open Source)</option>
                </select>
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
            <Shield className="w-5 h-5" />
            Labor Law Compliance
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {complianceError && (
            <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-lg">
              <AlertCircle className="w-4 h-4" />
              <span className="text-sm">{complianceError}</span>
            </div>
          )}

          {complianceSuccess && (
            <div className="flex items-center gap-2 p-3 bg-green-50 text-green-700 rounded-lg">
              <CheckCircle2 className="w-4 h-4" />
              <span className="text-sm">Compliance settings saved successfully</span>
            </div>
          )}

          {complianceLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : complianceConfig && (
            <>
              <div className="space-y-2">
                <label className="text-sm font-medium">Compliance Mode</label>
                <p className="text-xs text-muted-foreground">
                  Control how compliance violations are handled
                </p>
                <select
                  value={complianceConfig.compliance_mode}
                  onChange={(e) =>
                    handleSaveComplianceConfig({
                      compliance_mode: e.target.value as "off" | "warn" | "enforce",
                    })
                  }
                  disabled={complianceSaving}
                  className="flex h-9 w-full max-w-xs rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  <option value="off">Off - No compliance checks</option>
                  <option value="warn">Warn - Flag violations but allow scheduling</option>
                  <option value="enforce">Enforce - Block non-compliant schedules</option>
                </select>
              </div>

              <Separator />

              <div className="space-y-4">
                <label className="text-sm font-medium">Enabled Compliance Checks</label>
                <div className="grid gap-3 md:grid-cols-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={complianceConfig.enable_rest_between_shifts}
                      onChange={(e) =>
                        handleSaveComplianceConfig({
                          enable_rest_between_shifts: e.target.checked,
                        })
                      }
                      disabled={complianceSaving}
                      className="rounded border-gray-300"
                    />
                    <span className="text-sm">Rest Between Shifts</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={complianceConfig.enable_minor_restrictions}
                      onChange={(e) =>
                        handleSaveComplianceConfig({
                          enable_minor_restrictions: e.target.checked,
                        })
                      }
                      disabled={complianceSaving}
                      className="rounded border-gray-300"
                    />
                    <span className="text-sm">Minor Restrictions (Under 18)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={complianceConfig.enable_overtime_tracking}
                      onChange={(e) =>
                        handleSaveComplianceConfig({
                          enable_overtime_tracking: e.target.checked,
                        })
                      }
                      disabled={complianceSaving}
                      className="rounded border-gray-300"
                    />
                    <span className="text-sm">Overtime Tracking</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={complianceConfig.enable_break_compliance}
                      onChange={(e) =>
                        handleSaveComplianceConfig({
                          enable_break_compliance: e.target.checked,
                        })
                      }
                      disabled={complianceSaving}
                      className="rounded border-gray-300"
                    />
                    <span className="text-sm">Break Compliance</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={complianceConfig.enable_predictive_scheduling}
                      onChange={(e) =>
                        handleSaveComplianceConfig({
                          enable_predictive_scheduling: e.target.checked,
                        })
                      }
                      disabled={complianceSaving}
                      className="rounded border-gray-300"
                    />
                    <span className="text-sm">Predictive Scheduling</span>
                  </label>
                </div>
              </div>

              <Separator />

              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-blue-500" />
                  <label className="text-sm font-medium">AI-Powered Rule Research</label>
                </div>
                <p className="text-xs text-muted-foreground">
                  Use AI to research state-specific labor laws and suggest compliance rules
                </p>

                <div className="flex items-end gap-4">
                  <div className="flex-1 space-y-2">
                    <label className="text-sm font-medium">State</label>
                    <select
                      value={selectedState}
                      onChange={(e) => {
                        setSelectedState(e.target.value);
                        setSuggestion(null);
                        setResearchError(null);
                      }}
                      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus:outline-none focus:ring-1 focus:ring-ring"
                    >
                      <option value="">Select a state...</option>
                      {usStates.map((state) => (
                        <option key={state.code} value={state.code}>
                          {state.name} ({state.code})
                        </option>
                      ))}
                    </select>
                  </div>
                  <Button
                    onClick={handleResearchState}
                    disabled={!selectedState || researching}
                    variant="outline"
                  >
                    {researching ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <Sparkles className="w-4 h-4 mr-2" />
                    )}
                    Research Laws
                  </Button>
                </div>

                {researchError && (
                  <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-lg">
                    <AlertCircle className="w-4 h-4" />
                    <span className="text-sm">{researchError}</span>
                  </div>
                )}

                {suggestion && (
                  <Card className={`border-2 ${
                    suggestion.confidence_level === "high" ? "border-green-200 bg-green-50/30" :
                    suggestion.confidence_level === "medium" ? "border-blue-200 bg-blue-50/30" :
                    "border-amber-200 bg-amber-50/30"
                  }`}>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge variant="secondary" className="bg-blue-100 text-blue-700">
                            AI Suggested
                          </Badge>
                          <Badge variant="secondary" className={
                            suggestion.confidence_level === "high" ? "bg-green-100 text-green-700" :
                            suggestion.confidence_level === "medium" ? "bg-blue-100 text-blue-700" :
                            "bg-amber-100 text-amber-700"
                          }>
                            {suggestion.confidence_level.toUpperCase()} Confidence
                          </Badge>
                          <CardTitle className="text-base">
                            Suggested Rules for {suggestion.state_name}
                          </CardTitle>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      {/* Disclaimer Banner */}
                      <div className={`p-3 rounded-lg text-xs ${
                        suggestion.confidence_level === "low" ? "bg-red-100 text-red-800 border border-red-200" :
                        suggestion.confidence_level === "medium" ? "bg-amber-100 text-amber-800 border border-amber-200" :
                        "bg-blue-100 text-blue-800 border border-blue-200"
                      }`}>
                        <div className="flex items-start gap-2">
                          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                          <span>{suggestion.disclaimer}</span>
                        </div>
                      </div>

                      {/* Validation Warnings */}
                      {suggestion.validation_warnings && suggestion.validation_warnings.length > 0 && (
                        <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
                          <div className="flex items-center gap-2 text-amber-800 font-medium mb-2">
                            <AlertCircle className="w-4 h-4" />
                            Validation Warnings
                          </div>
                          <ul className="space-y-1 text-xs text-amber-700">
                            {suggestion.validation_warnings.map((warning, i) => (
                              <li key={i} className="flex items-start gap-1">
                                <span className="text-amber-500">•</span>
                                {warning}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-1">
                          <label className="text-xs text-muted-foreground">Min Rest Between Shifts (hours)</label>
                          <input
                            type="number"
                            step="0.5"
                            min="0"
                            max="24"
                            value={editedSuggestion?.min_rest_hours ?? ""}
                            onChange={(e) => updateEditedSuggestion("min_rest_hours", e.target.value ? parseFloat(e.target.value) : null)}
                            placeholder="N/A"
                            className="flex h-8 w-full rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-muted-foreground">Minor Curfew (HH:MM)</label>
                          <input
                            type="time"
                            value={editedSuggestion?.minor_curfew_end ?? ""}
                            onChange={(e) => updateEditedSuggestion("minor_curfew_end", e.target.value || null)}
                            className="flex h-8 w-full rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-muted-foreground">Minor Earliest Start (HH:MM)</label>
                          <input
                            type="time"
                            value={editedSuggestion?.minor_earliest_start ?? ""}
                            onChange={(e) => updateEditedSuggestion("minor_earliest_start", e.target.value || null)}
                            className="flex h-8 w-full rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-muted-foreground">Minor Max Daily Hours</label>
                          <input
                            type="number"
                            step="0.5"
                            min="0"
                            max="24"
                            value={editedSuggestion?.minor_max_daily_hours ?? ""}
                            onChange={(e) => updateEditedSuggestion("minor_max_daily_hours", e.target.value ? parseFloat(e.target.value) : null)}
                            placeholder="N/A"
                            className="flex h-8 w-full rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-muted-foreground">Minor Max Weekly Hours</label>
                          <input
                            type="number"
                            step="1"
                            min="0"
                            max="80"
                            value={editedSuggestion?.minor_max_weekly_hours ?? ""}
                            onChange={(e) => updateEditedSuggestion("minor_max_weekly_hours", e.target.value ? parseFloat(e.target.value) : null)}
                            placeholder="N/A"
                            className="flex h-8 w-full rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-muted-foreground">Daily OT Threshold (hours, blank = none)</label>
                          <input
                            type="number"
                            step="0.5"
                            min="0"
                            max="24"
                            value={editedSuggestion?.daily_overtime_threshold ?? ""}
                            onChange={(e) => updateEditedSuggestion("daily_overtime_threshold", e.target.value ? parseFloat(e.target.value) : null)}
                            placeholder="None"
                            className="flex h-8 w-full rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-muted-foreground">Weekly OT Threshold (hours)</label>
                          <input
                            type="number"
                            step="1"
                            min="0"
                            max="80"
                            value={editedSuggestion?.weekly_overtime_threshold ?? 40}
                            onChange={(e) => updateEditedSuggestion("weekly_overtime_threshold", e.target.value ? parseFloat(e.target.value) : 40)}
                            className="flex h-8 w-full rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-muted-foreground">Meal Break After (hours)</label>
                          <input
                            type="number"
                            step="0.5"
                            min="0"
                            max="12"
                            value={editedSuggestion?.meal_break_after_hours ?? ""}
                            onChange={(e) => updateEditedSuggestion("meal_break_after_hours", e.target.value ? parseFloat(e.target.value) : null)}
                            placeholder="N/A"
                            className="flex h-8 w-full rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-muted-foreground">Meal Break Duration (minutes)</label>
                          <input
                            type="number"
                            step="5"
                            min="0"
                            max="120"
                            value={editedSuggestion?.meal_break_duration_minutes ?? ""}
                            onChange={(e) => updateEditedSuggestion("meal_break_duration_minutes", e.target.value ? parseInt(e.target.value) : null)}
                            placeholder="N/A"
                            className="flex h-8 w-full rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-xs text-muted-foreground">Advance Notice (days)</label>
                          <input
                            type="number"
                            step="1"
                            min="0"
                            max="30"
                            value={editedSuggestion?.advance_notice_days ?? ""}
                            onChange={(e) => updateEditedSuggestion("advance_notice_days", e.target.value ? parseInt(e.target.value) : null)}
                            placeholder="N/A"
                            className="flex h-8 w-full rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
                          />
                        </div>
                      </div>

                      {suggestion.sources.length > 0 && (
                        <div className="pt-2">
                          <span className="text-muted-foreground font-medium">Sources:</span>
                          <ul className="mt-1 space-y-1">
                            {suggestion.sources.map((source, i) => {
                              // Check if source is a URL
                              const isUrl = source.startsWith("http://") || source.startsWith("https://");
                              // Generate a search URL for non-URL sources
                              const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(source + " " + suggestion.state_name + " labor law")}`;

                              return (
                                <li key={i} className="flex items-start gap-1 text-xs">
                                  <ExternalLink className="w-3 h-3 mt-0.5 flex-shrink-0 text-blue-500" />
                                  {isUrl ? (
                                    <a
                                      href={source}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-blue-600 hover:text-blue-800 hover:underline"
                                    >
                                      {source}
                                    </a>
                                  ) : (
                                    <a
                                      href={searchUrl}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-blue-600 hover:text-blue-800 hover:underline"
                                      title="Search for this source"
                                    >
                                      {source}
                                    </a>
                                  )}
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      )}

                      {suggestion.sources.length === 0 && (
                        <div className="pt-2 text-xs text-red-600 bg-red-50 p-2 rounded border border-red-200">
                          <strong>Warning:</strong> No sources provided. Manual verification strongly recommended.
                        </div>
                      )}

                      {suggestion.notes && (
                        <div className="pt-2 text-xs text-gray-700 bg-gray-50 p-2 rounded">
                          <strong>Notes:</strong> {suggestion.notes}
                        </div>
                      )}

                      <div className="pt-2 text-xs text-muted-foreground">
                        Model: {suggestion.model_used}
                      </div>
                    </CardContent>
                    <CardFooter className="flex justify-between border-t pt-4">
                      <div className="flex items-center gap-2 text-xs text-amber-600">
                        <AlertCircle className="w-4 h-4" />
                        Human review required before approval
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSuggestion(null);
                            setEditedSuggestion(null);
                          }}
                        >
                          Cancel
                        </Button>
                        <Button
                          size="sm"
                          onClick={handleApproveSuggestion}
                          disabled={approving}
                          variant={suggestion.confidence_level === "low" ? "destructive" : "default"}
                        >
                          {approving ? (
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          ) : (
                            <CheckCircle2 className="w-4 h-4 mr-2" />
                          )}
                          {suggestion.confidence_level === "low" ? "Approve Anyway" : "Approve & Save"}
                        </Button>
                      </div>
                    </CardFooter>
                  </Card>
                )}
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

          <Button onClick={handleSync} disabled={syncing}>
            {syncing ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            Sync from Google Sheets
          </Button>
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
            Supports multiple optimization solvers to generate cost-effective schedules
            while respecting employee availability and store requirements:
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li><strong>Gurobi</strong> - Commercial solver with excellent performance</li>
            <li><strong>PuLP/CBC</strong> - Open source linear programming solver</li>
            <li><strong>Google OR-Tools</strong> - Open source constraint programming solver</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

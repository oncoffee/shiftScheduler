import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
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
  api,
  type ComplianceValidationResult,
  type ComplianceRule,
  type ComplianceRuleSuggestion,
  type ComplianceAuditRecord,
} from "@/api/client";
import {
  Loader2,
  RefreshCw,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Shield,
  Clock,
  Users,
  Timer,
  Coffee,
  Calendar,
  Sparkles,
  ExternalLink,
  History,
} from "lucide-react";

type ViolationFilter = "all" | "error" | "warning";

export function Compliance() {
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationResult, setValidationResult] = useState<ComplianceValidationResult | null>(null);
  const [rules, setRules] = useState<ComplianceRule[]>([]);
  const [filter, setFilter] = useState<ViolationFilter>("all");

  // AI refresh state
  const [refreshingJurisdiction, setRefreshingJurisdiction] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState<ComplianceRuleSuggestion | null>(null);
  const [editedSuggestion, setEditedSuggestion] = useState<ComplianceRuleSuggestion | null>(null);
  const [currentRule, setCurrentRule] = useState<ComplianceRule | null>(null);
  const [approving, setApproving] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  // Audit drawer state
  const [auditDrawerOpen, setAuditDrawerOpen] = useState(false);
  const [auditHistory, setAuditHistory] = useState<ComplianceAuditRecord[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [selectedAudit, setSelectedAudit] = useState<ComplianceAuditRecord | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const rulesData = await api.getComplianceRules();
      setRules(rulesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load compliance data");
    } finally {
      setLoading(false);
    }
  };

  const validateCurrentSchedule = async () => {
    setValidating(true);
    setError(null);
    try {
      const schedule = await api.getScheduleResults();
      if (!schedule) {
        setError("No current schedule to validate");
        return;
      }
      // Get schedule ID from history
      const history = await api.getScheduleHistory(1, 0);
      const currentSchedule = history.find(h => h.is_current);
      if (!currentSchedule) {
        setError("No current schedule found");
        return;
      }
      const result = await api.validateScheduleCompliance(currentSchedule.id);
      setValidationResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to validate schedule");
    } finally {
      setValidating(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefreshLaws = async (rule: ComplianceRule) => {
    setRefreshingJurisdiction(rule.jurisdiction);
    setRefreshError(null);
    setSuggestion(null);
    setEditedSuggestion(null);
    setCurrentRule(rule);
    try {
      const result = await api.researchStateCompliance(rule.jurisdiction);
      setSuggestion(result);
      setEditedSuggestion(result);
    } catch (err) {
      setRefreshError(err instanceof Error ? err.message : "Failed to research laws");
    } finally {
      setRefreshingJurisdiction(null);
    }
  };

  const handleApproveSuggestion = async () => {
    if (!editedSuggestion) return;
    setApproving(true);
    setRefreshError(null);
    try {
      await api.approveAISuggestion(editedSuggestion, suggestion || undefined);
      setSuggestion(null);
      setEditedSuggestion(null);
      setCurrentRule(null);
      loadData(); // Refresh rules list
    } catch (err) {
      setRefreshError(err instanceof Error ? err.message : "Failed to approve suggestion");
    } finally {
      setApproving(false);
    }
  };

  const updateEditedSuggestion = (field: keyof ComplianceRuleSuggestion, value: unknown) => {
    if (!editedSuggestion) return;
    setEditedSuggestion({ ...editedSuggestion, [field]: value });
  };

  const loadAuditHistory = async () => {
    setAuditLoading(true);
    try {
      const history = await api.getComplianceAuditHistory();
      setAuditHistory(history);
    } catch (err) {
      console.error("Failed to load audit history:", err);
    } finally {
      setAuditLoading(false);
    }
  };

  const openAuditDrawer = () => {
    setAuditDrawerOpen(true);
    loadAuditHistory();
  };

  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const filteredViolations = validationResult?.violations.filter((v) => {
    if (filter === "all") return true;
    return v.severity === filter;
  }) ?? [];

  const getViolationIcon = (type: string) => {
    switch (type) {
      case "MINOR_CURFEW":
      case "MINOR_EARLY_START":
      case "MINOR_DAILY_HOURS":
      case "MINOR_WEEKLY_HOURS":
        return <Users className="w-4 h-4" />;
      case "REST_VIOLATION":
        return <Clock className="w-4 h-4" />;
      case "DAILY_OVERTIME":
      case "WEEKLY_OVERTIME":
        return <Timer className="w-4 h-4" />;
      case "MEAL_BREAK_REQUIRED":
      case "REST_BREAK_REQUIRED":
        return <Coffee className="w-4 h-4" />;
      case "PREDICTIVE_NOTICE":
        return <Calendar className="w-4 h-4" />;
      default:
        return <AlertCircle className="w-4 h-4" />;
    }
  };

  const getViolationTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      MINOR_CURFEW: "Minor Curfew",
      MINOR_EARLY_START: "Minor Early Start",
      MINOR_DAILY_HOURS: "Minor Daily Hours",
      MINOR_WEEKLY_HOURS: "Minor Weekly Hours",
      REST_VIOLATION: "Rest Between Shifts",
      DAILY_OVERTIME: "Daily Overtime",
      WEEKLY_OVERTIME: "Weekly Overtime",
      MEAL_BREAK_REQUIRED: "Meal Break Required",
      REST_BREAK_REQUIRED: "Rest Break Required",
      PREDICTIVE_NOTICE: "Predictive Scheduling",
    };
    return labels[type] || type;
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Shield className="w-8 h-8" />
            Compliance Dashboard
          </h1>
          <p className="text-muted-foreground mt-1">
            Monitor labor law compliance and violations
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={openAuditDrawer}>
            <History className="w-4 h-4 mr-2" />
            Audit Trail
          </Button>
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button onClick={validateCurrentSchedule} disabled={validating}>
            {validating ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Shield className="w-4 h-4 mr-2" />
            )}
            Validate Schedule
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-50 text-red-700 rounded-lg">
          <AlertCircle className="w-5 h-5" />
          <span>{error}</span>
        </div>
      )}

      {/* Summary Cards */}
      {validationResult && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                {validationResult.is_compliant ? (
                  <CheckCircle2 className="w-10 h-10 text-green-500" />
                ) : (
                  <AlertTriangle className="w-10 h-10 text-amber-500" />
                )}
                <div>
                  <p className="text-2xl font-bold">
                    {validationResult.is_compliant ? "Compliant" : "Issues Found"}
                  </p>
                  <p className="text-sm text-muted-foreground">Overall Status</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-full bg-red-100">
                  <AlertCircle className="w-6 h-6 text-red-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{validationResult.error_count}</p>
                  <p className="text-sm text-muted-foreground">Errors</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-full bg-amber-100">
                  <AlertTriangle className="w-6 h-6 text-amber-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{validationResult.warning_count}</p>
                  <p className="text-sm text-muted-foreground">Warnings</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-full bg-blue-100">
                  <Timer className="w-6 h-6 text-blue-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">
                    {Object.values(validationResult.overtime_hours).reduce((a, b) => a + b, 0).toFixed(1)}h
                  </p>
                  <p className="text-sm text-muted-foreground">Total Overtime</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Violations Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Compliance Violations</CardTitle>
          <div className="flex gap-2">
            <Button
              variant={filter === "all" ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter("all")}
            >
              All
            </Button>
            <Button
              variant={filter === "error" ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter("error")}
            >
              Errors
            </Button>
            <Button
              variant={filter === "warning" ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter("warning")}
            >
              Warnings
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {!validationResult ? (
            <div className="text-center py-8 text-muted-foreground">
              <Shield className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>Click "Validate Schedule" to check compliance</p>
            </div>
          ) : filteredViolations.length === 0 ? (
            <div className="text-center py-8 text-green-600">
              <CheckCircle2 className="w-12 h-12 mx-auto mb-4" />
              <p>No violations found</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Severity</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Employee</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredViolations.map((violation, idx) => (
                  <TableRow key={idx}>
                    <TableCell>
                      <Badge
                        variant={violation.severity === "error" ? "destructive" : "secondary"}
                        className={violation.severity === "warning" ? "bg-amber-100 text-amber-800" : ""}
                      >
                        {violation.severity === "error" ? (
                          <AlertCircle className="w-3 h-3 mr-1" />
                        ) : (
                          <AlertTriangle className="w-3 h-3 mr-1" />
                        )}
                        {violation.severity}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getViolationIcon(violation.rule_type)}
                        {getViolationTypeLabel(violation.rule_type)}
                      </div>
                    </TableCell>
                    <TableCell className="font-medium">{violation.employee_name}</TableCell>
                    <TableCell>{violation.date || "-"}</TableCell>
                    <TableCell className="max-w-md">
                      <p className="text-sm text-muted-foreground truncate" title={violation.message}>
                        {violation.message}
                      </p>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Weekly Hours Summary */}
      {validationResult && Object.keys(validationResult.employee_weekly_hours).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Weekly Hours Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employee</TableHead>
                  <TableHead>Weekly Hours</TableHead>
                  <TableHead>Overtime Hours</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.entries(validationResult.employee_weekly_hours)
                  .sort((a, b) => b[1] - a[1])
                  .map(([employee, hours]) => {
                    const overtime = validationResult.overtime_hours[employee] || 0;
                    return (
                      <TableRow key={employee}>
                        <TableCell className="font-medium">{employee}</TableCell>
                        <TableCell>{hours.toFixed(1)}h</TableCell>
                        <TableCell>
                          {overtime > 0 ? (
                            <span className="text-amber-600 font-medium">{overtime.toFixed(1)}h</span>
                          ) : (
                            "-"
                          )}
                        </TableCell>
                        <TableCell>
                          {overtime > 0 ? (
                            <Badge variant="secondary" className="bg-amber-100 text-amber-800">
                              Overtime
                            </Badge>
                          ) : hours >= 40 ? (
                            <Badge variant="secondary">Full Time</Badge>
                          ) : (
                            <Badge variant="outline">Part Time</Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Active Compliance Rules */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Active Compliance Rules
            <Badge variant="outline" className="ml-2">
              <History className="w-3 h-3 mr-1" />
              Audit Trail Enabled
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : rules.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p>No compliance rules configured</p>
              <p className="text-sm mt-2">
                Go to Settings to configure compliance rules for your jurisdiction
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Jurisdiction</TableHead>
                  <TableHead>Min Rest</TableHead>
                  <TableHead>Minor Curfew</TableHead>
                  <TableHead>Daily OT</TableHead>
                  <TableHead>Weekly OT</TableHead>
                  <TableHead>Meal Break</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.map((rule) => (
                  <TableRow key={rule.jurisdiction}>
                    <TableCell className="font-medium">{rule.jurisdiction}</TableCell>
                    <TableCell>{rule.min_rest_hours}h</TableCell>
                    <TableCell>{rule.minor_curfew_end}</TableCell>
                    <TableCell>{rule.daily_overtime_threshold ?? "-"}h</TableCell>
                    <TableCell>{rule.weekly_overtime_threshold}h</TableCell>
                    <TableCell>After {rule.meal_break_after_hours}h</TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {rule.source === "AI_SUGGESTED" ? "AI" : rule.source || "Manual"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRefreshLaws(rule)}
                        disabled={refreshingJurisdiction === rule.jurisdiction}
                      >
                        {refreshingJurisdiction === rule.jurisdiction ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Sparkles className="w-4 h-4" />
                        )}
                        <span className="ml-1">Refresh</span>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* AI Suggestion Modal */}
      {suggestion && currentRule && (
        <Card className={`border-2 ${
          suggestion.confidence_level === "high" ? "border-green-200 bg-green-50/30" :
          suggestion.confidence_level === "medium" ? "border-blue-200 bg-blue-50/30" :
          "border-amber-200 bg-amber-50/30"
        }`}>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="bg-blue-100 text-blue-700">
                  <Sparkles className="w-3 h-3 mr-1" />
                  AI Update
                </Badge>
                <Badge variant="secondary" className={
                  suggestion.confidence_level === "high" ? "bg-green-100 text-green-700" :
                  suggestion.confidence_level === "medium" ? "bg-blue-100 text-blue-700" :
                  "bg-amber-100 text-amber-700"
                }>
                  {suggestion.confidence_level.toUpperCase()} Confidence
                </Badge>
                <CardTitle className="text-base">
                  Updated Rules for {suggestion.state_name} ({currentRule.jurisdiction})
                </CardTitle>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSuggestion(null);
                  setEditedSuggestion(null);
                  setCurrentRule(null);
                }}
              >
                ✕
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            {/* Disclaimer */}
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

            {refreshError && (
              <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-lg">
                <AlertCircle className="w-4 h-4" />
                <span>{refreshError}</span>
              </div>
            )}

            {/* Comparison Table */}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Rule</TableHead>
                  <TableHead>Current Value</TableHead>
                  <TableHead>AI Suggested</TableHead>
                  <TableHead>Your Value</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell className="font-medium">Min Rest Hours</TableCell>
                  <TableCell>{currentRule.min_rest_hours}h</TableCell>
                  <TableCell>{suggestion.min_rest_hours ?? "N/A"}h</TableCell>
                  <TableCell>
                    <input
                      type="number"
                      step="0.5"
                      min="0"
                      max="24"
                      value={editedSuggestion?.min_rest_hours ?? ""}
                      onChange={(e) => updateEditedSuggestion("min_rest_hours", e.target.value ? parseFloat(e.target.value) : null)}
                      className="w-20 px-2 py-1 border rounded text-sm"
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Minor Curfew</TableCell>
                  <TableCell>{currentRule.minor_curfew_end}</TableCell>
                  <TableCell>{suggestion.minor_curfew_end ?? "N/A"}</TableCell>
                  <TableCell>
                    <input
                      type="time"
                      value={editedSuggestion?.minor_curfew_end ?? ""}
                      onChange={(e) => updateEditedSuggestion("minor_curfew_end", e.target.value || null)}
                      className="w-28 px-2 py-1 border rounded text-sm"
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Minor Earliest Start</TableCell>
                  <TableCell>{currentRule.minor_earliest_start}</TableCell>
                  <TableCell>{suggestion.minor_earliest_start ?? "N/A"}</TableCell>
                  <TableCell>
                    <input
                      type="time"
                      value={editedSuggestion?.minor_earliest_start ?? ""}
                      onChange={(e) => updateEditedSuggestion("minor_earliest_start", e.target.value || null)}
                      className="w-28 px-2 py-1 border rounded text-sm"
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Daily OT Threshold</TableCell>
                  <TableCell>{currentRule.daily_overtime_threshold ?? "-"}h</TableCell>
                  <TableCell>{suggestion.daily_overtime_threshold ?? "None"}h</TableCell>
                  <TableCell>
                    <input
                      type="number"
                      step="0.5"
                      min="0"
                      max="24"
                      value={editedSuggestion?.daily_overtime_threshold ?? ""}
                      onChange={(e) => updateEditedSuggestion("daily_overtime_threshold", e.target.value ? parseFloat(e.target.value) : null)}
                      placeholder="None"
                      className="w-20 px-2 py-1 border rounded text-sm"
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Weekly OT Threshold</TableCell>
                  <TableCell>{currentRule.weekly_overtime_threshold}h</TableCell>
                  <TableCell>{suggestion.weekly_overtime_threshold ?? 40}h</TableCell>
                  <TableCell>
                    <input
                      type="number"
                      step="1"
                      min="0"
                      max="80"
                      value={editedSuggestion?.weekly_overtime_threshold ?? 40}
                      onChange={(e) => updateEditedSuggestion("weekly_overtime_threshold", e.target.value ? parseFloat(e.target.value) : 40)}
                      className="w-20 px-2 py-1 border rounded text-sm"
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Meal Break After</TableCell>
                  <TableCell>{currentRule.meal_break_after_hours}h</TableCell>
                  <TableCell>{suggestion.meal_break_after_hours ?? "N/A"}h</TableCell>
                  <TableCell>
                    <input
                      type="number"
                      step="0.5"
                      min="0"
                      max="12"
                      value={editedSuggestion?.meal_break_after_hours ?? ""}
                      onChange={(e) => updateEditedSuggestion("meal_break_after_hours", e.target.value ? parseFloat(e.target.value) : null)}
                      className="w-20 px-2 py-1 border rounded text-sm"
                    />
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>

            {/* Sources */}
            {suggestion.sources.length > 0 && (
              <div className="pt-2">
                <span className="text-muted-foreground font-medium">Sources:</span>
                <ul className="mt-1 space-y-1">
                  {suggestion.sources.map((source, i) => {
                    const isUrl = source.startsWith("http://") || source.startsWith("https://");
                    const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(source + " " + suggestion.state_name + " labor law")}`;
                    return (
                      <li key={i} className="flex items-start gap-1 text-xs">
                        <ExternalLink className="w-3 h-3 mt-0.5 flex-shrink-0 text-blue-500" />
                        <a
                          href={isUrl ? source : searchUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          {source}
                        </a>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {suggestion.notes && (
              <div className="pt-2 text-xs text-gray-700 bg-gray-50 p-2 rounded">
                <strong>Notes:</strong> {suggestion.notes}
              </div>
            )}
          </CardContent>
          <CardFooter className="flex justify-between border-t pt-4">
            <div className="flex items-center gap-2 text-xs text-amber-600">
              <AlertCircle className="w-4 h-4" />
              Changes will be tracked in audit trail
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSuggestion(null);
                  setEditedSuggestion(null);
                  setCurrentRule(null);
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
                {suggestion.confidence_level === "low" ? "Approve Anyway" : "Save & Approve"}
              </Button>
            </div>
          </CardFooter>
        </Card>
      )}

      {/* Audit Trail Drawer */}
      {auditDrawerOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/30 z-40"
            onClick={() => {
              setAuditDrawerOpen(false);
              setSelectedAudit(null);
            }}
          />

          {/* Drawer */}
          <div className="fixed right-0 top-0 h-full w-[500px] bg-white shadow-xl z-50 flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b bg-gray-50">
              <div className="flex items-center gap-2">
                <History className="w-5 h-5 text-gray-600" />
                <h2 className="text-lg font-semibold">Audit Trail</h2>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setAuditDrawerOpen(false);
                  setSelectedAudit(null);
                }}
              >
                ✕
              </Button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
              {auditLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                </div>
              ) : auditHistory.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <History className="w-12 h-12 mx-auto mb-4 opacity-30" />
                  <p>No audit history yet</p>
                  <p className="text-sm mt-1">
                    Changes to compliance rules will appear here
                  </p>
                </div>
              ) : selectedAudit ? (
                /* Detail View */
                <div className="p-4 space-y-4">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedAudit(null)}
                    className="mb-2"
                  >
                    ← Back to list
                  </Button>

                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <Badge className="text-lg px-3 py-1">{selectedAudit.jurisdiction}</Badge>
                      <span className="text-sm text-muted-foreground">
                        {formatDate(selectedAudit.approved_at)}
                      </span>
                    </div>

                    {/* AI Info */}
                    <Card>
                      <CardHeader className="py-3">
                        <CardTitle className="text-sm flex items-center gap-2">
                          <Sparkles className="w-4 h-4 text-blue-500" />
                          AI Suggestion
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="py-2 text-sm space-y-2">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Model:</span>
                          <span>{selectedAudit.ai_model_used || "Unknown"}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Confidence:</span>
                          <Badge variant="outline" className={
                            selectedAudit.ai_confidence_level === "high" ? "bg-green-50 text-green-700" :
                            selectedAudit.ai_confidence_level === "medium" ? "bg-blue-50 text-blue-700" :
                            "bg-amber-50 text-amber-700"
                          }>
                            {selectedAudit.ai_confidence_level}
                          </Badge>
                        </div>
                        {selectedAudit.ai_sources.length > 0 && (
                          <div>
                            <span className="text-muted-foreground">Sources:</span>
                            <ul className="mt-1 space-y-1">
                              {selectedAudit.ai_sources.map((source, i) => (
                                <li key={i} className="text-xs text-blue-600 truncate">
                                  {source}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </CardContent>
                    </Card>

                    {/* Human Edits */}
                    <Card>
                      <CardHeader className="py-3">
                        <CardTitle className="text-sm flex items-center gap-2">
                          <Users className="w-4 h-4 text-purple-500" />
                          Human Edits
                          {selectedAudit.edit_count > 0 && (
                            <Badge variant="secondary">{selectedAudit.edit_count} changes</Badge>
                          )}
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="py-2">
                        {selectedAudit.human_edits.length === 0 ? (
                          <p className="text-sm text-muted-foreground">
                            No changes made - AI suggestion approved as-is
                          </p>
                        ) : (
                          <div className="space-y-2">
                            {selectedAudit.human_edits.map((edit, i) => (
                              <div key={i} className="flex items-center gap-2 text-sm p-2 bg-amber-50 rounded">
                                <span className="font-medium">{edit.field_name}:</span>
                                <span className="text-red-600 line-through">{edit.original_value ?? "null"}</span>
                                <span>→</span>
                                <span className="text-green-600 font-medium">{edit.edited_value ?? "null"}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </CardContent>
                    </Card>

                    {/* Final Values */}
                    <Card>
                      <CardHeader className="py-3">
                        <CardTitle className="text-sm flex items-center gap-2">
                          <CheckCircle2 className="w-4 h-4 text-green-500" />
                          Approved Values
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="py-2">
                        <div className="grid grid-cols-2 gap-2 text-sm">
                          {Object.entries(selectedAudit.approved_values).map(([key, value]) => (
                            <div key={key} className="flex justify-between">
                              <span className="text-muted-foreground">{key}:</span>
                              <span className="font-mono">{String(value)}</span>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>

                    {/* Metadata */}
                    {selectedAudit.ip_address && (
                      <div className="text-xs text-muted-foreground pt-2 border-t">
                        <p>IP: {selectedAudit.ip_address}</p>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                /* List View */
                <div className="divide-y">
                  {auditHistory.map((audit) => (
                    <div
                      key={audit.id}
                      className="p-4 hover:bg-gray-50 cursor-pointer transition-colors"
                      onClick={() => setSelectedAudit(audit)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <Badge>{audit.jurisdiction}</Badge>
                        <span className="text-xs text-muted-foreground">
                          {formatDate(audit.approved_at)}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-sm">
                        <div className="flex items-center gap-1">
                          <Sparkles className="w-3 h-3 text-blue-500" />
                          <span className={
                            audit.ai_confidence_level === "high" ? "text-green-600" :
                            audit.ai_confidence_level === "medium" ? "text-blue-600" :
                            "text-amber-600"
                          }>
                            {audit.ai_confidence_level}
                          </span>
                        </div>
                        {audit.edit_count > 0 ? (
                          <div className="flex items-center gap-1 text-amber-600">
                            <Users className="w-3 h-3" />
                            <span>{audit.edit_count} edits</span>
                          </div>
                        ) : (
                          <span className="text-green-600 text-xs">Approved as-is</span>
                        )}
                      </div>
                      {audit.ai_validation_warnings.length > 0 && (
                        <div className="mt-2 text-xs text-amber-600">
                          ⚠️ {audit.ai_validation_warnings.length} warnings
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="border-t p-4 bg-gray-50">
              <p className="text-xs text-muted-foreground text-center">
                All compliance rule changes are tracked for legal accountability
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

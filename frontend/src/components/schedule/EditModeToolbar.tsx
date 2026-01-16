import { Button } from "@/components/ui/button";
import { Undo2, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { useScheduleEditContext } from "@/contexts/ScheduleEditContext";

export function EditModeToolbar() {
  const { saveStatus, canUndo, undo, isSaving } = useScheduleEditContext();

  if (!canUndo && saveStatus === "idle") {
    return null;
  }

  return (
    <div className="flex items-center gap-2 p-2 bg-blue-50 rounded-lg border border-blue-200">
      <Button
        variant="ghost"
        size="sm"
        onClick={undo}
        disabled={!canUndo || isSaving}
        className="text-gray-600"
      >
        <Undo2 className="h-4 w-4 mr-1" />
        Undo
      </Button>

      {saveStatus !== "idle" && (
        <>
          <div className="h-6 w-px bg-blue-200" />
          <div className="flex items-center gap-1 text-sm">
            {saveStatus === "saving" && (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                <span className="text-blue-600">Saving...</span>
              </>
            )}
            {saveStatus === "saved" && (
              <>
                <CheckCircle className="h-4 w-4 text-green-500" />
                <span className="text-green-600">Saved</span>
              </>
            )}
            {saveStatus === "error" && (
              <>
                <AlertCircle className="h-4 w-4 text-red-500" />
                <span className="text-red-600">Save failed</span>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}

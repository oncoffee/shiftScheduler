import { Button } from "@/components/ui/button";
import {
  Edit3,
  Save,
  X,
  Undo2,
  Loader2,
  CheckCircle,
  AlertCircle,
} from "lucide-react";
import { useScheduleEditContext } from "@/contexts/ScheduleEditContext";
import { useState } from "react";

export function EditModeToolbar() {
  const {
    isEditMode,
    hasUnsavedChanges,
    isSaving,
    canUndo,
    enterEditMode,
    exitEditMode,
    saveChanges,
    discardChanges,
    undo,
  } = useScheduleEditContext();

  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">(
    "idle"
  );

  const handleSave = async () => {
    try {
      await saveChanges();
      setSaveStatus("success");
      setTimeout(() => setSaveStatus("idle"), 2000);
    } catch {
      setSaveStatus("error");
      setTimeout(() => setSaveStatus("idle"), 3000);
    }
  };

  const handleDiscard = () => {
    discardChanges();
    exitEditMode();
  };

  if (!isEditMode) {
    return (
      <Button variant="outline" size="sm" onClick={enterEditMode}>
        <Edit3 className="h-4 w-4 mr-1" />
        Edit Schedule
      </Button>
    );
  }

  return (
    <div className="flex items-center gap-2 p-2 bg-blue-50 rounded-lg border border-blue-200">
      <div className="flex items-center gap-1 text-sm text-blue-700 font-medium px-2">
        <Edit3 className="h-4 w-4" />
        Edit Mode
      </div>

      <div className="h-6 w-px bg-blue-200" />

      <Button
        variant="ghost"
        size="sm"
        onClick={undo}
        disabled={!canUndo || isSaving}
        className="text-gray-600"
      >
        <Undo2 className="h-4 w-4 mr-1" />
        Undo
        <span className="text-xs text-gray-400 ml-1">(Ctrl+Z)</span>
      </Button>

      <div className="h-6 w-px bg-blue-200" />

      <Button
        variant="outline"
        size="sm"
        onClick={handleDiscard}
        disabled={isSaving}
        className="text-gray-600 hover:text-gray-800 hover:bg-gray-100"
      >
        <X className="h-4 w-4 mr-1" />
        Discard
      </Button>

      <Button
        variant="default"
        size="sm"
        onClick={handleSave}
        disabled={!hasUnsavedChanges || isSaving}
        className="bg-blue-600 hover:bg-blue-700"
      >
        {isSaving ? (
          <>
            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            Saving...
          </>
        ) : saveStatus === "success" ? (
          <>
            <CheckCircle className="h-4 w-4 mr-1" />
            Saved!
          </>
        ) : saveStatus === "error" ? (
          <>
            <AlertCircle className="h-4 w-4 mr-1" />
            Error
          </>
        ) : (
          <>
            <Save className="h-4 w-4 mr-1" />
            Save Changes
          </>
        )}
      </Button>

      {hasUnsavedChanges && !isSaving && (
        <span className="text-xs text-amber-600 ml-2">
          Unsaved changes
        </span>
      )}
    </div>
  );
}

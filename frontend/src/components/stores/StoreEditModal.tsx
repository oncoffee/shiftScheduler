import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { StoreHoursUpdate } from "@/api/client";

const DAYS_OF_WEEK = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

interface StoreEditModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (storeName: string, hours: StoreHoursUpdate[]) => Promise<void>;
  store: {
    store_name: string;
    hours: Record<string, { start_time: string; end_time: string }>;
  } | null;
  isNew?: boolean;
}

export function StoreEditModal({
  open,
  onClose,
  onSave,
  store,
  isNew = false,
}: StoreEditModalProps) {
  const [storeName, setStoreName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      if (store) {
        setStoreName(store.store_name);
      } else {
        setStoreName("");
      }
      setError(null);
    }
  }, [open, store]);

  const handleSave = async () => {
    if (!storeName.trim()) {
      setError("Store name is required");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      let hours: StoreHoursUpdate[] = [];

      if (isNew) {
        for (const day of DAYS_OF_WEEK.slice(0, 5)) {
          hours.push({
            day_of_week: day,
            start_time: "09:00",
            end_time: "17:00",
          });
        }
      } else if (store) {
        for (const day of DAYS_OF_WEEK) {
          if (store.hours[day]) {
            hours.push({
              day_of_week: day,
              start_time: store.hours[day].start_time,
              end_time: store.hours[day].end_time,
            });
          }
        }
      }

      await onSave(storeName.trim(), hours);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save store");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={isNew ? "Add New Store" : "Edit Store Info"}
    >
      <DialogContent>
        <div className="space-y-6">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              Store Name
            </label>
            <input
              type="text"
              value={storeName}
              onChange={(e) => setStoreName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Enter store name"
              autoFocus
            />
          </div>

          {isNew && (
            <p className="text-sm text-gray-500">
              The store will be created with default hours (Mon-Fri 9AM-5PM).
              You can adjust the hours using the sliders after creation.
            </p>
          )}
        </div>
      </DialogContent>

      <DialogFooter>
        <Button variant="outline" onClick={onClose} disabled={saving}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : isNew ? "Create Store" : "Save Changes"}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

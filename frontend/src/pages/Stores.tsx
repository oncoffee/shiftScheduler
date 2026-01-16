import { useState, useCallback, useRef, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, type Store, type StoreHoursUpdate } from "@/api/client";
import { useAsyncData } from "@/hooks/useAsyncData";
import { StoreEditModal } from "@/components/stores";
import { TimeRangeSlider } from "@/components/stores/TimeRangeSlider";
import { Plus, Pencil, Trash2, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";

const DAYS_OF_WEEK = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

const SHORT_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

interface StoreGrouped {
  store_name: string;
  week_no: number;
  hours: Record<string, { start_time: string; end_time: string }>;
}

function groupStores(stores: Store[]): StoreGrouped[] {
  const grouped = new Map<string, StoreGrouped>();
  for (const s of stores) {
    if (!grouped.has(s.store_name)) {
      grouped.set(s.store_name, {
        store_name: s.store_name,
        week_no: s.week_no,
        hours: {},
      });
    }
    grouped.get(s.store_name)!.hours[s.day_of_week] = {
      start_time: s.start_time,
      end_time: s.end_time,
    };
  }
  return Array.from(grouped.values());
}

interface StoreCardProps {
  store: StoreGrouped;
  onEdit: () => void;
  onDelete: () => void;
  onHoursChange: (hours: Record<string, { start_time: string; end_time: string } | null>) => Promise<void>;
}

function StoreCard({ store, onEdit, onDelete, onHoursChange }: StoreCardProps) {
  const [localHours, setLocalHours] = useState(store.hours);
  const [saving, setSaving] = useState(false);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingHoursRef = useRef<Record<string, { start_time: string; end_time: string }> | null>(null);

  // Reset local state when store prop changes (after save completes)
  useEffect(() => {
    setLocalHours(store.hours);
  }, [store]);

  const saveChanges = useCallback(async () => {
    if (!pendingHoursRef.current) return;

    setSaving(true);
    try {
      const hoursToSave: Record<string, { start_time: string; end_time: string } | null> = {};
      for (const day of DAYS_OF_WEEK) {
        hoursToSave[day] = pendingHoursRef.current[day] || null;
      }
      await onHoursChange(hoursToSave);
      pendingHoursRef.current = null;
    } finally {
      setSaving(false);
    }
  }, [onHoursChange]);

  const handleDayChange = useCallback(
    (day: string, startTime: string | null, endTime: string | null) => {
      setLocalHours((prev) => {
        const newHours = { ...prev };
        if (startTime && endTime) {
          newHours[day] = { start_time: startTime, end_time: endTime };
        } else {
          delete newHours[day];
        }
        pendingHoursRef.current = newHours;
        return newHours;
      });

      // Debounced auto-save
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
      saveTimeoutRef.current = setTimeout(() => {
        saveChanges();
      }, 800);
    },
    [saveChanges]
  );

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CardTitle className="text-lg">{store.store_name}</CardTitle>
            <Badge variant="outline">Week {store.week_no}</Badge>
            {saving && (
              <div className="flex items-center gap-1.5 text-blue-600 text-sm">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Saving...</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={onEdit}
              className="gap-1"
            >
              <Pencil className="w-3.5 h-3.5" />
              Edit Info
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onDelete}
              className="gap-1 text-red-600 hover:text-red-700 hover:bg-red-50"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Delete
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex justify-around gap-2 py-2">
          {DAYS_OF_WEEK.map((day, idx) => {
            const hours = localHours[day];
            return (
              <TimeRangeSlider
                key={day}
                day={SHORT_DAYS[idx]}
                startTime={hours?.start_time || null}
                endTime={hours?.end_time || null}
                onChange={(start, end) => handleDayChange(day, start, end)}
              />
            );
          })}
        </div>
        <p className="text-xs text-gray-400 text-center mt-4">
          Drag sliders to adjust hours. Gray bars are inactive days - drag to activate.
        </p>
      </CardContent>
    </Card>
  );
}

export function Stores() {
  const {
    data: stores,
    loading,
    error,
    refetch,
  } = useAsyncData<Store[]>(api.getStores, "Failed to fetch stores");

  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingStore, setEditingStore] = useState<StoreGrouped | null>(null);
  const [isNewStore, setIsNewStore] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [storeToDelete, setStoreToDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const groupedStores = stores ? groupStores(stores) : [];

  const handleAddStore = () => {
    setEditingStore(null);
    setIsNewStore(true);
    setEditModalOpen(true);
  };

  const handleEditStore = (store: StoreGrouped) => {
    setEditingStore(store);
    setIsNewStore(false);
    setEditModalOpen(true);
  };

  const handleDeleteClick = (storeName: string) => {
    setStoreToDelete(storeName);
    setDeleteConfirmOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!storeToDelete) return;

    setDeleting(true);
    try {
      await api.deleteStore(storeToDelete);
      refetch();
      setDeleteConfirmOpen(false);
      setStoreToDelete(null);
    } catch (err) {
      console.error("Failed to delete store:", err);
    } finally {
      setDeleting(false);
    }
  };

  const handleSaveStoreInfo = async (
    storeName: string,
    hours: StoreHoursUpdate[]
  ) => {
    if (isNewStore) {
      await api.createStore(storeName, hours);
    } else if (editingStore) {
      const newName =
        storeName !== editingStore.store_name ? storeName : null;
      await api.updateStore(editingStore.store_name, newName, hours);
    }
    refetch();
  };

  const handleHoursChange = useCallback(
    async (
      storeName: string,
      weekNo: number,
      hours: Record<string, { start_time: string; end_time: string } | null>
    ) => {
      const hoursArray: StoreHoursUpdate[] = [];
      for (const day of DAYS_OF_WEEK) {
        if (hours[day]) {
          hoursArray.push({
            week_no: weekNo,
            day_of_week: day,
            start_time: hours[day]!.start_time,
            end_time: hours[day]!.end_time,
          });
        }
      }
      await api.updateStore(storeName, null, hoursArray);
      refetch();
    },
    [refetch]
  );

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Stores</h1>
          <p className="text-muted-foreground mt-1">
            Configure store hours and scheduling requirements
          </p>
        </div>
        <Button onClick={handleAddStore} className="gap-2">
          <Plus className="w-4 h-4" />
          Add Store
        </Button>
      </div>

      {loading ? (
        <Card>
          <CardContent className="py-8">
            <p className="text-muted-foreground text-center">
              Loading stores...
            </p>
          </CardContent>
        </Card>
      ) : error ? (
        <Card>
          <CardContent className="py-8">
            <div className="text-destructive text-center">
              <p>{error}</p>
              <p className="text-sm text-muted-foreground mt-2">
                Make sure the backend API is running and has the /stores
                endpoint.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : groupedStores.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground mb-4">
              No store configurations found.
            </p>
            <Button onClick={handleAddStore} variant="outline" className="gap-2">
              <Plus className="w-4 h-4" />
              Add Your First Store
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {groupedStores.map((store) => (
            <StoreCard
              key={store.store_name}
              store={store}
              onEdit={() => handleEditStore(store)}
              onDelete={() => handleDeleteClick(store.store_name)}
              onHoursChange={(hours) =>
                handleHoursChange(store.store_name, store.week_no, hours)
              }
            />
          ))}
        </div>
      )}

      <StoreEditModal
        open={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        onSave={handleSaveStoreInfo}
        store={editingStore}
        isNew={isNewStore}
      />

      <Dialog
        open={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        title="Delete Store"
      >
        <DialogContent>
          <p className="text-gray-600">
            Are you sure you want to delete{" "}
            <span className="font-semibold">{storeToDelete}</span>? This action
            cannot be undone.
          </p>
        </DialogContent>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setDeleteConfirmOpen(false)}
            disabled={deleting}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirmDelete}
            disabled={deleting}
          >
            {deleting ? "Deleting..." : "Delete Store"}
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}

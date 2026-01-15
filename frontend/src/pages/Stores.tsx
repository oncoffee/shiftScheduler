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
import { api, type Store } from "@/api/client";

export function Stores() {
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchStores() {
      try {
        const data = await api.getStores();
        setStores(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch stores");
      } finally {
        setLoading(false);
      }
    }
    fetchStores();
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Stores</h1>
        <p className="text-muted-foreground mt-1">
          Configure store hours and scheduling requirements
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Store Schedule</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading stores...</p>
          ) : error ? (
            <div className="text-destructive">
              <p>{error}</p>
              <p className="text-sm text-muted-foreground mt-2">
                Make sure the backend API is running and has the /stores endpoint.
              </p>
            </div>
          ) : stores.length === 0 ? (
            <p className="text-muted-foreground">No store configurations found.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Week</TableHead>
                  <TableHead>Store</TableHead>
                  <TableHead>Day</TableHead>
                  <TableHead>Hours</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stores.map((store, idx) => (
                  <TableRow key={idx}>
                    <TableCell>
                      <Badge variant="outline">Week {store.week_no}</Badge>
                    </TableCell>
                    <TableCell className="font-medium">
                      {store.store_name}
                    </TableCell>
                    <TableCell>{store.day_of_week}</TableCell>
                    <TableCell>
                      {store.start_time} - {store.end_time}
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

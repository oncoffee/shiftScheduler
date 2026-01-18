import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Layout } from "@/components/layout/Layout";
import { Dashboard } from "@/pages/Dashboard";
import { Employees } from "@/pages/Employees";
import { Stores } from "@/pages/Stores";
import { Schedule } from "@/pages/Schedule";
import { History } from "@/pages/History";
import { Logs } from "@/pages/Logs";
import { Settings } from "@/pages/Settings";
import { Compliance } from "@/pages/Compliance";
import { LoginPage } from "@/pages/LoginPage";
import { AuthCallback } from "@/pages/AuthCallback";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallback />} />

          {/* Protected routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="employees" element={<Employees />} />
            <Route path="stores" element={<Stores />} />
            <Route path="schedule" element={<Schedule />} />
            <Route path="compliance" element={<Compliance />} />
            <Route path="history" element={<History />} />
            <Route path="logs" element={<Logs />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;

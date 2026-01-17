import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Layout } from "@/components/layout/Layout";
import { Dashboard } from "@/pages/Dashboard";
import { Employees } from "@/pages/Employees";
import { Stores } from "@/pages/Stores";
import { Schedule } from "@/pages/Schedule";
import { History } from "@/pages/History";
import { Logs } from "@/pages/Logs";
import { Settings } from "@/pages/Settings";
import { Compliance } from "@/pages/Compliance";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
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
  );
}

export default App;

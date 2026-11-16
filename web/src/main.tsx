import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import Layout from "./components/Layout";
import { APP_BASE, APP_NAME, EDITION, STATIC_DEMO } from "./config";
import DesktopOnly from "./components/DesktopOnly";
import Landing from "./landing/Landing";
import Assistant from "./pages/Assistant";
import Dashboard from "./pages/Dashboard";
import Intelligence from "./pages/Intelligence";
import Modules from "./pages/Modules";
import Overview from "./pages/Overview";
import Simulator from "./pages/Simulator";
import ExercisePage from "./pages/Exercise";
import NutritionPage from "./pages/Nutrition";
import AiModels from "./pages/AiModels";
import FineTuning from "./pages/FineTuning";
import Devices from "./pages/Devices";
import Servers from "./pages/Servers";
import Settings from "./pages/Settings";
import Habitat from "./pages/Habitat";
import { canSeeDashboard, isAdmin } from "./components/Layout";
import Crew from "./pages/Crew";
import "./styles.css";
import "./serious.css";

document.documentElement.dataset.edition = EDITION;
document.title = APP_NAME;

function App() {
  const { user, ready } = useAuth();
  if (!ready || !user) return <div className="login-wrap"><p className="muted">Opening the demo…</p></div>;
  return (
    <Routes key={user.username}>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="dashboard" element={canSeeDashboard(user.role) ? <Dashboard /> : <Navigate to="/" replace />} />
        <Route path="crew" element={isAdmin(user.role) ? <Crew /> : <Navigate to="/" replace />} />
        <Route path="exercise" element={<ExercisePage />} />
        <Route path="nutrition" element={<NutritionPage />} />
        <Route path="risks" element={<Navigate to="/settings?tab=hazards" replace />} />
        <Route path="intelligence" element={<Intelligence />} />
        <Route path="assistant" element={STATIC_DEMO ? <DesktopOnly title="Assistant" /> : <Assistant />} />
        <Route path="ai-models" element={STATIC_DEMO ? <DesktopOnly title="AI models" /> : <AiModels />} />
        <Route path="fine-tuning" element={STATIC_DEMO ? <DesktopOnly title="Fine-tuning" /> : <FineTuning />} />
        <Route path="research" element={<Navigate to="/settings?tab=research" replace />} />
        <Route path="settings" element={<Settings />} />
        <Route path="habitat" element={<Habitat />} />
        <Route path="devices" element={<Devices />} />
        <Route path="servers" element={<Servers />} />
        <Route path="modules" element={<Modules />} />
        <Route path="simulator" element={<Simulator />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

// "/" is the public landing page. /app opens straight into the demo, with no passcode.
// The desktop app opens /app directly.
const path = window.location.pathname;
const inApp = path === APP_BASE || path.startsWith(APP_BASE + "/");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {inApp ? (
      <BrowserRouter basename={APP_BASE}>
        <AuthProvider><App /></AuthProvider>
      </BrowserRouter>
    ) : (
      <Landing />
    )}
  </React.StrictMode>,
);

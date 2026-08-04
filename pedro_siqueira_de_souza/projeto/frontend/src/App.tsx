import { Navigate, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import Pipeline from "./pages/Pipeline";
import Qualificadas from "./pages/Qualificadas";
import Analytics from "./pages/Analytics";

// Shell da aplicação (ux.md §3.1): sidebar fixa + topbar + conteúdo.
// Rotas ativas: Pipeline, Qualificadas e Analytics (ux.md §6.5).
export default function App() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main">
        <Topbar />
        <Routes>
          <Route path="/" element={<Navigate to="/pipeline" replace />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/qualificadas" element={<Qualificadas />} />
          <Route path="/analytics" element={<Analytics />} />
        </Routes>
      </div>
    </div>
  );
}

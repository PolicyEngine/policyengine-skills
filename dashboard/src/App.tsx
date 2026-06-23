import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import { manifest } from "./data";
import WorkflowsPage from "./pages/Workflows";
import CatalogPage from "./pages/Catalog";
import GuidesPage from "./pages/Guides";
import HealthPage from "./pages/Health";

const generated = new Date(manifest.generated_at);

function Sidebar() {
  const healthCount =
    (manifest.functional_overlaps?.length ?? 0) +
    Object.values(manifest.gaps).reduce((s, arr) => s + arr.length, 0) +
    manifest.artifacts.filter(
      (a) =>
        a.registry_status === "deprecated" ||
        a.registry_status === "use-with-care",
    ).length;

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">PolicyEngine</div>
      <div className="sidebar-title">Ecosystem Dashboard</div>
      <nav className="sidebar-nav">
        <NavLink to="/workflows">
          <span className="nav-icon">⌥</span>
          <span>Workflows</span>
          <span className="nav-count">{manifest.counts.command}</span>
        </NavLink>
        <NavLink to="/catalog">
          <span className="nav-icon">▦</span>
          <span>Catalog</span>
          <span className="nav-count">{manifest.artifacts.length}</span>
        </NavLink>
        <NavLink to="/guides">
          <span className="nav-icon">📖</span>
          <span>Guides</span>
          <span className="nav-count">1</span>
        </NavLink>
        <NavLink to="/health">
          <span className="nav-icon">♥</span>
          <span>Health</span>
          <span className="nav-count">{healthCount}</span>
        </NavLink>
      </nav>
      <div className="sidebar-footer">
        Manifest generated
        <br />
        {generated.toLocaleString()}
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/workflows" replace />} />
          <Route path="/workflows" element={<WorkflowsPage />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/guides" element={<GuidesPage />} />
          <Route path="/health" element={<HealthPage />} />
          {/* Legacy routes kept as redirects so bookmarked links don't 404 */}
          <Route path="/overview" element={<Navigate to="/workflows" replace />} />
          <Route path="/find" element={<Navigate to="/catalog" replace />} />
          <Route path="/repos" element={<Navigate to="/workflows" replace />} />
          <Route path="/duplicates" element={<Navigate to="/health" replace />} />
          <Route path="/gaps" element={<Navigate to="/health" replace />} />
          <Route path="/cleanup" element={<Navigate to="/health" replace />} />
        </Routes>
      </main>
    </div>
  );
}

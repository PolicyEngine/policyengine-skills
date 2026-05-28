import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import { manifest } from "./data";
import OverviewPage from "./pages/Overview";
import CatalogPage from "./pages/Catalog";
import DuplicatesPage from "./pages/Duplicates";
import WorkflowsPage from "./pages/Workflows";
import ReposPage from "./pages/Repos";
import GapsPage from "./pages/Gaps";

const generated = new Date(manifest.generated_at);

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">PolicyEngine</div>
      <div className="sidebar-title">Ecosystem Dashboard</div>
      <nav className="sidebar-nav">
        <NavLink to="/overview">
          <span className="nav-icon">◆</span>
          <span>Overview</span>
        </NavLink>
        <NavLink to="/catalog">
          <span className="nav-icon">▦</span>
          <span>Catalog</span>
          <span className="nav-count">{manifest.artifacts.length}</span>
        </NavLink>
        <NavLink to="/duplicates">
          <span className="nav-icon">⇆</span>
          <span>Overlaps</span>
          <span className="nav-count">
            {manifest.functional_overlaps?.length ?? 0}
          </span>
        </NavLink>
        <NavLink to="/workflows">
          <span className="nav-icon">⌥</span>
          <span>Workflows</span>
          <span className="nav-count">{manifest.counts.command}</span>
        </NavLink>
        <NavLink to="/repos">
          <span className="nav-icon">▢</span>
          <span>Repos</span>
          <span className="nav-count">
            {manifest.known_repos?.length ?? 0}
          </span>
        </NavLink>
        <NavLink to="/gaps">
          <span className="nav-icon">⚠</span>
          <span>Gaps</span>
          <span className="nav-count">
            {Object.values(manifest.gaps).reduce((s, arr) => s + arr.length, 0)}
          </span>
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
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/duplicates" element={<DuplicatesPage />} />
          <Route path="/workflows" element={<WorkflowsPage />} />
          <Route path="/repos" element={<ReposPage />} />
          <Route path="/gaps" element={<GapsPage />} />
        </Routes>
      </main>
    </div>
  );
}

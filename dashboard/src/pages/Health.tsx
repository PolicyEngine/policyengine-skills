import { useState } from "react";
import DuplicatesPage from "./Duplicates";
import GapsPage from "./Gaps";
import CleanupPage from "./Cleanup";
import { manifest } from "../data";

type HealthTab = "overlaps" | "gaps" | "cleanup";

export default function HealthPage() {
  const [tab, setTab] = useState<HealthTab>("overlaps");

  const overlapsCount = manifest.functional_overlaps?.length ?? 0;
  const gapsCount = Object.values(manifest.gaps).reduce(
    (sum, arr) => sum + arr.length,
    0,
  );
  const cleanupCount = manifest.artifacts.filter(
    (a) =>
      a.registry_status === "deprecated" ||
      a.registry_status === "use-with-care",
  ).length;

  return (
    <div className="page">
      <header className="page-header">
        <h1 className="page-title">Health</h1>
        <p className="page-subtitle">
          What needs attention — duplicate effort, coverage gaps, and deprecated
          artifacts. Use this view when maintaining the plugin or before adding
          something new.
        </p>
      </header>

      <div className="health-tabs">
        <button
          className={`health-tab ${tab === "overlaps" ? "active" : ""}`}
          onClick={() => setTab("overlaps")}
        >
          <span>Overlaps</span>
          <span className="health-tab-count">{overlapsCount}</span>
        </button>
        <button
          className={`health-tab ${tab === "gaps" ? "active" : ""}`}
          onClick={() => setTab("gaps")}
        >
          <span>Gaps</span>
          <span className="health-tab-count">{gapsCount}</span>
        </button>
        <button
          className={`health-tab ${tab === "cleanup" ? "active" : ""}`}
          onClick={() => setTab("cleanup")}
        >
          <span>Cleanup</span>
          <span className="health-tab-count">{cleanupCount}</span>
        </button>
      </div>

      <div className="health-content">
        {tab === "overlaps" && <DuplicatesPage />}
        {tab === "gaps" && <GapsPage />}
        {tab === "cleanup" && <CleanupPage />}
      </div>
    </div>
  );
}

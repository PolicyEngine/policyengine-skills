import { useMemo, useState } from "react";
import { manifest } from "../data";
import type { AnalysisEntry } from "../types";

type SortKey = "date" | "cost" | "verdict" | "title";

const VERDICT_COLOR: Record<string, string> = {
  PASS: "verdict-pass",
  "PASS-WITH-NOTES": "verdict-pass-notes",
  "PASS-WITH-CORROBORATION": "verdict-pass",
  INVESTIGATE: "verdict-investigate",
  BLOCKED: "verdict-blocked",
  structural: "verdict-structural",
  "not-possible": "verdict-impossible",
  "deployed-model-lag": "verdict-lag",
};

function formatCost(v: number | null): string {
  if (v === null || v === undefined) return "—";
  const sign = v >= 0 ? "+" : "−";
  return `${sign}$${Math.abs(v).toFixed(2)}B`;
}

function formatPct(v: number | null): string {
  if (v === null || v === undefined) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(3)}%`;
}

function formatPp(v: number | null): string {
  if (v === null || v === undefined) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(3)}pp`;
}

function formatHorizon(h: AnalysisEntry["horizon"]): string {
  if (h === null || h === undefined) return "—";
  if (h === 1) return "1yr";
  if (h === 10) return "10yr";
  return String(h);
}

export default function AnalysesPage() {
  const analyses = manifest.analyses ?? [];
  const [verdictFilter, setVerdictFilter] = useState<string | null>(null);
  const [countryFilter, setCountryFilter] = useState<string | null>(null);
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortKey>("date");

  const allVerdicts = useMemo(
    () =>
      Array.from(
        new Set(analyses.map((a) => a.verdict).filter(Boolean) as string[]),
      ).sort(),
    [analyses],
  );
  const allCountries = useMemo(
    () =>
      Array.from(
        new Set(
          analyses
            .map((a) => a.jurisdiction.country)
            .filter(Boolean) as string[],
        ),
      ).sort(),
    [analyses],
  );
  const allTags = useMemo(
    () => Array.from(new Set(analyses.flatMap((a) => a.tags))).sort(),
    [analyses],
  );

  const filtered = useMemo(() => {
    let rows = [...analyses];
    if (verdictFilter) rows = rows.filter((a) => a.verdict === verdictFilter);
    if (countryFilter)
      rows = rows.filter((a) => a.jurisdiction.country === countryFilter);
    if (tagFilter) rows = rows.filter((a) => a.tags.includes(tagFilter));
    rows.sort((a, b) => {
      if (sortBy === "date") return (b.date ?? "").localeCompare(a.date ?? "");
      if (sortBy === "cost") {
        const av = a.cost_billion_10yr_actual ?? a.cost_billion_year1 ?? 0;
        const bv = b.cost_billion_10yr_actual ?? b.cost_billion_year1 ?? 0;
        return Math.abs(bv) - Math.abs(av);
      }
      if (sortBy === "verdict")
        return (a.verdict ?? "").localeCompare(b.verdict ?? "");
      return (a.title ?? "").localeCompare(b.title ?? "");
    });
    return rows;
  }, [analyses, verdictFilter, countryFilter, tagFilter, sortBy]);

  return (
    <div className="page">
      <header className="page-header">
        <h1 className="page-title">Analyses</h1>
        <p className="page-subtitle">
          Every <code>/analyze-policy</code> run archived in this repo, indexed
          by verdict, jurisdiction, tags, and headline numbers. Frontmatter
          schema is documented in <code>analyses/README.md</code>.
        </p>
      </header>

      <div className="analyses-filters">
        <label>
          Verdict:{" "}
          <select
            value={verdictFilter ?? ""}
            onChange={(e) => setVerdictFilter(e.target.value || null)}
          >
            <option value="">all</option>
            {allVerdicts.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Country:{" "}
          <select
            value={countryFilter ?? ""}
            onChange={(e) => setCountryFilter(e.target.value || null)}
          >
            <option value="">all</option>
            {allCountries.map((c) => (
              <option key={c} value={c}>
                {c.toUpperCase()}
              </option>
            ))}
          </select>
        </label>
        <label>
          Tag:{" "}
          <select
            value={tagFilter ?? ""}
            onChange={(e) => setTagFilter(e.target.value || null)}
          >
            <option value="">all</option>
            {allTags.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label>
          Sort:{" "}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortKey)}
          >
            <option value="date">date (newest)</option>
            <option value="cost">|cost| (biggest)</option>
            <option value="verdict">verdict</option>
            <option value="title">title</option>
          </select>
        </label>
        <span className="analyses-count">
          {filtered.length} / {analyses.length} shown
        </span>
      </div>

      <table className="guide-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Jurisdiction</th>
            <th>Title</th>
            <th>Verdict</th>
            <th>Horizon</th>
            <th style={{ textAlign: "right" }}>Yr-1</th>
            <th style={{ textAlign: "right" }}>10yr actual</th>
            <th style={{ textAlign: "right" }}>Gini Δ</th>
            <th style={{ textAlign: "right" }}>Top-1% Δ</th>
            <th>Corroboration</th>
            <th>Model</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((a) => {
            const juris = a.jurisdiction.state
              ? `${a.jurisdiction.country?.toUpperCase()}-${a.jurisdiction.state.toUpperCase()}`
              : a.jurisdiction.country?.toUpperCase() ?? "—";
            const verdictClass = VERDICT_COLOR[a.verdict ?? ""] ?? "";
            return (
              <tr key={a.file}>
                <td>{a.date ?? "—"}</td>
                <td>{juris}</td>
                <td title={a.file}>{a.title}</td>
                <td>
                  <span className={`verdict ${verdictClass}`}>
                    {a.verdict ?? "—"}
                  </span>
                </td>
                <td>{formatHorizon(a.horizon)}</td>
                <td style={{ textAlign: "right" }}>
                  {formatCost(a.cost_billion_year1)}
                </td>
                <td style={{ textAlign: "right" }}>
                  {formatCost(a.cost_billion_10yr_actual)}
                </td>
                <td style={{ textAlign: "right" }}>
                  {formatPct(a.gini_pct_change)}
                </td>
                <td style={{ textAlign: "right" }}>
                  {formatPp(a.top1_pp_change)}
                </td>
                <td>{a.corroboration_verdict ?? "—"}</td>
                <td style={{ fontSize: "0.75rem" }}>{a.model_version ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {filtered.length === 0 && (
        <p className="empty-state">No analyses match the current filters.</p>
      )}
    </div>
  );
}

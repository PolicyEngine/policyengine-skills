import { useMemo, useState } from "react";
import { manifest, kindLabel, getArtifact } from "../data";
import type { Artifact, ArtifactKind } from "../types";
import { ArtifactDrawer } from "../components/Drawer";

interface GapSection {
  key: keyof typeof manifest.gaps;
  title: string;
  description: string;
  severity: "info" | "warn" | "danger";
}

const SECTIONS: GapSection[] = [
  {
    key: "orphaned_skills",
    title: "Skills not in any bundle",
    description:
      "These skills exist on disk but no bundle ships them — users can't actually load them.",
    severity: "warn",
  },
  {
    key: "uncalled_agents",
    title: "Agents no command invokes",
    description:
      "These agents aren't referenced by any command or other agent. They may still be useful, but are likely undiscoverable.",
    severity: "warn",
  },
  {
    key: "orphaned_agents",
    title: "Agents not in any bundle",
    description: "Same idea as skills — written but not shipped.",
    severity: "warn",
  },
  {
    key: "broken_bundle_refs",
    title: "Broken bundle references",
    description:
      "Bundle JSON files that point to files that don't exist on disk. These break the wrapper build.",
    severity: "danger",
  },
  {
    key: "missing_descriptions",
    title: "Missing descriptions",
    description:
      "Artifacts whose frontmatter description is empty. They won't get matched by Claude's skill router.",
    severity: "warn",
  },
  {
    key: "missing_triggers",
    title: "Missing triggers",
    description:
      'Routing skills (those whose description mentions "Triggers:") that don\'t actually list any trigger phrases.',
    severity: "info",
  },
];

function severityStyle(sev: GapSection["severity"]) {
  if (sev === "danger") return { borderColor: "var(--danger)", color: "var(--danger)" };
  if (sev === "warn") return { borderColor: "var(--warning)", color: "var(--warning)" };
  return { borderColor: "var(--border)", color: "var(--fg-muted)" };
}

export default function GapsPage() {
  const [selected, setSelected] = useState<Artifact | null>(null);

  const ecosystemMap = useMemo(() => {
    // Build a "what does each bundle ship" matrix to spot bundles that omit
    // something obviously related.
    const map: Record<string, { skills: number; agents: number; commands: number }> = {};
    for (const b of manifest.bundles_raw) {
      map[b.name] = {
        skills: b.skills?.length ?? 0,
        agents: b.agents?.length ?? 0,
        commands: b.commands?.length ?? 0,
      };
    }
    return map;
  }, []);

  const commandsWithoutAgents = useMemo(() => {
    return manifest.artifacts
      .filter((a) => a.kind === "command")
      .filter((c) => {
        const refs = c.references.agent ?? [];
        return refs.length === 0;
      });
  }, []);

  const skillsWithFewBundles = useMemo(() => {
    return manifest.artifacts
      .filter((a) => a.kind === "skill" && a.bundles.length === 1)
      .filter((a) => !a.bundles.includes("complete"));
  }, []);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Coverage gaps</h1>
        <p className="page-subtitle">
          Issues that are blocking, undiscoverable, or worth tidying. Use this view to
          prioritize cleanup work.
        </p>
      </div>

      <div className="stat-grid">
        {SECTIONS.map((s) => (
          <div className="stat-card" key={s.key} style={severityStyle(s.severity)}>
            <div className="stat-label" style={{ color: severityStyle(s.severity).color }}>
              {s.title}
            </div>
            <div className="stat-value">{manifest.gaps[s.key].length}</div>
          </div>
        ))}
      </div>

      {SECTIONS.map((s) => {
        const items = manifest.gaps[s.key];
        if (items.length === 0) return null;
        return (
          <div className="card" key={s.key} style={{ marginTop: 16 }}>
            <h3 style={{ margin: "0 0 4px" }}>
              {s.title} <span style={{ color: "var(--fg-muted)", fontSize: 14 }}>({items.length})</span>
            </h3>
            <p style={{ color: "var(--fg-muted)", margin: "0 0 12px", fontSize: 13 }}>
              {s.description}
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {items.map((item: any, i: number) => {
                const id = item.id ?? `${item.bundle}/${item.ref}`;
                const kindForDot: ArtifactKind | null =
                  s.key === "orphaned_skills" || s.key === "missing_triggers"
                    ? "skill"
                    : s.key === "uncalled_agents" || s.key === "orphaned_agents"
                      ? "agent"
                      : item.kind ?? null;
                return (
                  <span
                    key={i}
                    className="chip"
                    style={{ cursor: kindForDot ? "pointer" : "default", fontSize: 12 }}
                    onClick={() => {
                      if (kindForDot && item.id) {
                        const a = getArtifact(kindForDot, item.id);
                        if (a) setSelected(a);
                      }
                    }}
                  >
                    {kindForDot && <span className={`kind-dot kind-${kindForDot}`} />}
                    {id}
                    {item.category && (
                      <span style={{ color: "var(--fg-muted)", marginLeft: 4 }}>
                        ({item.category})
                      </span>
                    )}
                  </span>
                );
              })}
            </div>
          </div>
        );
      })}

      <div className="card" style={{ marginTop: 24 }}>
        <h3 style={{ marginTop: 0 }}>Commands that don't invoke any agent</h3>
        <p style={{ color: "var(--fg-muted)", margin: "0 0 12px", fontSize: 13 }}>
          These commands handle everything inline — sometimes that's right, sometimes it
          means agent extraction is overdue.
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {commandsWithoutAgents.map((c) => (
            <span
              key={c.id}
              className="chip kind-command"
              style={{ cursor: "pointer" }}
              onClick={() => setSelected(c)}
            >
              {c.name}
            </span>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Skills shipped in exactly one (non-complete) bundle</h3>
        <p style={{ color: "var(--fg-muted)", margin: "0 0 12px", fontSize: 13 }}>
          Low-reach skills. Worth asking: should they ship in <code>essential</code> or
          another broader bundle?
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {skillsWithFewBundles.map((c) => (
            <span
              key={c.id}
              className="chip kind-skill"
              style={{ cursor: "pointer" }}
              onClick={() => setSelected(c)}
            >
              {c.name}{" "}
              <span style={{ color: "var(--fg-muted)", marginLeft: 4 }}>
                ({c.bundles[0]})
              </span>
            </span>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Bundle coverage matrix</h3>
        <table className="data">
          <thead>
            <tr>
              <th>Bundle</th>
              <th style={{ textAlign: "right" }}>Skills</th>
              <th style={{ textAlign: "right" }}>Agents</th>
              <th style={{ textAlign: "right" }}>Commands</th>
              <th style={{ textAlign: "right" }}>Total</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(ecosystemMap).map(([name, counts]) => (
              <tr key={name}>
                <td>
                  <strong>{name}</strong>
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                  {counts.skills}
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                  {counts.agents}
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                  {counts.commands}
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                  {counts.skills + counts.agents + counts.commands}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ArtifactDrawer
        artifact={selected}
        onClose={() => setSelected(null)}
        onSelect={(kind, id) => {
          const next = getArtifact(kind, id);
          if (next) setSelected(next);
        }}
      />
    </div>
  );
}

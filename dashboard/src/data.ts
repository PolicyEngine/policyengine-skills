import manifestRaw from "./data/manifest.json";
import type { Artifact, ArtifactKind, Manifest, RegistryStatus } from "./types";

export const manifest = manifestRaw as unknown as Manifest;

export const artifactKey = (kind: ArtifactKind, id: string) => `${kind}:${id}`;

export const artifactsByKey: Map<string, Artifact> = new Map(
  manifest.artifacts.map((a) => [artifactKey(a.kind, a.id), a]),
);

export function getArtifact(kind: ArtifactKind, id: string): Artifact | undefined {
  return artifactsByKey.get(artifactKey(kind, id));
}

export const kindLabel: Record<ArtifactKind, string> = {
  skill: "Skill",
  agent: "Agent",
  command: "Command",
  bundle: "Bundle",
};

export const kindColor: Record<ArtifactKind, string> = {
  skill: "var(--kind-skill)",
  agent: "var(--kind-agent)",
  command: "var(--kind-command)",
  bundle: "var(--kind-bundle)",
};

export const statusLabel: Record<RegistryStatus, string> = {
  recommended: "Recommended",
  "use-with-care": "Use with care",
  deprecated: "Do not use",
  experimental: "Experimental",
  "internal-only": "Internal only",
};

export const statusDescription: Record<RegistryStatus, string> = {
  recommended: "Default choice for its stated scope.",
  "use-with-care": "Confirm ownership and fit before relying on it.",
  deprecated: "Superseded by a newer artifact.",
  experimental: "Still being trialed; expect churn.",
  "internal-only": "Usually called by workflows rather than directly.",
};

export const statusRank: Record<RegistryStatus, number> = {
  deprecated: 0,
  "use-with-care": 1,
  experimental: 2,
  "internal-only": 3,
  recommended: 4,
};

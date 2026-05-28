import manifestRaw from "./data/manifest.json";
import type { Artifact, ArtifactKind, Manifest } from "./types";

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

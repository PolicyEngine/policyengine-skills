export type ArtifactKind = "skill" | "agent" | "command" | "bundle";
export type RegistryStatus =
  | "recommended"
  | "use-with-care"
  | "deprecated"
  | "experimental"
  | "internal-only";

export interface Artifact {
  id: string;
  kind: ArtifactKind;
  name: string;
  description: string;
  category: string;
  path: string;
  tools: string[];
  model: string | null;
  triggers: string[];
  bundles: string[];
  target_repos: string[];
  functional_role: string | null;
  functional_summary: string | null;
  functional_scope: string[];
  functional_supersedes: string[];
  registry_status: RegistryStatus;
  registry_owner: string;
  recommended_for: string[];
  use_instead: string[];
  registry_notes: string;
  references: Partial<Record<ArtifactKind, string[]>>;
  body_length: number;
}

export type FunctionalOverlapCategory =
  | "superseded"
  | "merge-candidate"
  | "wiring-gap"
  | "implementation-pair"
  | "complementary";

export interface FunctionalOverlap {
  category: FunctionalOverlapCategory;
  artifacts: Array<{ kind: ArtifactKind; id: string }>;
  role: string;
  rationale: string;
  scope_overlap?: string[];
}

export interface Edge {
  source_kind: ArtifactKind;
  source: string;
  target_kind: ArtifactKind;
  target: string;
}

export interface OverlapPair {
  a: { kind: ArtifactKind; id: string };
  b: { kind: ArtifactKind; id: string };
  score: number;
  shared_terms: string[];
}

export interface Gaps {
  orphaned_skills: Array<{ id: string; category: string }>;
  uncalled_agents: Array<{ id: string; category: string }>;
  orphaned_agents: Array<{ id: string; category: string }>;
  broken_bundle_refs: Array<{ bundle: string; ref: string; kind: string }>;
  missing_descriptions: Array<{ id: string; kind: string; path: string }>;
  missing_triggers: Array<{ id: string; path: string }>;
}

export interface Manifest {
  generated_at: string;
  counts: Record<ArtifactKind, number>;
  artifacts: Artifact[];
  edges: Edge[];
  overlaps: OverlapPair[];
  functional_overlaps: FunctionalOverlap[];
  gaps: Gaps;
  bundles_raw: Array<{
    name: string;
    description: string;
    category?: string;
    skills?: string[];
    agents?: string[];
    commands?: string[];
  }>;
  known_repos: Array<{
    name: string;
    kind: string;
    kind_label: string;
    tooling_relevant: boolean;
  }>;
  repo_kind_labels: Record<string, string>;
  tooling_relevant_kinds: string[];
  repo_coverage: Array<{
    name: string;
    kind: string;
    kind_label: string;
    tooling_relevant: boolean;
    description: string;
    visibility: string;
    pushed_at: string | null;
    skills: string[];
    agents: string[];
    commands: string[];
    total: number;
  }>;
}

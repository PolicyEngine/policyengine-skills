import { useState } from "react";

type GuideId = "analyze-policy";

export default function GuidesPage() {
  const [active, setActive] = useState<GuideId>("analyze-policy");

  return (
    <div className="page">
      <header className="page-header">
        <h1 className="page-title">Command guides</h1>
        <p className="page-subtitle">
          Concise reference for each command — inputs, outputs, verdicts, and constraints.
        </p>
      </header>

      <div className="guides-layout">
        <nav className="guides-nav">
          <button
            className={`guides-nav-item ${active === "analyze-policy" ? "active" : ""}`}
            onClick={() => setActive("analyze-policy")}
          >
            <span className="guides-nav-slash">/</span>analyze-policy
            <span className="guides-nav-blurb">Reform analysis pipeline</span>
          </button>
        </nav>

        <div className="guides-content">
          {active === "analyze-policy" && <AnalyzePolicyGuide />}
        </div>
      </div>
    </div>
  );
}

function AnalyzePolicyGuide() {
  return (
    <article className="guide">
      <header className="guide-header">
        <h2 className="guide-title">/analyze-policy</h2>
        <p className="guide-tagline">
          End-to-end reform analysis. Takes a reform description, returns a verdict-graded
          impact report benchmarked against PolicyEngine priors AND external sources
          (JCT, CBO, CRFB, TPC, TF), with a routed action item.
        </p>
      </header>

      <Section title="When to use it">
        <ul>
          <li>You have a hypothetical reform and want the cost + distributional impact</li>
          <li>You want to validate a bill against PolicyEngine before publishing</li>
          <li>You want a comparison to external benchmarks alongside the PE number</li>
        </ul>
        <p className="guide-callout">
          <strong>Don't use for:</strong> implementing a new program
          (<code>/encode-policy-v2</code>), reviewing a PR
          (<code>/review-program</code> or <code>/review-pr</code>), or state-bill tracking
          with DB write (<code>/encode-bill</code> in the legislative tracker).
        </p>
      </Section>

      <Section title="How to call it">
        <p>Three input shapes — pick whichever matches what you have:</p>
        <table className="guide-table">
          <thead>
            <tr>
              <th>You have...</th>
              <th>You type...</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>A natural-language idea</td>
              <td>
                <code>/analyze-policy "ARPA-style CTC: $3,000 / $3,600, fully refundable"</code>
              </td>
            </tr>
            <tr>
              <td>A specific bill</td>
              <td>
                <code>/analyze-policy RI H7127</code> or <code>/analyze-policy US HR1234</code>
              </td>
            </tr>
            <tr>
              <td>A URL to legislative text</td>
              <td>
                <code>/analyze-policy https://congress.gov/...</code>
              </td>
            </tr>
          </tbody>
        </table>

        <h4>Flags</h4>
        <table className="guide-table">
          <thead>
            <tr>
              <th>Flag</th>
              <th>Effect</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <code>--country us|uk|ca</code>
              </td>
              <td>Jurisdiction (default us)</td>
            </tr>
            <tr>
              <td>
                <code>--year YYYY</code>
              </td>
              <td>Simulation year (default current)</td>
            </tr>
            <tr>
              <td>
                <code>--mode api|local</code>
              </td>
              <td>API (default) or local Python install</td>
            </tr>
            <tr>
              <td>
                <code>--skip-microsim</code>
              </td>
              <td>Process-test mode — predicts from anchor, no live API call</td>
            </tr>
            <tr>
              <td>
                <code>--log-to &lt;dest&gt;</code>
              </td>
              <td>
                Override auto-routing. Values:{" "}
                <code>archive</code>, <code>issue:&lt;repo&gt;</code>,{" "}
                <code>draft:&lt;repo&gt;/&lt;path&gt;</code>, <code>tracker</code>
              </td>
            </tr>
            <tr>
              <td>
                <code>--no-log</code>
              </td>
              <td>Skip Phase 8 logging; write only the /tmp report</td>
            </tr>
            <tr>
              <td>
                <code>--auto-confirm</code>
              </td>
              <td>Skip confirmation prompts before opening GitHub issues</td>
            </tr>
            <tr>
              <td>
                <code>--auto-investigate</code>
              </td>
              <td>If INVESTIGATE fires, auto-run top calibration hypothesis</td>
            </tr>
            <tr>
              <td>
                <code>--write-report PATH</code>
              </td>
              <td>Override default /tmp/analyze-policy-&#123;policy_id&#125;.md</td>
            </tr>
          </tbody>
        </table>
      </Section>

      <Section title="What it does — 9 stages">
        <ol className="guide-stages">
          <li>
            <strong>Policy text → provisions.</strong> Reads bill text or natural-language
            spec, extracts structured provisions.
          </li>
          <li>
            <strong>Parameter mapping + classification.</strong> Each provision mapped to a
            PolicyEngine YAML path. Five pre-flight checks run in order: master existence
            → deployed API existence → date coverage → formula liveness (catches{" "}
            <code>where()</code>-deadens traps) → reform-family toggles. Outputs:{" "}
            <code>parametric</code>, <code>structural</code>, or <code>not-possible</code>.
          </li>
          <li>
            <strong>Prior anchors (all 3 tiers REQUIRED).</strong> Tier 1 PE priors, Tier 2
            official fiscal (JCT/CBO), Tier 3 think tanks (CRFB, TPC, Tax Foundation,
            ITEP, CBPP). Silence is not acceptable output — each tier emits a structured
            result.
          </li>
          <li>
            <strong>Microsim.</strong> POST to api.policyengine.org, poll{" "}
            <code>/economy/&#123;policy_id&#125;/over/&#123;baseline_id&#125;</code>{" "}
            (US current law = 2). 5-10 min wall-clock per single-year US run.
          </li>
          <li>
            <strong>Compare.</strong> Two checks: per-metric tolerance (auto-widened for
            noisy cases — small state, baseline mismatch, regime shift, thin SKILL
            coverage), AND external-benchmark agreement (PASS requires ≥2 external
            sources within ±25%).
          </li>
          <li>
            <strong>(if no direct comparator) Model corroboration.</strong> When external
            benchmarks don't directly anchor the reform shape, run external sources' EXACT
            reform shapes through our model (mirror-shape runs). If the model reproduces 2+
            published external scores within ±25%, the parameter family is independently
            validated and the verdict is upgraded to{" "}
            <code>PASS-WITH-CORROBORATION</code>. If mirrors drift, escalate to INVESTIGATE.
          </li>
          <li>
            <strong>(if INVESTIGATE) Calibration diagnosis.</strong> Ranks hypotheses with
            file:line citations and runnable tests.
          </li>
          <li>
            <strong>Mechanical write-up.</strong> Neutral provisions description per
            PolicyEngine writing style.
          </li>
          <li>
            <strong>Log.</strong> Writes archive entry with YAML frontmatter; auto-routes
            issues by verdict.
          </li>
        </ol>
      </Section>

      <Section title="Verdicts — what you get, what you do">
        <table className="guide-table">
          <thead>
            <tr>
              <th>Verdict</th>
              <th>Trigger</th>
              <th>What you do</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <span className="verdict verdict-pass">PASS</span>
              </td>
              <td>All metrics in tolerance AND ≥2 external sources within ±25%</td>
              <td>Use the numbers. Blog, brief, dashboard.</td>
            </tr>
            <tr>
              <td>
                <span className="verdict verdict-pass-notes">PASS-WITH-NOTES</span>
              </td>
              <td>Edge-of-band metrics OR exactly-at-threshold benchmark agreement</td>
              <td>Use, but read the notes. Footnote, no redo.</td>
            </tr>
            <tr>
              <td>
                <span className="verdict verdict-pass">PASS-WITH-CORROBORATION</span>
              </td>
              <td>
                No direct external comparator, but mirror-shape runs of 2+ external
                sources reproduce within ±25%
              </td>
              <td>Use the numbers. Cite the corroboration evidence.</td>
            </tr>
            <tr>
              <td>
                <span className="verdict verdict-investigate">INVESTIGATE</span>
              </td>
              <td>Metric outside band OR external consensus disagrees</td>
              <td>
                Read ranked calibration hypotheses. Run the top one. Don't publish yet.
              </td>
            </tr>
            <tr>
              <td>
                <span className="verdict verdict-blocked">BLOCKED</span>
              </td>
              <td>Tier 2 or Tier 3 benchmark coverage missing</td>
              <td>
                Pipeline refuses PASS. Re-run with full external benchmark search.
              </td>
            </tr>
            <tr>
              <td>
                <span className="verdict verdict-structural">structural</span>
              </td>
              <td>Reform needs new variable / formula logic</td>
              <td>Open model-extension backlog issue in policyengine-&#123;country&#125;.</td>
            </tr>
            <tr>
              <td>
                <span className="verdict verdict-impossible">not-possible</span>
              </td>
              <td>Out of model scope (audit policy, enforcement, etc.)</td>
              <td>Redefine the question or use a different tool.</td>
            </tr>
            <tr>
              <td>
                <span className="verdict verdict-lag">deployed-model-lag</span>
              </td>
              <td>Parameter exists on master but not yet in deployed API</td>
              <td>Wait for next PE-US release; re-run.</td>
            </tr>
          </tbody>
        </table>
      </Section>

      <Section title="Output — what you receive">
        <p>
          A single markdown report with 9 sections: reform table (with YAML paths) →
          classification (with all 5 pre-flight checks logged + reform-dict) → prior
          anchors → external benchmarks → microsim result (all poverty buckets including
          adult and senior; both relative and absolute Gini) → comparison + verdict →
          calibration diagnosis (if INVESTIGATE) → methodology (carried forward from
          anchor) → known limitations.
        </p>
        <p>The report lands at:</p>
        <ul>
          <li>
            <code>/tmp/analyze-policy-&#123;policy_id&#125;.md</code> — always (the raw
            report)
          </li>
          <li>
            <code>analyses/YYYY-MM-DD-jurisdiction-slug.md</code> — archived with YAML
            frontmatter (policy_id, verdict, jurisdiction, benchmark_sources, tags)
          </li>
          <li>
            GitHub issue — auto-opened on INVESTIGATE or structural verdicts (the
            hypothesis is the issue body)
          </li>
        </ul>
      </Section>

      <Section title="Where it lives — archive path resolution">
        <p>The archive directory is resolved in this order:</p>
        <ol>
          <li>
            Explicit <code>--log-to archive:&lt;path&gt;</code>
          </li>
          <li>
            <code>$PWD/analyses/</code> if it exists
          </li>
          <li>
            <code>$POLICYENGINE_ANALYSES_DIR</code> environment variable
          </li>
          <li>
            <code>~/.policyengine/analyses/</code> (auto-created)
          </li>
        </ol>
        <p>
          The frontmatter is greppable for retrospective queries:{" "}
          <code>grep -l "verdict: INVESTIGATE" analyses/*.md</code>,{" "}
          <code>grep -l "state: ri" analyses/*.md</code>.
        </p>
      </Section>

      <Section title="Destination routing — runtime prompt, context-aware">
        <p>
          The pipeline detects the current repo and verdict, surfaces a shortlist
          tailored to the context, and asks the analyst to pick. Pre-selected defaults:
        </p>
        <table className="guide-table">
          <thead>
            <tr>
              <th>Verdict</th>
              <th>Pre-selected</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>PASS / PASS-WITH-NOTES / PASS-WITH-CORROBORATION</td>
              <td>Local archive only</td>
            </tr>
            <tr>
              <td>INVESTIGATE</td>
              <td>
                Local archive + GH issue in policyengine-&#123;country&#125;-data
                (calibration hypothesis as action item)
              </td>
            </tr>
            <tr>
              <td>structural</td>
              <td>
                Local archive + GH issue in policyengine-&#123;country&#125; (model-change
                estimate as action item)
              </td>
            </tr>
            <tr>
              <td>not-possible / deployed-model-lag</td>
              <td>Local archive only (rationale documented)</td>
            </tr>
          </tbody>
        </table>
        <p>
          Context-specific additions in the prompt:
        </p>
        <ul>
          <li>
            Inside <code>policyengine-app</code> → "Save as draft research post:{" "}
            <code>src/posts/articles/&#123;slug&#125;.md</code> + update{" "}
            <code>posts.json</code>"
          </li>
          <li>
            Inside any PE repo → corresponding <code>gh issue</code> option
          </li>
          <li>
            Always → "Custom path / repo — type a destination spec"
          </li>
        </ul>
        <p>
          All non-local destinations show a body preview (Y/N/edit) before submission.
          Skip the prompt with <code>--auto-confirm</code>, override the routing entirely
          with <code>--log-to &lt;dest&gt;,&lt;dest&gt;</code>, or suppress all logging
          with <code>--no-log</code>.
        </p>
      </Section>

      <Section title="Constraints — what to know before relying on it">
        <ul className="guide-warnings">
          <li>
            <strong>Live microsim is single-year only.</strong> 10-year cost is
            extrapolated. Naive year-1 × 11 fails across regime shifts (e.g., 2030 OBBBA
            SALT snap-back). For publication, run the snap-back year directly.
          </li>
          <li>
            <strong>State-level variance is real.</strong> Comparator auto-widens tolerance
            ×1.5 for small states (sub-10K CPS records), ×1.3 for narrow populations, ×1.5
            for baseline mismatch. RI / VT / WY / AK / ND / SD / DE / MT / NH / ME / HI /
            ID / NM / NE / WV / UT trigger small-state widening.
          </li>
          <li>
            <strong>Stage 6 quality depends on SKILL coverage.</strong> CTC and SALT rows
            in the calibration-diagnostics SKILL are well-developed. EITC / small-state /
            UK rows are thinner — the agent flags this honestly via{" "}
            <code>coverage_note</code>.
          </li>
          <li>
            <strong>Deployed-model lag is real.</strong> Parameters can land on master
            days/weeks before the deployed API has them. Pre-flight check catches this and
            falls back to process-test mode.
          </li>
          <li>
            <strong>`.inf` only works for float-typed parameters.</strong> Integer-typed
            (ages, qualifying-children counts) need a large numeric like <code>999</code>.
            Pre-flight handles this; don't override.
          </li>
          <li>
            <strong>Wall-clock:</strong> 10-15 min per live federal run. ~30 min when
            iterating reform-dict shape. State runs blocked by deployed lag take seconds
            (caught by pre-flight).
          </li>
        </ul>
      </Section>

      <Section title="Related commands">
        <ul>
          <li>
            <code>/encode-policy-v2</code> — implements a NEW benefit program (parameters,
            variables, tests). Use when the model needs to be extended before analysis.
          </li>
          <li>
            <code>/encode-bill</code> (in <code>state-legislative-tracker</code>) — same
            intelligence plus Supabase DB write. Use inside the tracker repo for state-bill
            scoring.
          </li>
          <li>
            <code>/review-program</code>, <code>/review-pr</code> — for PR review rather
            than reform analysis.
          </li>
          <li>
            <code>/encode-reform</code> — implements a contributed reform under{" "}
            <code>gov/contrib/</code>.
          </li>
        </ul>
      </Section>

      <Section title="Five live tests on record">
        <table className="guide-table">
          <thead>
            <tr>
              <th>Reform</th>
              <th>Verdict</th>
              <th>What it surfaced</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>CTC ARPA-style (federal)</td>
              <td>PASS-WITH-NOTES</td>
              <td>Bracket-indexed paths, phase_out.arpa toggle requirement</td>
            </tr>
            <tr>
              <td>SALT cap repeal (federal)</td>
              <td>INVESTIGATE → Stage 6 verified</td>
              <td>/over/&#123;baseline_id&#125; semantics, real response schema</td>
            </tr>
            <tr>
              <td>EITC ARPA-style (federal)</td>
              <td>PASS-WITH-NOTES</td>
              <td>.inf int-vs-float distinction; senior poverty headline metric</td>
            </tr>
            <tr>
              <td>RI state CTC $250</td>
              <td>BLOCKED (deployed-lag, caught cleanly)</td>
              <td>Metadata pre-flight, future-dated parameter family</td>
            </tr>
            <tr>
              <td>VT EITC match increase</td>
              <td>PASS-WITH-NOTES</td>
              <td>
                <code>where()</code>-deadens-leaf trap, auto-widening end-to-end (×2.93)
              </td>
            </tr>
            <tr>
              <td>SALT cap → flat $60K (federal)</td>
              <td>PASS-WITH-NOTES with 2/4 external agreement</td>
              <td>
                Mandatory benchmarks — CRFB, TPC, Tax Foundation, Penn Wharton bracketing
              </td>
            </tr>
          </tbody>
        </table>
      </Section>

      <footer className="guide-footer">
        <p>
          <strong>Source files:</strong>{" "}
          <code>targets/claude/commands/analyze-policy.md</code> (command),{" "}
          <code>targets/claude/agents/</code> (8 agents),{" "}
          <code>skills/domain-knowledge/policyengine-prior-scores-skill/</code> and{" "}
          <code>policyengine-calibration-diagnostics-skill/</code> (2 skills).
        </p>
      </footer>
    </article>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="guide-section">
      <h3 className="guide-section-title">{title}</h3>
      {children}
    </section>
  );
}

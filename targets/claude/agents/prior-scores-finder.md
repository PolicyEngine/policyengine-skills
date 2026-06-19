---
name: prior-scores-finder
description: Finds prior scored reforms to anchor a new analysis — PolicyEngine's own published scores first, then official fiscal notes (state legislative fiscal offices, JCT, CBO, CRFB), then think-tank analyses (Tax Foundation, ITEP, CBPP, TPC). Generalizes the legislative-tracker fiscal-finder by adding the PolicyEngine prior-scores layer.
tools: WebFetch, WebSearch, Read, Bash, Skill
model: sonnet
---

# Prior Scores Finder

Returns a ranked list of analog reforms with **specific magnitudes** (10-year cost, distributional impact, poverty effect) for use as the ground-truth anchor in Stage 5 comparison.

## Inputs

- `reform` (description + provisions from `policy-text-researcher`)
- `jurisdiction` (`{country, state?}`)

## Process

### Tier 1: PolicyEngine prior scores (highest priority)

The closest comparison is PolicyEngine's own previously-published score of an analogous reform.

1. Invoke the `policyengine-prior-scores` skill (structured index of PE-published reforms).
2. If the skill doesn't return a hit, fall back to:
   - `WebFetch policyengine.org/{country}/research` — browsable index.
   - `WebSearch "site:policyengine.org {reform_keywords}"`.
   - `WebFetch blog.policyengine.org` (note: Medium redirect may need fallback).
3. Also check `policyengine-research-lookup` skill for blog posts.
4. Cross-reference dedicated calculators (e.g., `ri-ctc-calculator`, `salternative`, `vance-harris-ctc-comparison`) for anchor numbers.

Extract for each PE prior:
- Reform name + URL
- Year of analysis
- 10-year cost or single-year cost
- Distributional impact (Gini, top-decile share)
- Poverty impact (overall + child)
- Methodology notes (static / dynamic, dataset version)

### Tier 2: Official fiscal notes

For state bills, find the legislative fiscal office note:

| State | Source |
|---|---|
| UT | `le.utah.gov/~{year}/fiscalnotes/{bill}.pdf` |
| SC | `scstatehouse.gov` → Bill page → "Fiscal Impact" |
| OK | `oklegislature.gov` → Bill page → "Fiscal Analysis" |
| NY | `nyassembly.gov` → "Fiscal Note" |
| CA | `lao.ca.gov` (Legislative Analyst's Office) |
| NC | `sites.ncleg.gov/frd/fiscal-notes/` |
| CT | `cga.ct.gov/ofa/` |
| KS | `kslegislature.gov` → Fiscal Note PDF |
| ND | `ndlegis.gov` → "Fiscal Notes" tab |
| IL | `ilga.gov` → "Fiscal Note" |
| RI | `rilegislature.gov` → Fiscal Note |
| WV | `wvlegislature.gov` → Fiscal Note |
| GA | `legis.ga.gov` → Fiscal Note |

For federal: JCT scores at `jct.gov/publications`, CBO at `cbo.gov`.

### Tier 3: Think-tank analyses

```
"{reform_keywords}" site:taxfoundation.org
"{reform_keywords}" site:itep.org
"{reform_keywords}" site:cbpp.org
"{reform_keywords}" site:taxpolicycenter.org
"{reform_keywords}" site:crfb.org
```

Extract magnitudes — these are external validation, not primary anchors.

### Output

```json
{
  "anchors": [
    {
      "tier": "pe-prior",
      "title": "Restoration of the ARPA expanded CTC",
      "url": "https://policyengine.org/us/research/...",
      "year": 2023,
      "magnitudes": {
        "annual_cost_billion": 100.2,
        "ten_year_cost_billion": null,
        "child_poverty_pct_change": -37.0,
        "overall_poverty_pct_change": -9.0,
        "gini_pct_change": -1.9
      },
      "methodology": {
        "dataset": "Enhanced CPS 2023",
        "static_or_dynamic": "static",
        "time_window": "single-year-2023",
        "behavioral_assumptions": "no labor-supply response"
      }
    }
  ],
  "official_scores": [...],
  "thinktank_scores": [...],
  "preferred_anchor_index": 0,
  "anchor_notes": "PE 'Restoration' analysis matches reform parameters line-for-line. Single-year score must be extrapolated to 10-year window using +10-12% uprating."
}
```

The `methodology` object is structured so the `reform-comparator` can carry it forward into its `methodology_carried_forward` field and the final report's Methodology section gets a consistent shape.

If **no PE prior exists**, surface that explicitly — that's a signal the reform is novel for PE and the comparator should weight official/think-tank scores more heavily.

## Hand-off

Returns the anchor list. Downstream:
- `reform-comparator` (Stage 5) uses the preferred anchor to bracket the expected microsim magnitude.
- `calibration-diagnostics` (Stage 6) reads `methodology_notes` to identify whose calibration the prior was built on.

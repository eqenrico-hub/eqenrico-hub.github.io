---
title: "SHARE4MED × Paper 1 — PhD research informs an industrial EU project"
subtitle: "A systematic benchmark of 114 urban dashboards against the SHARE4MED electronic Governance Dashboard being built by ETT S.p.A. for Interreg NEXT MED"
order: 4
date: 2026-04-18
excerpt: "How a systematic review of 86 peer-reviewed urban dashboards (my PhD Paper 1 at UniGe) was used to benchmark the SHARE4MED Mediterranean-coalition Governance Dashboard designed at ETT. Identifies the exact literature gap the industrial project fills."
---

## Context

I study urban dashboards at the University of Genoa (PhD XXXIX cycle, *Management and Security* curriculum, supervisor Prof. R. P. Dameri). My **Paper 1** — *Governing and managing cities through urban dashboards: looking for a taxonomy of tools* — is a systematic review and taxonomy of **86 urban dashboards** from peer-reviewed literature, classifying each on 24 functional and thematic features (Revina 2021 goal classes + bottom-up end-user typology + 8-domain textual analysis + additional functional features, following Kitchin et al. 2016's umbrella definition).

In parallel, through the RAISE / SPOKE 1 programme, I am attached to **ETT S.p.A.**, the company building the **SHARE4MED electronic Governance Dashboard** (Output 4.1 of the [Interreg NEXT MED](https://www.interregnextmed.eu/) project SHARE4MED — a coalition-level dashboard for Mediterranean municipalities, tracking Mission Ocean 2030 targets). In the SHARE4MED application form the tool is called *Governance Dashboard*, *electronic Governance Dashboard (eGD)* or *Coalition Dashboard* — never *urban dashboard*; this note respects that convention. For the purposes of Paper 1's analytical framework, however, a coalition-level decision-support platform of this kind falls inside the *urban dashboard* umbrella as defined by Kitchin et al. (2016).

This note documents a single concrete exercise: **using Paper 1's taxonomy as a filter to test whether the existing literature already describes a platform like SHARE4MED**, and if not, what components of SHARE4MED are novel and what components are literature-attested.

## The question, in operational form

The SHARE4MED electronic Governance Dashboard is characterised by four elements:

- **A — Cross-border / inter-municipal scope.** It serves a coalition of Mediterranean municipalities across the northern and southern shore, not a single city or a single country.
- **B — Multi-thematic breadth.** It integrates governance, environment / Mission Ocean 2030, and economic-development indicators in one platform.
- **C — Strategic KPI framework.** It is target-driven (distance to Mission Ocean 2030), not plain descriptive statistics.
- **D — Coalition governance decision-support layer.** It is a space in which a named group of municipalities decides together — not a one-way consultable benchmark portal.

Does the reviewed urban-dashboard literature already describe a platform combining all four? And if not, which of these components is literature-attested and which is genuinely new for SHARE4MED?

## Method

- **Sample.** The 86 dashboards of Paper 1's corpus plus 28 operational online platforms collected and coded against the same taxonomy. Total universe: 114.
- **Filter.** A taxonomy preset matching the SHARE4MED profile: `Integrated` AND `Performance metrics` AND (`Decision-making` OR `Information and Knowledge Management`) AND (`Public administrators and policymakers` OR `Business, professional users or researchers`) AND at least one of (`Governance and Urban planning`, `Environment and Energy`, `Economic development`). This yielded **47 candidates**.
- **Depth of analysis.**
  - 23 literature candidates read in full from the original peer-reviewed PDF.
  - 6 highest-ranked online platforms inspected via URL.
  - 18 lower-priority online platforms evaluated at metadata level only (declared limitation).
- **Scoring rubric.** +3 for cross-border scope, +2 for governance framing, +2 for strategic KPI targets, +1 for multi-thematic breadth, +1 for co-design, +1 for forecasting (bonus), −2 for single-city only, −2 for commercial. Component D was assessed qualitatively.

## Findings

### The four-component matrix

| Combination | Existing urban dashboards realising it | What is still missing for SHARE4MED |
|---|---|---|
| **A + B** | Eurostat Urban Audit / City Statistics; Regions and Cities Illustrated (Eurostat) | no target framework, no coalition decision-support |
| **A + C** | ROCK (EU H2020, Cultural Heritage, 3 pilot cities + 32 partners / 13 countries); Trafair (EU, 6 cities incl. Modena IT + Santiago de Compostela ES, traffic + air quality); ARCH (EU H2020, 4 cities, disaster risk + cultural heritage) | single-domain thematic focus, per-city instances without a coalition layer |
| **B + C** | Kourtit & Nijkamp 2018 — the Stockholm Pentagon / XXQ / CSF → ~70 KPI cascade | single-city, multi-city benchmark is literature-only |
| **A + B + C** | OECD Regions and Cities Atlas + OECD Local SDGs sibling; OECD SDG Distance Indicators; Arup City Resilience Index | no coalition decision layer, thin coverage of Southern-Mediterranean partner countries |
| **A + B + C + D for a named coalition** | **no documented case found in the 47 reviewed candidates** | this is SHARE4MED's space |

### What SHARE4MED can borrow from the literature

Four *deployed* multi-city platforms are suitable development benchmarks — ETT can actively model WP4 design on these:

- **ROCK (Turilazzi et al. 2021)** — multi-tier stack (CKAN + BI dashboards + Linked Open Data + SPARQL); participatory ontology; per-city replication with a shared semantic layer.
- **Trafair (Bachechi et al. 2022)** — open-source stack (PostgreSQL + PostGIS + TimescaleDB + GeoServer + Angular); scenario-comparison UI (PAIR 2020 vs. PUMS 2030); requirements-driven design; STL + IQR anomaly detection.
- **ARCH (Villani et al. 2023)** — 4-workshop co-creation methodology (W1–W4 + Miro + Risk Scenario Toolbox); UML "who / what / where / when / how" data model; low-code replicable architecture.
- **InDash (Zuo et al. 2023)** — 13 prefectural cities in Jiangsu, deployed and validated with 30 users; radar-chart composite-index pattern; user-centered design workflow.

Several other papers are **methodology references** for specific design decisions: the Adjusted Mazziotta-Pareto composite method (Lazar 2022), the target-distance wheel chart (OECD Local SDGs), the hierarchical resilience cascade (Arup CRI), the third-party-rating-as-KPI-backbone pattern (Ferdinand 2016), the KPI funnel (Borsari 2023), the critical-theory caveats on dashboards as socio-technical assemblages (Kitchin 2016).

### What SHARE4MED adds

The *coalition* element **D** — a genuinely multi-actor decision workspace for a named group of municipalities with shared targets — is the piece the reviewed literature does not document. Combined with the Southern-Mediterranean geographic scope that OECD and Eurostat do not cover at sub-national granularity, this makes SHARE4MED a **literature-informed integration in a configuration the reviewed corpus has not yet tested** — not an invention from scratch, but not a replication either.

## Why this matters beyond this one project

This is a concrete test of a claim that is too often asserted and too rarely demonstrated: that a systematic taxonomy of urban dashboards has *predictive* value — that it can, given a proposed new platform, tell you which of its components are already solved and which are genuinely novel. For the 47 candidates this filter produced, the answer is sharp: **three of the four SHARE4MED components are attested in separate and adjacent ways**, and **the fourth is where the actual design work lives**. The taxonomy does not just describe a landscape; it maps where the gaps are.

## Files produced (local to the working copy)

`SHARE4MED_profile.md` (reference profile), `priority_ranking.md` (abstract-based priority list), `reports/L1…L23` (full-PDF reviews), `reports/O1…O6` (URL inspections), `SHARE4MED_benchmark_synthesis.md` (the consolidated deliverable that will feed the WP4 literature-context section of the proposal).

## References

Key literature mentioned:

- Kitchin, R., Lauriault, T., McArdle, G. (2016). *Knowing and governing cities through urban indicators, city benchmarking and real-time dashboards.*
- Revina, A. (2021). *Classification of dashboards by goal.*
- Turilazzi, B., Leoni, G., Gaspari, J., Masari, M., Boulanger, S.O. (2021). *Cultural Heritage and Digital Tools: the ROCK Interoperable Platform.*
- Bachechi, C., Po, L., Rollo, F. (2022). *Big Data Analytics and Visualization in Traffic Monitoring.*
- Villani, M.L., Giovinazzi, S., Costanzo, A. (2023). *Co-Creating GIS-Based Dashboards to Democratize Knowledge on Urban Resilience Strategies.*
- Zuo, C., Ding, L., Liu, X., Zhang, H., Meng, L. (2023). *Map-based dashboard design with open government data.*
- Kourtit, K., Nijkamp, P. (2018). *Big data dashboards as smart decision support tools for i-cities.*
- Lazar, D., Litan, C.M. (2022). *Regional well-being in Romania: assessment after a decade of EU accession.*

Benchmarked online platforms: OECD Regions and Cities Atlas; OECD Local SDGs; OECD SDG Distance Indicators; OECD Subnational Government Dashboard; Eurostat Urban Audit; Eurostat Regions and Cities Illustrated; Arup City Resilience Index.

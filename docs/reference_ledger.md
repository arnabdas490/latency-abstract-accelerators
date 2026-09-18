# Reference and Claim Ledger

Status: working research record
Updated: 2026-09-18

Purpose: map every important project claim to primary literature or current
documentation and record what that evidence does and does not establish.

This document deliberately separates established prior work from candidate
research gaps.

## Evidence levels

- A: direct primary-paper section, figure, rule, or current documentation.
- B: primary-paper abstract or project documentation sufficient for scope.
- C: preliminary adjacent-work check; must not support strong negative claims.

---

## CALYX-1 — Calyx

Citation:

Rachit Nigam, Samuel Thomas, Zhijing Li, and Adrian Sampson.
"A Compiler Infrastructure for Accelerator Generators."
ASPLOS 2021.
DOI: 10.1145/3445814.3446712.

Current documentation:

- Calyx Documentation, "Static Timing."
- Calyx Documentation, "Attributes."
- Accessed 2026-09-18.

Evidence used:

- Calyx provides accelerator structure plus explicit control.
- Current Calyx distinguishes default dynamic/latency-insensitive control from
  static constructs carrying concrete cycle counts.
- Static timing composition includes concrete sequential/parallel timing.
- Current attributes include numeric timing information such as promotion
  hints and interval guarantees.

What this establishes:

Concrete static timing and static/dynamic interaction already exist in Calyx.

What it does not establish:

The audit does not establish that no Calyx extension or downstream project
can represent generator-dependent symbolic timing.

Project consequence:

Do not claim static timing, seq/par timing, or static children inside dynamic
control as new.

Evidence level: A.

---

## FILAMENT-1 — Filament

Citation:

Rachit Nigam, Pedro Henrique Azevedo de Amorim, and Adrian Sampson.
"Modular Hardware Design with Timeline Types."
PLDI 2023.
DOI: 10.1145/3591234.

Evidence used:

Filament uses timeline types to encode temporal and structural constraints at
hardware interfaces and supports modular composition of statically scheduled
pipelines.

What this establishes:

Temporal contracts at module boundaries are established prior work.

Project consequence:

Do not claim generic modular timing interfaces or timing-safe static module
composition.

Evidence level: A/B.

---

## PIEZO-1 — Piezo unified control

Citation:

Caleb Kim, Pai Li, Anshuman Mohan, Andrew Butt, Adrian Sampson, and
Rachit Nigam.
"Unifying Static and Dynamic Intermediate Languages for Accelerator
Generators."
OOPSLA 2024.
DOI: 10.1145/3689790.

Evidence used:

The paper introduces Piezo, where static constructs are semantic refinements
of dynamic counterparts. Static and dynamic accelerator control coexist in a
single IR, enabling cross-boundary optimization.

Locator:

- Introduction and semantic motivation.
- Section on interaction between static and dynamic constructs.

What this establishes:

Mixed static/dynamic accelerator control is prior work.

Project consequence:

Do not claim LS+LI unification.

Evidence level: A.

---

## PIEZO-2 — fixed-latency inference

Same citation as PIEZO-1.

Evidence used:

Piezo can infer a static version of dynamic code when it can determine a
constant latency and then optionally promote the region.

Locator:

- Static inference/promotion discussion, approximately Section 5.1 in the
  OOPSLA 2024 paper.

What this establishes:

Once constant timing is available, Piezo already has machinery for converting
eligible dynamic regions to static ones.

Project consequence:

A system that merely resolves LA externally and feeds concrete timing into
Piezo is a serious baseline.

Evidence level: A.

---

## LILAC-1 — latency-abstract interfaces

Citation:

Rachit Nigam, Ethan Gabizon, Edmund Lam, Carolyn Zech, Jonathan Balkind,
and Adrian Sampson.
"Parameterized Hardware Design with Latency-Abstract Interfaces."
ASPLOS 2026.
DOI: 10.1145/3779212.3790199.

Evidence used:

Lilac represents generated hardware whose temporal behavior is unknown during
design but becomes concrete during generator elaboration.

Output parameters expose generator-produced temporal facts upward.

What this establishes:

Latency abstraction itself is prior work.

Project consequence:

Do not claim LA interfaces or generator-produced latency parameters.

Evidence level: A.

---

## LILAC-2 — hierarchical symbolic timing

Same citation as LILAC-1.

Evidence used:

Lilac composes child output parameters symbolically. Examples include parent
timing expressions built from child latencies while those values remain
abstract.

Locator used in audit:

- Early language/examples section, including the generated FPU example.

What this establishes:

Hierarchical symbolic timing propagation and checking are already supported
within the LA setting.

Project consequence:

V1.3 component timing summaries alone are not a novelty argument.

Evidence level: A.

---

## LILAC-3 — richer temporal contracts

Same citation as LILAC-1.

Evidence used:

Lilac temporal interfaces describe more than one terminal scalar latency.
The paper discusses temporal availability relationships and throughput /
initiation-interval-like behavior in generator interfaces.

What this establishes:

The information available at an LA boundary can be richer than scalar
latency.

Project consequence:

A future mixed-control boundary may need to study whether preserving richer
temporal information has value.

Important limitation:

Existence of richer temporal contracts does not prove that Piezo or another
higher-level IR needs all of them.

Evidence level: A.

---

## LILAC-4 — LI remains necessary / future-work boundary

Same citation as LILAC-1.

Evidence used:

Lilac explicitly states that LA does not replace latency-insensitive
interfaces for genuinely input-dependent behavior and identifies unification
of LI and LA abstractions as future work.

Locator used in audit:

- Future Work section near the end of the paper.

What this establishes:

The LA+LI interaction is explicitly acknowledged as an open direction by the
Lilac authors.

What it does not establish:

It does not establish that the specific abstraction proposed in this project
is novel or correct.

Project consequence:

This is the strongest motivation for studying an LA-to-mixed-control staging
boundary.

Evidence level: A.

---

## LILAC-5 — elaborate-LA-first baseline

Same citation as LILAC-1.

Evidence used:

Lilac discusses composing LA modules into larger LA regions/islands and
connecting them to latency-insensitive contexts.

What this establishes:

A practical design strategy is to resolve a sufficiently large LA subsystem
and expose an LI-facing boundary.

Project consequence:

"Resolve LA first, then hand concrete timing to Piezo/Calyx" must be treated
as the project's strongest baseline, not a straw man.

Evidence level: A.

---

## DASS-1 — static islands in dynamic hardware

Citation:

Jianyi Cheng, Lana Josipović, George A. Constantinides,
Paolo Ienne, and John Wickerson.
"DASS: Combining Dynamic & Static Scheduling in High-Level Synthesis."
IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems,
41(3):628-641, 2022.
DOI: 10.1109/TCAD.2021.3065902.

Supplementary background:

Jianyi Cheng.
"Combining Dynamic and Static Scheduling in High-Level Synthesis."
PhD thesis, Imperial College London, 2023.
DOI: 10.25560/105815.

Evidence used:

DASS identifies regions amenable to static scheduling, synthesizes them as
statically scheduled components ("static islands"), and leaves top-level
hardware dynamically scheduled.

What this establishes:

Static islands inside dynamically scheduled hardware are established prior
work.

Project consequence:

Do not claim this architecture itself.

Evidence level: B/A from thesis abstract and description.

---

## ANVIL-1 — timing-safe dynamic contracts

Citation:

Jason Zhijingcheng Yu, Aditya Ranjan Jha, Umang Mathur,
Trevor E. Carlson, and Prateek Saxena.
"Anvil: A General-Purpose Timing-Safe Hardware Description Language."
ASPLOS 2026.
Preprint: arXiv:2503.19447.

Evidence used:

Anvil statically enforces timing contracts across communicating modules and
can parameterize contracts over abstract runtime time points.

What this establishes:

Timing-safe modular interfaces can express dynamic timing behavior.

Project consequence:

The proposed project must distinguish generator/elaboration-time uncertainty
from runtime timing uncertainty.

Evidence level: B.

---

## HIR-1 — explicit accelerator scheduling

Citation:

Kingshuk Majumder and Uday Bondhugula.
"HIR: An MLIR-based Intermediate Representation for Hardware Accelerator
Description."
arXiv:2103.00194.

Evidence used:

HIR combines high-level accelerator representation with programmer-defined
explicit schedules and synchronization-free static parallelism.

What this establishes:

Explicit accelerator scheduling is established prior work.

Project consequence:

Do not claim scheduling machinery itself.

Evidence level: B.

---

## ALLO-1 — hierarchical composition

Citation:

Hongzheng Chen, Niansong Zhang, Shaojie Xiang, Zhichen Zeng,
Mengjia Dai, and Zhiru Zhang.
"Allo: A Programming Model for Composable Accelerator Design."
PLDI 2024.
arXiv:2404.04815.

Evidence used:

Allo preserves program hierarchy and combines accelerator customizations
bottom-up and type-safely across functions.

What this establishes:

Hierarchical, composable accelerator design is established prior work.

What it does not establish:

This audit has not found evidence in the primary abstract/material inspected
that Allo provides Lilac-style generator output timing parameters inside a
mixed LI/LS IR.

Project consequence:

Do not make generic hierarchy/composability claims.

Evidence level: B/C for the negative comparison.

---

## CIRCT-1 — current scheduling infrastructure

Source:

LLVM CIRCT, current Scheduling documentation and
`circt/Scheduling/Problems.h`.
Accessed 2026-09-18.

Evidence used:

The scheduling infrastructure associates operator types with concrete integer
latencies and computes integer start times subject to constraints. The current
API includes `setLatency(OperatorType, unsigned)`.

What this establishes:

CIRCT has reusable scheduling infrastructure for clients that supply concrete
latency facts.

What it does not establish:

This evidence does not justify the broad claim that the CIRCT ecosystem cannot
represent latency abstraction by another mechanism.

Project consequence:

Treat CIRCT as relevant adjacent infrastructure, not as evidence of absence.

Evidence level: A for the scheduling API; C for ecosystem-level conclusions.

---

## Canonical source and locator index

This index records the exact primary source used for each claim. Page numbers
refer to the cited paper version where applicable. Documentation entries use
their exact heading because web documentation is not paginated.

| ID | Canonical source | Version / year | Exact locator used | Accessed |
|---|---|---|---|---|
| CALYX-1 | https://docs.calyxir.org/lang/static.html and https://docs.calyxir.org/lang/attributes.html | current documentation | `Static Timing` -> `Static Constructs in the Calyx IL` -> `Static Control Operators`; `Attributes` -> `Meaning of Attributes` -> `promotable(n)` and `interval(n)` | 2026-09-18 |
| FILAMENT-1 | https://doi.org/10.1145/3591234 ; preprint https://arxiv.org/abs/2304.10646 | PLDI 2023 | Abstract; §1; §2.2 `Filament`; timeline-type interface discussion | 2026-09-18 |
| PIEZO-1 | https://doi.org/10.1145/3689790 | OOPSLA 2024 | Abstract; §4 `Compilation`; Table 1 `Interfaces between types of control` | 2026-09-18 |
| PIEZO-2 | https://doi.org/10.1145/3689790 | OOPSLA 2024 | §5.1 `Static Inference and Promotion`, especially the constant-latency inference conditions | 2026-09-18 |
| LILAC-1 | https://doi.org/10.1145/3779212.3790199 ; author PDF https://people.csail.mit.edu/rachit/files/pubs/lilac.pdf | ASPLOS 2026 | §3.1 `Specifying Latency-Abstract Interfaces`; Fig. 4 | 2026-09-18 |
| LILAC-2 | same as LILAC-1 | ASPLOS 2026 | §3.2; Fig. 5 `Latency-abstract FPU implementation in Lilac` | 2026-09-18 |
| LILAC-3 | same as LILAC-1 | ASPLOS 2026 | §6.2 `LA Interfaces for Generators`, Table 3; §7.1, Figs. 10-11 | 2026-09-18 |
| LILAC-4 | same as LILAC-1 | ASPLOS 2026 | §9 `Future Work` | 2026-09-18 |
| LILAC-5 | same as LILAC-1 | ASPLOS 2026 | §7.2 `Cost of Latency Insensitivity`, discussion of LA "islands" wrapped with LI interfaces | 2026-09-18 |
| DASS-1 | https://doi.org/10.1109/TCAD.2021.3065902 | IEEE TCAD 2022 | Abstract; §I `Introduction`; Fig. 1 and description of statically scheduled regions within dynamically scheduled hardware | 2026-09-18 |
| ANVIL-1 | https://arxiv.org/abs/2503.19447 | ASPLOS 2026 / preprint | Abstract; timing-contract discussion concerning abstract runtime time points | 2026-09-18 |
| HIR-1 | https://arxiv.org/abs/2103.00194 | 2021 preprint | Abstract and introductory description of explicit accelerator schedules | 2026-09-18 |
| ALLO-1 | https://arxiv.org/abs/2404.04815 | PLDI 2024 | Abstract and hierarchical/composable customization discussion | 2026-09-18 |
| CIRCT-1 | https://github.com/llvm/circt/blob/main/docs/Scheduling.md and https://github.com/llvm/circt/blob/main/include/circt/Scheduling/Problems.h | current main branch | `Static scheduling infrastructure` -> `Getting started` -> `Constructing a problem instance`; `Problem::getLatency` / `Problem::setLatency` | 2026-09-18 |

## Prior-work overlap and effect on the candidate gap

| ID | Overlap with V1.3 | Effect on candidate gap |
|---|---|---|
| CALYX-1 | V1.3 ultimately lowers to Calyx static/dynamic constructs and uses the same basic sum/max timing algebra. | Kills claims around concrete LS constructs or mixed static/dynamic containment; leaves generator-dependent staging open. |
| FILAMENT-1 | V1.3 component summaries overlap conceptually with modular temporal interfaces. | Kills generic modular-timing-interface claims. |
| PIEZO-1 | V1.3 targets the same broad mixed static/dynamic accelerator setting. | Kills LS+LI unification as a contribution. |
| PIEZO-2 | V1.3 eventually supplies concrete timing suitable for the kind of fixed-latency reasoning Piezo already performs. | Establishes the strongest downstream baseline: resolve LA first, then use Piezo. |
| LILAC-1 | V1.3 begins with the same class of generator-dependent timing that Lilac already abstracts. | Kills LA itself as a contribution. |
| LILAC-2 | V1.3 structurally propagates child timing; Lilac already performs symbolic hierarchical timing composition. | Kills bottom-up/hierarchical timing propagation as a novelty argument. |
| LILAC-3 | V1.3 exports only scalar component latency, while Lilac can represent II, event delays, parameter-dependent timing, and multi-cycle availability. | Supports the richer-contract research direction, but does not prove such information is required by a mixed-control IR. |
| LILAC-4 | V1.3 does not yet represent unresolved LA and genuine LI behavior together in one timing abstraction. | Directly motivates investigation of the LA/LI boundary; does not establish our proposed solution as novel. |
| LILAC-5 | V1.3 could plausibly be replaced by an architecture that builds/resolves an LA island first and wraps or hands it to an LI/mixed-control system. | Narrows the project sharply and supplies the research-level kill baseline. |
| DASS-1 | DASS already places statically scheduled regions inside dynamically scheduled hardware. | Kills static-island-inside-dynamic claims. |
| ANVIL-1 | Anvil overlaps with timing-safe modular contracts that include dynamic timing behavior. | Forces a distinction between runtime timing abstraction and generator/elaboration-time timing abstraction. |
| HIR-1 | HIR overlaps with explicit static scheduling machinery. | Kills generic scheduling claims; no strong negative conclusion about LA is drawn. |
| ALLO-1 | Allo overlaps with hierarchical accelerator composition and bottom-up customization. | Kills generic hierarchy/composability claims; current audit does not establish absence of all LA-like mechanisms. |
| CIRCT-1 | CIRCT can schedule once concrete integer latency properties are supplied. | Potential implementation substrate; current API evidence does not establish ecosystem-wide absence of LA support. |

## Project claim ledger

## Dead claims

Do not use:

- "first latency-abstract generator interface";
- "first bottom-up timing propagation";
- "first symbolic hierarchical latency composition";
- "first modular timing interface";
- "first mixed static/dynamic accelerator IR";
- "first static islands inside dynamic hardware";
- "first hierarchical accelerator composition."

## Safe V1.3 claims

- V1.3 is an exploratory compiler prototype for the LA-to-mixed-control
  boundary.
- Generator timing is absent from the canonical source.
- One unchanged source and symbolic IR handle five generated timing
  configurations.
- The prototype infers reusable component timing after elaboration.
- A parent reasons using child timing summaries rather than child
  implementation bodies or direct generator facts.
- Parent-level constraints can accept or reject generated configurations.
- Accepted variants lower to Calyx and execute through Verilator.
- V1.3 is proof-of-mechanism, not proof of novelty.

## Candidate research claim

The project investigates whether latency abstraction should persist as an
elaboration-time state inside a mixed-control accelerator IR instead of being
fully eliminated before that IR receives the generated component.

Status: candidate question only.

## Research-level kill test

If:

    LA composition and checking in Lilac
        -> generator elaboration
        -> concrete timed module
        -> Piezo/Calyx

provides all useful correctness, modularity, scheduling, and optimization,
then no additional unified abstraction is justified.

## Evidence still required

A stronger system must demonstrate at least one useful property whose natural
scope crosses the LA/LI boundary while LA information remains unresolved.

Possible directions:

- cross-layer symbolic constraint;
- richer temporal-interface preservation;
- scheduling/specialization dependent on unresolved LA facts;
- correctness property spanning LA and LI regions;
- optimization that cannot be cleanly decomposed into
  "Lilac first, Piezo second."

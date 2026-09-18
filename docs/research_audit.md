# Research Audit: Latency Abstraction at the Mixed-Control Boundary

Status: working research audit, not a novelty claim
Updated: 2026-09-18
Frozen implementation baseline: `v1.3-freeze`

## 1. Research question

How should latency-abstract temporal contracts from generated hardware cross
into a higher-level mixed-control accelerator IR, so generated regions can
remain abstract during composition, refine to statically scheduled behavior
when elaboration resolves their timing, and coexist with genuinely
runtime-variable control?

## 2. Candidate gap

Existing systems separately provide:

- latency-abstract generator interfaces and symbolic temporal composition;
- modular static timing contracts;
- mixed static/dynamic accelerator control;
- static scheduling infrastructure once concrete timing is available.

The candidate gap is therefore not any of those capabilities independently.

The remaining question is the staging boundary between them: whether
generator-dependent temporal information should remain first-class inside a
mixed-control accelerator IR long enough to support reasoning,
specialization, or correctness checking before all timing has been
concretized.

This remains a candidate research question, not an established novelty claim.

## 3. What prior work already owns

### Calyx

Calyx provides a reusable accelerator compiler IR with hardware structure and
software-like control. Its current timing model includes concrete static timing
constructs such as `static<n>`, along with dynamic control.

Consequence:

- Do not claim concrete static timing.
- Do not claim structural `seq`/`par` timing composition.
- Do not claim dynamic parents containing statically timed regions as new.

### Filament

Filament provides modular temporal interfaces for statically scheduled
hardware using timeline types.

Consequence:

- Do not claim modular timing contracts in general.
- Do not claim temporal interfaces across hardware modules in general.

### Piezo

Piezo unifies static and dynamic accelerator control in one IR by treating
static behavior as a refinement of dynamic behavior. It supports
cross-boundary optimization and can infer/promote fixed-latency dynamic
regions when constant timing is known.

Consequence:

- Do not claim mixed static/dynamic accelerator control.
- Do not claim runtime-dynamic control containing static children.
- Do not claim dynamic-to-static promotion after fixed timing becomes known.

### Lilac

Lilac provides latency-abstract interfaces for generated hardware whose timing
is unknown during design but becomes concrete during generator elaboration.

Lilac also supports:

- output timing parameters;
- bottom-up timing propagation;
- hierarchical symbolic temporal composition;
- correctness checking while timing remains abstract;
- richer temporal information than a single latency value.

Lilac explicitly distinguishes LA from genuinely latency-insensitive behavior
and identifies unification of LI and LA abstractions as future work.

Consequence:

- Do not claim latency abstraction itself.
- Do not claim generator output parameters.
- Do not claim bottom-up generator timing propagation.
- Do not claim hierarchical symbolic timing composition.

### DASS

DASS combines dynamic and static scheduling by creating statically scheduled
"static islands" while leaving surrounding hardware dynamically scheduled.

Consequence:

- Do not claim static islands within dynamically controlled hardware.

### Anvil

Anvil provides timing-safe modular composition and timing contracts that can
express dynamic timing behavior.

Consequence:

- Do not claim timing-safe modular hardware interfaces broadly.
- Distinguish generator/elaboration-time uncertainty from runtime timing
  uncertainty.

### HIR

HIR provides explicit schedules and synchronization-free static accelerator
execution.

Consequence:

- Do not claim explicit accelerator scheduling itself.

### Allo

Allo provides hierarchical, bottom-up, type-safe composition of accelerator
customizations.

Consequence:

- Do not claim hierarchical accelerator composition itself.

### CIRCT scheduling

Current CIRCT scheduling infrastructure accepts concrete integer operator
latencies and computes schedules satisfying timing/dependence constraints.

Consequence:

- CIRCT is relevant infrastructure once latency information is supplied.
- Current audit evidence does not establish that CIRCT cannot express LA
  through some other mechanism.
- Do not make a negative claim about the entire CIRCT ecosystem from the
  scheduling API alone.

## 4. Strong baseline: elaborate LA first

The strongest adversarial baseline is:

    Lilac / LA subsystem
            |
       symbolic composition
            |
       generator elaboration
            |
       concrete timing
            |
       ordinary LS component
            |
       Piezo / Calyx
            |
       mixed static/dynamic accelerator

This may already be the correct architecture. Lilac itself discusses a
design style in which smaller components are connected using LA interfaces
until they form a sufficiently large LA "island," which is then wrapped with
an LI interface.

If an elaborate-first pipeline of this form provides all useful reasoning,
modularity, correctness, and optimization before handing a concretely timed
component to Piezo/Calyx, then an additional cross-layer abstraction is
unnecessary.

This is the research-level kill test.

## 5. What V1.3 demonstrates

V1.3 is a proof-of-mechanism, not a novelty result.

The prototype demonstrates:

1. Generator timing is absent from the source program.
2. Generator elaboration produces physical timing facts.
3. Structural timing is inferred through reusable components.
4. Components export timing summaries.
5. Parent timing analysis receives child interfaces rather than child
   implementation bodies or generator facts.
6. Parent-level constraints can accept or reject generated configurations.
7. Accepted programs lower to Calyx and execute through Verilator.
8. One unchanged source and symbolic IR handle all tested configurations.

The canonical C1/C2 reversal is:

    C1: A=2, B=5
        T_pair=5
        T_tail=2
        T_total=7
        ACCEPT

    C2: A=5, B=2
        T_pair=5
        T_tail=5
        T_total=10
        REJECT

The source program and symbolic IR are identical across the two
configurations.

## 6. What V1.3 does not demonstrate

V1.3 currently resolves generator timing before higher-level component timing
is resolved.

It does not yet demonstrate:

- symbolic LA timing surviving deeply into mixed-control IR;
- richer LA temporal contracts crossing that boundary;
- LA-aware partitioning while timing remains unresolved;
- cross-layer optimization that requires unresolved LA information;
- a formal LA-to-LS refinement semantics;
- novelty relative to the combined capabilities of existing systems.

## 7. Surviving stronger hypothesis

A useful unified accelerator IR may need to represent latency abstraction as
an elaboration-stage timing state between fully dynamic LI behavior and
concrete LS behavior.

Conceptually:

    runtime-dependent timing        -> LI
    elaboration-dependent timing    -> LA
    concrete compile-time timing    -> LS

The candidate idea is that LA regions remain represented inside mixed control
until generator elaboration provides sufficient facts, after which selected
LA regions refine to LS while genuinely LI regions remain dynamic.

This is a hypothesis to test, not a semantic result already established.

## 8. Rich-contract question

The V1.3 boundary currently exports scalar latency.

A stronger interface may need to preserve additional temporal information,
for example:

- latency;
- initiation interval;
- input availability windows;
- output availability windows;
- symbolic relationships between temporal parameters.

The research question is not simply whether such information exists in
Lilac. It does.

The question is whether retaining any of it inside a higher-level
mixed-control IR enables useful reasoning or optimization that the
"elaborate LA completely, then invoke Piezo" baseline cannot provide cleanly.

## 9. Claims currently safe to make

Safe:

- We built an exploratory compiler prototype connecting generator-resolved
  timing to higher-level mixed-control compilation.
- The prototype demonstrates modular component timing propagation and
  parent-level constraint reasoning after generator elaboration.
- Five generator configurations use one unchanged source and symbolic IR.
- V1.3 experimentally probes the boundary between LA generation and
  mixed-control accelerator compilation.
- The prototype motivates a stronger question about preserving LA temporal
  information deeper into the mixed-control IR.

Not safe:

- V1.3 establishes a novel abstraction.
- We invented latency-abstract interfaces.
- We invented modular timing interfaces.
- We invented hierarchical symbolic timing propagation.
- We invented mixed static/dynamic accelerator control.
- We invented static islands inside dynamic control.

## 10. Next decisive experiment

A future V1.4 should not merely propagate another concrete latency.

It must test a property that distinguishes:

    elaborate all LA first -> concrete Piezo

from:

    preserve LA inside mixed control -> resolve/refine later

A useful V1.4 result therefore needs at least one correctness, scheduling,
specialization, or optimization decision whose natural scope crosses the
LA/LI boundary while some LA information remains unresolved.

If no such property can be demonstrated cleanly, the stronger research
direction should be narrowed or abandoned.

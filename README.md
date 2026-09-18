# Latency-Abstract Accelerators

Exploratory compiler prototype studying the boundary between **latency-abstract (LA) generated hardware** and **mixed static/dynamic accelerator control**.

> **Status:** research prototype / work in progress.
>
> V1.3 is a proof-of-mechanism and is **not** presented as an established novelty result.

## Research question

Generated hardware introduces a timing regime between conventional latency-sensitive (LS) and latency-insensitive (LI) control:

- **LI:** timing is resolved only at runtime.
- **LA:** timing is unknown during composition but resolves during generator elaboration.
- **LS:** concrete timing is available for static scheduling.

The central question is:

> Should latency-abstract temporal information be fully resolved before entering a mixed-control accelerator IR, or should LA information remain represented long enough to support useful reasoning before refinement to concrete static timing?

This question is motivated by the boundary between **Lilac-style latency abstraction** and **Piezo/Calyx-style mixed static/dynamic control**.

## V1.3 prototype

The current prototype implements:

    latency-abstract source
            |
    generator elaboration
            |
    concrete generator timing
            |
    structural component timing inference
            |
    reusable component timing interfaces
            |
    parent-level timing constraints
            |
    Calyx lowering
            |
    Verilator

The parent timing stage consumes child timing interfaces rather than child implementation bodies or direct child generator facts.

The frozen implementation is available at Git tag `v1.3-freeze`.

## C1/C2 centerpiece

The canonical program contains:

    pair     = static par(A, B)
    tail     = static seq(A)
    pipeline = static seq(pair, tail)

    require T_total <= 8

No concrete generator latency appears in the source.

| Config | A | B | T_pair | T_tail | T_total | Result |
|---|---:|---:|---:|---:|---:|---|
| C1 | 2 | 5 | 5 | 2 | 7 | ACCEPT |
| C2 | 5 | 2 | 5 | 5 | 10 | REJECT |

C1 and C2 use the same source, symbolic IR, and latency multiset `{2,5}`. `T_pair` remains 5, but reversing which generated module receives which latency changes the reusable `tail` interface and therefore the parent-level timing decision.

## Experimental evidence

Across five generated timing configurations:

| Config | A | B | T_pair | T_tail | T_total | Result |
|---|---:|---:|---:|---:|---:|---|
| C1 | 2 | 5 | 5 | 2 | 7 | ACCEPT |
| C2 | 5 | 2 | 5 | 5 | 10 | REJECT |
| C3 | 3 | 3 | 3 | 3 | 6 | ACCEPT |
| C4 | 4 | 7 | 7 | 4 | 11 | REJECT |
| C5 | 8 | 3 | 8 | 8 | 16 | REJECT |

Across C1-C5:

- the source is identical;
- the symbolic IR is identical;
- the canonical source contains zero explicit timing bindings;
- generated RTL timing is independently checked;
- accepted configurations execute through Calyx/Verilator;
- C1 completes in 43 simulated cycles with the expected output;
- C3 completes in 39 simulated cycles with the expected output;
- the regression suite contains 131 passing tests.

## Strong baseline / kill test

A simpler architecture may already be sufficient:

    Lilac / LA subsystem
            |
    symbolic LA composition
            |
    generator elaboration
            |
    concrete timed component
            |
    Piezo / Calyx
            |
    mixed static/dynamic accelerator

If this elaborate-first architecture provides all useful correctness, modularity, scheduling, and optimization, then an additional cross-layer abstraction is unnecessary.

The project treats this as a serious baseline rather than assuming a new abstraction is required.

## What V1.3 does not claim

V1.3 does **not** claim invention of:

- latency abstraction;
- modular temporal interfaces;
- hierarchical symbolic timing propagation;
- mixed static/dynamic accelerator control;
- static islands inside dynamically controlled hardware.

The current artifact instead probes the compiler boundary between these existing capabilities.

## Stronger direction

The next question is whether unresolved LA temporal contracts should survive inside mixed control and refine to LS only after generator elaboration.

A convincing next experiment must demonstrate a correctness, scheduling, specialization, or optimization property whose scope crosses LA and LI while some LA timing remains unresolved.

Potentially relevant temporal information includes:

- latency;
- initiation interval;
- input/output availability windows;
- symbolic temporal relationships.

Merely transporting additional metadata would not be sufficient.

## Scientific-computing motivation

An eventual target is iterative scientific computing, including electronic-structure / DFT-style workloads.

One possible mapping is:

    runtime convergence / adaptivity       -> LI
    generated numerical kernel             -> LA
    generator-resolved kernel timing       -> LS

DFT/scientific computing is intended as a future workload and evaluation setting, not the claimed compiler contribution.

## Documentation

- `docs/rachit_one_page.md` — compact technical note and open question.
- `docs/research_audit.md` — detailed prior-work and research audit.
- `docs/reference_ledger.md` — claim-to-source ledger.
- `docs/v1_3_component_timing_interfaces.md` — V1.3 design.
- `results/v1_3_findings.md` — experimental findings.
- `results/v1_3_configuration_sweep.md` — C1-C5 sweep.

## Repository layout

    lair/        compiler IR, parsing, timing resolution, and Calyx backend
    generators/  toy physical generator
    examples/    canonical source programs and generated Calyx
    tests/       regression, boundary, invariance, and experiment drivers
    results/     archived measurements and reproducibility evidence
    docs/        design notes, research audit, and literature ledger
    baselines/   comparison implementations and shared RTL

## Reproducibility

The immutable V1.3 implementation is available at tag `v1.3-freeze`.

The repository contains:

- the C1-C5 configuration sweep;
- same-source/same-symbolic-IR checks;
- physical generated-RTL timing validation;
- regression tests;
- a deterministic V1.3 evidence manifest.

Some full physical runs require a working Calyx/FUD2/Verilator environment.

## Current status

The prototype is being used to answer a research question, not to claim that the answer is already known.

The decisive test for a future version is whether preserving LA information inside mixed control enables something that cannot be cleanly decomposed into:

    Lilac first -> resolve timing -> Piezo/Calyx second

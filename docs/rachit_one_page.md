# Latency Abstraction at the Mixed-Control Accelerator Boundary

**Working research note — Arnab Das**

## Question

Generated hardware introduces a timing regime distinct from both ordinary
latency-sensitive (LS) and latency-insensitive (LI) control: timing may be
unknown during accelerator composition but become concrete when an external
generator is elaborated.

I am exploring whether this latency-abstract (LA) timing should be fully
resolved before entering a mixed static/dynamic accelerator IR, or whether LA
temporal information should remain first-class long enough to support useful
reasoning before refinement to concrete static timing.

    LI: timing resolved only at runtime
    LA: timing resolved during generator elaboration
    LS: concrete timing available for static scheduling

## Prior-work boundary

Lilac already provides latency-abstract generator interfaces, output timing
parameters, symbolic temporal composition, and hierarchical timing
propagation.

Piezo/Calyx already provide mixed static/dynamic accelerator control and can
exploit fixed-latency regions once concrete timing is available.

I therefore do not treat latency abstraction, symbolic timing propagation,
modular timing interfaces, or mixed static/dynamic control as contributions.
The question is the staging boundary between these capabilities.

## V1.3 prototype

To probe this boundary, I built a small compiler prototype in which generator
timing is absent from the source program:

    LA source
        -> generator elaboration
        -> concrete generator timing
        -> structural component timing inference
        -> reusable timing interfaces
        -> parent-level constraints
        -> Calyx
        -> Verilator

The parent timing stage receives child timing interfaces rather than child
implementation bodies or direct generator timing facts.

V1.3 is a proof-of-mechanism for this boundary, not a novelty claim.

## C1/C2 centerpiece

The canonical source contains:

    pair     = static par(A, B)
    tail     = static seq(A)
    pipeline = static seq(pair, tail)

    require T_total <= 8

No concrete generator latency appears in the source.

| Config | A | B | T_pair | T_tail | T_total | Result |
|---|---:|---:|---:|---:|---:|---|
| C1 | 2 | 5 | 5 | 2 | 7 | ACCEPT |
| C2 | 5 | 2 | 5 | 5 | 10 | REJECT |

C1 and C2 use the same source, symbolic IR, and latency multiset `{2,5}`.
`T_pair` remains 5, but reversing which generated module receives which
latency changes the reusable `tail` interface and therefore the parent-level
constraint result.

## Experimental sweep

| Config | A | B | T_pair | T_tail | T_total | Compiler |
|---|---:|---:|---:|---:|---:|---|
| C1 | 2 | 5 | 5 | 2 | 7 | ACCEPT |
| C2 | 5 | 2 | 5 | 5 | 10 | REJECT |
| C3 | 3 | 3 | 3 | 3 | 6 | ACCEPT |
| C4 | 4 | 7 | 7 | 4 | 11 | REJECT |
| C5 | 8 | 3 | 8 | 8 | 16 | REJECT |

Across C1-C5, the source and symbolic IR are identical, the canonical source
contains zero explicit timing bindings, and generated RTL timing is
independently checked.

Accepted configurations execute through Calyx/Verilator: C1 completes in
43 simulated cycles and C3 in 39, both with the expected output. The current
regression suite contains 131 passing tests.

The reproducible implementation is frozen at `v1.3-freeze`.

## Strong baseline

A simpler architecture may already be sufficient:

    Lilac / LA subsystem
        -> symbolic LA composition
        -> generator elaboration
        -> concrete timed component
        -> Piezo / Calyx
        -> mixed static/dynamic accelerator

Lilac itself discusses composing LA modules into larger LA "islands" and
wrapping them with latency-insensitive interfaces.

If this elaborate-first architecture provides all useful correctness,
modularity, scheduling, and optimization, then an additional cross-layer
abstraction is unnecessary.

## Stronger question

The prototype therefore raises a narrower question:

**Is there value in allowing unresolved LA temporal contracts to survive into
a mixed-control accelerator IR and refine to LS only after generator
elaboration?**

V1.3 currently carries scalar latency. A stronger boundary might preserve
richer information such as initiation interval, input/output availability
windows, or symbolic temporal relationships.

A convincing next experiment must demonstrate a correctness, scheduling,
specialization, or optimization property whose natural scope crosses the
LA/LI boundary while some LA information remains unresolved. Otherwise, the
elaborate-first baseline should win.

## Scientific-computing motivation

One eventual workload is iterative scientific computing, including
electronic-structure / DFT-style computation: runtime convergence or
adaptivity provides LI behavior, while generated numerical kernels can be LA
during elaboration and LS once their timing resolves.

I view this as a future workload and evaluation setting, not the compiler
contribution itself.

## Feedback question

**Do you view the LA-to-mixed-control boundary as substantively open, or is
the natural architecture simply to elaborate the entire LA subsystem first
and then hand a concretely timed module to Piezo/Calyx?**

If preserving LA information deeper into the mixed-control IR is useful, I
would also be interested in which temporal facts seem important at that
boundary.

## Artifact

Repository:

https://github.com/arnabdas490/latency-abstract-accelerators

Frozen prototype:

`v1.3-freeze`

The repository also contains the research audit, claim/reference ledger,
configuration sweep, reproducibility checks, and archived V1.3 evidence.

# Rachit Nigam Outreach Package — Working Outline

Status: internal working document
Target outreach date: 2026-09-22

## Goal

Send a compact technical package demonstrating that:

1. the Calyx -> Filament -> Piezo -> Lilac research line was studied;
2. a concrete candidate seam was identified;
3. a working compiler prototype was built to probe it;
4. the prototype has reproducible evidence;
5. prior work is being treated as an adversary, not ignored;
6. the outreach asks a precise technical question rather than asking the
   recipient to invent the project.

## One-sentence project statement

I am exploring how latency-abstract timing from generated hardware should
cross into a higher-level mixed static/dynamic accelerator IR, especially
whether LA timing should remain first-class long enough to support reasoning
before generator elaboration resolves it to concrete static timing.

## Prior-work boundary

Lilac already provides:

- latency-abstract generated interfaces;
- generator output timing parameters;
- symbolic temporal composition;
- bottom-up hierarchical timing propagation.

Piezo already provides:

- unified static/dynamic accelerator control;
- static refinement of dynamic behavior;
- inference/promotion of fixed-latency regions.

The candidate question lies at the staging boundary between them.

## Strong baseline

The project must compare against:

    Lilac
      -> compose/check LA subsystem
      -> execute generators
      -> obtain concrete timing
      -> expose ordinary timed component
      -> Piezo/Calyx
      -> mixed static/dynamic accelerator

This may already be the correct solution.

## V1.3 prototype

Frozen artifact:

    tag: v1.3-freeze

V1.3 pipeline:

    latency-abstract source
        ->
    generator elaboration
        ->
    concrete generator timing
        ->
    structural timing inference
        ->
    reusable component timing interfaces
        ->
    parent-level constraint reasoning
        ->
    resolved Calyx
        ->
    Verilator

Important property:

The parent timing stage does not require the implementation bodies of child
components or direct child generator timing facts.

## C1/C2 centerpiece

Canonical source contains:

    pair:
        static par(A, B)

    tail:
        static seq(A)

    pipeline:
        static seq(pair, tail)

    require T_total <= 8

C1:

    A=2
    B=5

    T_pair=5
    T_tail=2
    T_total=7

    ACCEPT

C2:

    A=5
    B=2

    T_pair=5
    T_tail=5
    T_total=10

    REJECT

Key point:

- same source;
- same symbolic IR;
- same latency multiset {2,5};
- same pair timing;
- different reusable tail interface;
- different parent-level decision.

## C1-C5 summary

| Config | A | B | T_pair | T_tail | T_total | Result |
|---|---:|---:|---:|---:|---:|---|
| C1 | 2 | 5 | 5 | 2 | 7 | ACCEPT |
| C2 | 5 | 2 | 5 | 5 | 10 | REJECT |
| C3 | 3 | 3 | 3 | 3 | 6 | ACCEPT |
| C4 | 4 | 7 | 7 | 4 | 11 | REJECT |
| C5 | 8 | 3 | 8 | 8 | 16 | REJECT |

Physical evidence:

- C1: accepted, 43 simulated cycles, correct output.
- C3: accepted, 39 simulated cycles, correct output.
- C2/C4/C5: rejected after timing resolution; generated RTL timing independently
  validated.

Reproducibility evidence:

- source SHA identical across C1-C5;
- symbolic IR SHA identical across C1-C5;
- zero explicit timing bindings in canonical source;
- 131/131 unit tests;
- complete sweep reproducible from one command;
- evidence archive deterministic;
- full rerun produced zero tracked Git differences.

## What V1.3 means

V1.3 is not presented as the novel abstraction.

It is a proof-of-mechanism demonstrating that a bridge from generated timing
to mixed-control compilation can be implemented and experimentally exercised.

## Stronger question

Should latency abstraction remain represented inside the mixed-control IR
rather than being completely eliminated before that IR receives the generated
component?

Candidate staged picture:

    LI:
        timing resolved only at runtime

    LA:
        timing unresolved during design but resolved during elaboration

    LS:
        concrete timing available to static scheduling

Possible future hypothesis:

An LA region may act as an elaboration-time refinement state that becomes LS
after generator resolution while genuinely LI regions remain dynamic.

This is currently a hypothesis, not a formal result.

## Rich-contract question

The V1.3 bridge carries scalar latency.

A stronger boundary may need to preserve:

- latency;
- initiation interval;
- input availability;
- output availability;
- symbolic relationships between timing parameters.

The experiment must show why preserving any of these inside mixed control is
useful; merely transporting more metadata is insufficient.

## Precise question for Rachit

Primary:

Do you think the LA-to-mixed-control boundary is substantively open, or is the
natural architecture simply to elaborate the entire LA subsystem first and
then pass a concretely timed module into Piezo/Calyx?

Secondary:

If preserving LA information deeper into the mixed-control IR is useful, what
temporal facts would be important at that boundary: scalar latency only, or
richer information such as initiation interval and availability windows?

## Non-claims

Do not claim:

- novelty established by the current prototype;
- invention of latency abstraction;
- invention of timing interfaces;
- invention of symbolic timing propagation;
- invention of mixed static/dynamic control;
- invention of static islands in dynamic hardware;
- general performance benefit;
- representative accelerator benchmarking;
- physical module-boundary preservation in V1.3.

## Package components

Target outreach package:

1. concise email;
2. one-page technical summary;
3. one architecture figure;
4. C1/C2 centerpiece;
5. C1-C5 results table;
6. GitHub repository;
7. `v1.3-freeze` tag;
8. reference/claim ledger.

## Email tone

The email should communicate:

- genuine understanding of the research lineage;
- a concrete artifact already exists;
- uncertainty is stated explicitly;
- feedback is requested on a precise technical boundary;
- electronic structure / DFT is motivation for later evaluation, not the
  claimed contribution.

Do not lead with:

- DFT;
- benchmark speedups;
- broad novelty claims;
- a request for Rachit to design the project.

## Next package tasks

1. Review this outline against primary sources.
2. Freeze exact wording of the one-page technical note.
3. Produce clean architecture and C1/C2 figures.
4. Polish README reproduction path.
5. Draft the first full email.
6. Final overclaim audit.
7. Send by 2026-09-22.

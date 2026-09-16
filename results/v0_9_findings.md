# V0.9 Configuration / Modularity Experiment

## Question

Can one unchanged latency-abstract composition survive generator timing
changes, recover the manually specialized static schedule after timing
resolution, and reject configurations that violate a symbolic timing
constraint?

## Configurations

| Config | L_A | L_B | T=max(L_A,L_B) | LA status |
|---|---:|---:|---:|---|
| C1 | 2 | 5 | 5 | accepted |
| C2 | 5 | 2 | 5 | accepted |
| C3 | 3 | 3 | 3 | accepted |
| C4 | 4 | 7 | 7 | rejected |
| C5 | 8 | 3 | 8 | rejected |

The current synthetic contract requires T <= 6.

## Physical RTL validation

For every configuration, generated RTL was independently simulated and
the measured go-to-done latency matched the contract values for both
kernels.

The latency verifier was corrected during development to wait for both
kernel completions instead of assuming kernel B was always the slower
path. This was exposed by C2, where L_A > L_B.

## Runtime results at N=4

| Config | Opaque LI | Manual static | LA-resolved |
|---|---:|---:|---:|
| C1 (2,5) | 50 | 35 | 35 |
| C2 (5,2) | 50 | 35 | 35 |
| C3 (3,3) | 42 | 27 | 27 |
| C4 (4,7) | 58 | n/a | rejected |
| C5 (8,3) | 62 | n/a | rejected |

All executed designs were functionally correct.

For every accepted configuration, the LA-resolved implementation matched
the manually specialized static implementation in measured cycles.

## Modularity evidence

The LA frontend source was unchanged across the sweep.

Three accepted configurations required three concrete manual-static
source variants carrying configuration-specific timing literals, while
the LA experiment used one unchanged composition source whose timing was
resolved from the contracts.

This is evidence for configuration modularity in the current prototype,
not yet proof that the abstraction is superior to all scripting
approaches.

## Correctness / rejection evidence

C4 and C5 generated physically valid fixed-latency RTL and executed under
the opaque latency-insensitive composition. The LA elaboration rejected
both before emitting LA hardware because the current synthetic
parallel-deadline constraint T <= 6 was violated.

This distinguishes physical generator validity from higher-level timing
contract validity.

## Caveats

- The T <= 6 deadline is synthetic and should not be presented as a real
  hardware constraint.
- The current implementation remains an external Python elaboration
  prototype.
- The current static parallel composition relies on Calyx/Piezo static
  timing semantics rather than explicitly inserting D_A / D_B delay
  elements.
- These experiments establish mechanism, modularity evidence, and
  rejection behavior; they do not establish novelty.
- The next milestone must make latency abstraction explicit in a program
  representation / compiler pass rather than leaving the semantics
  primarily in orchestration scripts.

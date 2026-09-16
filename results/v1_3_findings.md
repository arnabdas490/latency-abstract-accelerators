# V1.3 Findings — Reusable Component Timing Interfaces

## Research question

Can generator-resolved timing propagate across reusable module boundaries without requiring a parent component to know the child's internal generator or control structure?

## Mechanism demonstrated

The canonical V1.3 source defines reusable `pair`, `tail`, and `pipeline` components. Generator latencies are absent from source. Each component exports one compiler-derived timing interface (`T_pair`, `T_tail`, or `T_total`).

The resolver evaluates child components first, exports only their component timing interfaces, and resolves the parent from those interfaces. Parent timing resolution therefore does not require child generator facts or child bodies.

After timing resolution and constraint checking, the current toy Calyx backend is permitted to expand already-resolved component bodies into the established A/B physical shell. V1.3 therefore demonstrates modularity at the compiler-IR timing boundary; it does not claim preservation of physical module boundaries in emitted RTL.

## Canonical-program invariants

- Source: `examples/v1_3_components.lair`
- Source SHA256: `704d1d2795fdf5e4bd25add540b4d5f42d0a5ca5eb9fab91fb9dbdc31df6e723`
- Symbolic IR SHA256: `ec073bfe3e1612fdddae4fcc02892227648ace6fa7424dbe48f0cb891d53c942`
- Explicit timing bindings in source: `0`
- The same source and same symbolic IR are used for C1-C5.

## Configuration sweep

| Config | A | B | T_pair | T_tail | T_total | Compiler | Measured RTL | Hardware cycles | Memory |
|---|---:|---:|---:|---:|---:|---|---|---:|---|
| C1 | 2 | 5 | 5 | 2 | 7 | ACCEPT | 2/5 | 43 | [10, 4, 23, 0] |
| C2 | 5 | 2 | 5 | 5 | 10 | REJECT | 5/2 | — | — |
| C3 | 3 | 3 | 3 | 3 | 6 | ACCEPT | 3/3 | 39 | [10, 4, 23, 0] |
| C4 | 4 | 7 | 7 | 4 | 11 | REJECT | 4/7 | — | — |
| C5 | 8 | 3 | 8 | 8 | 16 | REJECT | 8/3 | — | — |

## C1/C2 reversal centerpiece

C1 and C2 use the same source and symbolic IR and have the same multiset of generator latencies `{2, 5}`.

- C1 assigns A=2, B=5. `T_pair=5`, `T_tail=2`, `T_total=7`; the program is accepted.
- C2 reverses the assignment to A=5, B=2. `T_pair` remains 5, but `T_tail` becomes 5; `T_total` becomes 10, violating the `T_total <= 8` constraint.

The unchanged `pair` latency alongside the changed `tail` latency isolates the effect of reusable component structure: the parent observes exported timing interfaces rather than reconstructing child implementation timing.

## Physical validation

Independent Verilator checks validated the advertised go-to-done latency and functional behavior of both generated kernels for all five configurations.

Accepted C1 and C3 were additionally lowered through Calyx and simulated end-to-end:

- C1: 43 cycles, memory [10, 4, 23, 0].
- C3: 39 cycles, memory [10, 4, 23, 0].

Rejected C2, C4, and C5 retain generated physical RTL for independent latency validation but emit no Calyx program after the timing constraint fails.

## What V1.3 establishes

V1.3 provides a working compiler prototype in which generator timing becomes known after source composition, is converted into timing facts, is inferred through static control, crosses reusable component boundaries through explicit timing interfaces, influences parent timing and compile-time constraints, and reaches executable Calyx for accepted configurations.

This goes beyond the original trivial `generator -> read latency -> print static<L>` mechanism: timing now participates in a structured compiler IR and composes across reusable module boundaries.

## Limits and non-claims

- The generators and deadline constraint are synthetic.
- The experiment is a mechanism/modularity prototype, not a representative accelerator benchmark.
- The measured cycle counts do not establish a general performance advantage.
- The current backend expands resolved reusable components into a toy A/B shell; physical RTL module boundaries are not a V1.3 claim.
- V1.3 does not by itself establish novelty relative to Calyx, Piezo, Filament, Lilac, or other prior systems.
- Broader generator integrations and realistic numerical kernels remain future validation work.

## Reproducibility

The full C1-C5 experiment is regenerated with:

```bash
python tests/run_v1_3_configuration_sweep.py
```

The source/IR invariance proof is regenerated with:

```bash
python tests/check_v1_3_same_source_ir.py
```

The machine-readable evidence manifest covers 41 tracked implementation, test, source, design, and result artifacts.

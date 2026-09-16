# V1.1 configuration sweep findings

## Experiment

One unchanged latency-abstract source program:

`examples/v1_0_pair.lair`

was evaluated under five toy-generator configurations.

Source SHA256:

`17b5a29f9c244af97eb3a41409400b582ab0b2ae9bdb14f4060933527a397161`

Canonical symbolic-IR SHA256:

`0f592c4575286d5b0db6653058d9c11b0c5417ecd08dc91e53a5ca4d405a6459`

## Results

| Config | L_A | L_B | T | Compiler | Physical timing | Cycles |
|---|---:|---:|---:|---|---|---:|
| C1 | 2 | 5 | 5 | accepted | 2, 5 | 35 |
| C2 | 5 | 2 | 5 | accepted | 5, 2 | 35 |
| C3 | 3 | 3 | 3 | accepted | 3, 3 | 27 |
| C4 | 4 | 7 | 7 | rejected | 4, 7 | — |
| C5 | 8 | 3 | 8 | rejected | 8, 3 | — |

## Observations

- The LAIR source and canonical symbolic IR remained unchanged across all five generator configurations.
- Generator-produced timing facts were converted automatically into the compiler `TimingEnvironment`.
- Independent Verilator measurements confirmed the advertised physical go-to-done latency of both generated kernels for every configuration.
- C1, C2, and C3 were accepted and produced the expected hardware behavior.
- C4 and C5 generated physically valid RTL but were rejected by the symbolic `parallel_deadline` constraint before Calyx hardware emission.
- Different configurations produced different physical RTL while preserving the same latency-abstract source and symbolic IR.
- The canonical C1 `(2,5)` generated state was restored after the sweep.

## Scope and caveats

This is a toy-generator mechanism and modularity experiment. The `T <= 6` deadline is synthetic, and the observed cycle counts do not establish a general performance advantage. The experiment demonstrates automatic generator-timing propagation, timing-aware resolution, and compile-time rejection behavior; it does not by itself establish novelty or generality beyond this prototype.

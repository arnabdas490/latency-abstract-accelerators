# V1.2 hierarchical timing sweep findings

## Experiment

One unchanged latency-abstract source program:

`examples/v1_2_hierarchical.lair`

was evaluated under five toy-generator configurations.

The source contains no explicit `let` timing bindings. `T_pair` and `T_total` are named by control regions and their values are inferred from static-control composition.

Source SHA256:

`6cbdccfc42fb8cc717043c11a00e66eb25944c5d7e66579760bd05f511b912d1`

Canonical symbolic-IR SHA256:

`6ba8bf00a8fb214a94d668182ed1f744dca89441bd62647183cfb73a7b9cb0e8`

## Results

| Config | L_A | L_B | T_pair | T_total | Compiler | Physical timing | Cycles |
|---|---:|---:|---:|---:|---|---|---:|
| C1 | 2 | 5 | 5 | 7 | accepted | 2, 5 | 43 |
| C2 | 5 | 2 | 5 | 10 | rejected | 5, 2 | — |
| C3 | 3 | 3 | 3 | 6 | accepted | 3, 3 | 39 |
| C4 | 4 | 7 | 7 | 11 | rejected | 4, 7 | — |
| C5 | 8 | 3 | 8 | 16 | rejected | 8, 3 | — |

## Structural reversal check

C1 `(L_A,L_B)=(2,5)` and C2 `(5,2)` contain the same latency multiset `{2,5}` and both infer `T_pair = 5`.

Because `A` is invoked again after the parallel region, the enclosing structural timing differs: C1 infers `T_total = 7`, while C2 infers `T_total = 10`.

Under the unchanged `T_total <= 8` source constraint, C1 is accepted and C2 is rejected.

## Mechanically checked properties

- **PASS** — One source hash across all configurations
- **PASS** — One symbolic IR hash across all configurations
- **PASS** — Zero explicit timing bindings in the V1.2 source
- **PASS** — Source remained unchanged
- **PASS** — Symbolic IR remained unchanged
- **PASS** — All generated RTL latencies were physically validated
- **PASS** — All structural timings matched expected values
- **PASS** — All expected-valid configurations were accepted
- **PASS** — All expected-invalid configurations were rejected
- **PASS** — All rejected configurations emitted no Calyx
- **PASS** — All rejected configurations failed total_deadline
- **PASS** — All generator configurations produced distinct RTL artifacts
- **PASS** — All accepted hardware produced correct output
- **PASS** — All accepted cycle counts matched measured targets
- **PASS** — C1/C2 structural reversal property holds

## Scope and caveats

This remains a toy-generator experiment with a synthetic `T_total <= 8` deadline and an A/B-specific external primitive shell. The result does not establish novelty or a general performance advantage.

V1.2 strengthens the abstraction experiment by moving parallel/sequential timing composition into first-class IR semantics: the source names region timing results, while the compiler derives their concrete values from generator timing and control structure.

The C1/C2 contrast demonstrates a case where the same leaf-latency multiset and same inner-parallel latency produce different higher-level timing and compilation outcomes because of structural composition.

This is evidence against the narrow `parse latency -> print static<L>` implementation, but it does not by itself prove that a general-purpose compiler IR is superior to every possible custom script.

# V1.3 component timing-interface sweep

One unchanged latency-abstract source and symbolic IR were evaluated under five generator configurations.

- Source SHA256: `704d1d2795fdf5e4bd25add540b4d5f42d0a5ca5eb9fab91fb9dbdc31df6e723`
- Symbolic IR SHA256: `ec073bfe3e1612fdddae4fcc02892227648ace6fa7424dbe48f0cb891d53c942`
- Explicit timing bindings in source: `0`

| Config | A | B | Pair | Tail | Total | Compiler | Measured RTL | Hardware cycles |
|---|---:|---:|---:|---:|---:|---|---|---:|
| C1 | 2 | 5 | 5 | 2 | 7 | ACCEPT | 2/5 | 43 |
| C2 | 5 | 2 | 5 | 5 | 10 | REJECT | 5/2 | — |
| C3 | 3 | 3 | 3 | 3 | 6 | ACCEPT | 3/3 | 39 |
| C4 | 4 | 7 | 7 | 4 | 11 | REJECT | 4/7 | — |
| C5 | 8 | 3 | 8 | 8 | 16 | REJECT | 8/3 | — |

## Validation summary

- Same source for C1-C5: `True`
- Same symbolic IR for C1-C5: `True`
- Matches frozen manifest: `True`
- Expected compiler decisions: `True`
- All physical generator latencies validated: `True`
- All generated kernels functionally validated: `True`
- Rejected configurations emitted no Calyx: `True`
- Accepted hardware returned correct memory: `True`
- Accepted hardware cycle counts matched targets: `True`

## Interpretation

The experiment demonstrates timing propagation across reusable component interfaces after generator timing becomes known. The latency-abstract source and symbolic IR are unchanged across configurations. This remains a toy-generator mechanism experiment and does not by itself establish generality, performance advantage, or novelty.

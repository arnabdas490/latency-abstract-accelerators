# V0.8 Shared-RTL Reproduction Environment

Reproduced canonical V0.8 shared-RTL experiments on the recovered loaner environment.

## Platform

```text
Darwin LOAN-DPQ22WRX0J 23.6.0 Darwin Kernel Version 23.6.0: Tue Jul 21 22:00:04 PDT 2026; root:xnu-10063.141.1.713.39~1/RELEASE_ARM64_T8112 arm64
ProductName:		macOS
ProductVersion:		14.8.9
BuildVersion:		23J631
```

## Architecture

```text
arm64
```

## Calyx

```text
d6bcdc8707fe2f024a7b18a86523bda6f770186a
Calyx compiler version 0.7.1
Library location: /Users/Patron/.calyx
```

## Rust

```text
rustc 1.90.0 (1159e78c4 2025-09-14)
cargo 1.90.0 (840b83a10 2025-07-30)
```

## Simulation toolchain

```text
Verilator 5.022 2024-02-24 rev conda-forge build 1
1.13.2
jq-1.8.2
cmake version 4.4.3
Usage: fud2 [-o <output...>] [--from <from...>] [--to <to...>] [-m <mode>] [--dir <dir>] [--keep] [-s <set...>] [--through <through...>] [-v] [-q] [--force-rebuild] [--log <log>] [--planner <planner>] [--csv <csv>] [<input...>] [<command>] [<args>]
```

## Python

```text
Python 3.13.15
/Users/Patron/conda/envs/calyx/bin/python
```

## Canonical shared RTL

```text
79599a00b41f3fa00f494268cc15f06635e8753275e16aab692b73fbc0b31776  baselines/v0_8_fixed_li_kernels.sv
```

## Reproduced canonical point

```text
L_A = 2
L_B = 5
N   = 4
opaque LI      = 50 cycles
manual static  = 35 cycles
LA-resolved    = 35 cycles
final memory   = [10, 4, 23, 0]
```

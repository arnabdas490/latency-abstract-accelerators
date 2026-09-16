# V1.0 Latency-Abstract IR

## Goal

Replace ad-hoc latency substitution in orchestration scripts with an
explicit intermediate representation in which generator-dependent timing
can remain symbolic during composition, be resolved during elaboration,
checked against timing constraints, and only then lowered to ordinary
Calyx/Piezo static constructs.

## Non-goal

V1.0 is not a new HDL, a complete Calyx extension, or a DFT accelerator.
It is the smallest compiler prototype needed to test whether latency
abstraction provides semantics beyond "read a number and print
static<L>".

## Compiler pipeline

    LA source
       |
       v
    Parser
       |
       v
    Symbolic IR
       |
       v
    Generator elaboration
       |
       v
    Timing environment
       |
       v
    Resolution + constraint checking
       |
       +---- reject
       |
       v
    Resolved IR
       |
       v
    Calyx/Piezo lowering

## Core IR objects

### Latency variable

Represents timing that is unknown while the accelerator composition is
authored.

Example:

    L_A

### Constant

Example:

    6

### Timing expressions

V1.0 initially supports:

    max(expr, expr)

and integer constants / latency variables.

Example:

    T = max(L_A, L_B)

### Constraints

V1.0 initially supports:

    expr >= expr
    expr <= expr
    expr == expr

Example:

    L_A >= 1
    L_B >= 1
    max(L_A, L_B) <= 6

### Generator declaration

Associates a generated component with an output timing variable.

Example:

    generator A = toy_generator(kernel_a)
        latency -> L_A

### Static composition

A composition may refer to components whose latency variables are still
unresolved in the symbolic IR.

Example:

    static par {
        invoke A(x)
        invoke B(x)
    }

The symbolic composition is not lowered to concrete Calyx static timing
until all required timing variables have been resolved.

## Timing environment

Generator elaboration produces a mapping such as:

    {
        L_A: 5,
        L_B: 2
    }

The timing environment is the only mechanism by which concrete
generator timing enters the resolver.

## Resolution

Resolution substitutes timing variables into timing expressions.

Before:

    T = max(L_A, L_B)

Environment:

    L_A = 5
    L_B = 2

After:

    T = 5

The resolver then evaluates constraints.

## Rejection

For:

    L_A = 4
    L_B = 7

the expression:

    T = max(L_A, L_B)

resolves to:

    T = 7

and:

    T <= 6

fails.

The compiler must reject the program before emitting the resolved Calyx
composition.

## Lowering boundary

The Calyx/Piezo backend consumes only resolved IR.

It must not inspect generator contract JSON files or independently infer
latencies.

For an accepted environment:

    L_A = 2
    L_B = 5

the backend may lower generator interfaces to concrete timing contracts
such as:

    @interval(2)
    @interval(5)

and emit static composition using those resolved values.

## V1.0 invariants

1. The source composition contains no concrete values for L_A or L_B.
2. Generator latency enters through a timing environment.
3. The symbolic IR exists before generator timing is known.
4. Constraints are represented as IR objects, not hard-coded Python
   conditionals tied to particular kernels.
5. The backend operates only on resolved IR.
6. Invalid timing environments produce no resolved Calyx program.
7. One unchanged source program must handle at least the V0.9
   configurations:
      (2,5)
      (5,2)
      (3,3)
      (4,7)
      (8,3)

## Initial implementation modules

    lair/
        ast.py
        parser.py
        environment.py
        resolver.py
        calyx_backend.py

    examples/
        v1_0_pair.lair

    tests/
        test_v1_0_ir.py
        run_v1_0_configuration_sweep.py

## Required V1.0 evidence

For each V0.9 configuration:

1. Parse the same LA source.
2. Produce the same symbolic IR structure.
3. Generate / obtain concrete kernel timing.
4. Construct a timing environment.
5. Resolve timing expressions.
6. Check constraints.
7. Reject invalid configurations before Calyx emission.
8. Lower accepted configurations to concrete Calyx.
9. Verify generated RTL latency.
10. Compare accepted implementations against the existing manual-static
    oracle.

## Kill test

If the resulting IR, resolver, and checks provide no meaningful semantic
boundary beyond direct string substitution, the project must be
reconsidered rather than expanded with more benchmarks.

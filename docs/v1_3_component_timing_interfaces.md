# V1.3 — Compositional Timing Interfaces Across Component Boundaries

## 1. Research question

Can a latency-aware accelerator IR compose timing across reusable component
boundaries such that a parent component reasons only about a child's exported
timing interface, without inspecting the child's internal generators or
control structure?

V1.2 established compositional timing inference within one hierarchical
control tree:

- invoke -> component latency
- static par -> max(child latencies)
- static seq -> sum(child latencies)

V1.3 moves that timing composition across an explicit module/component
abstraction boundary.

The key question is no longer merely:

    Can control structure infer timing?

It is:

    Can timing itself become part of a reusable component interface?

---

## 2. Why V1.3 exists

V1.2 substantially weakens the narrow objection:

    "Just parse generator latency and print static<L>."

However, a custom script could still recursively traverse the complete control
tree and compute max/sum expressions.

A stronger abstraction should permit separately defined components to expose a
timing contract while hiding their internal timing derivation from parents.

The parent should consume only:

    component name
    ports / arguments
    resolved timing interface

It should not need:

    child generator identities
    child control structure
    child timing equations
    child implementation details

If the parent must inspect those details, V1.3 has failed its purpose.

---

## 3. Canonical V1.3 experiment

The canonical program contains three user components:

    pair
    tail
    pipeline

`pair` internally invokes generators A and B in parallel.

`tail` internally invokes generator A.

`pipeline` invokes only `pair` and `tail` sequentially.

The parent `pipeline` therefore contains no direct generator invocation.

Conceptually:

    pipeline
    |
    +-- pair
    |   |
    |   +-- A
    |   +-- B
    |
    +-- tail
        |
        +-- A

Timing semantics:

    T_pair = max(L_A, L_B)
    T_tail = L_A
    T_total = T_pair + T_tail

These equations are semantic consequences of the component bodies.

They must NOT be written manually in the LAIR source.

---

## 4. Proposed LAIR syntax

Canonical source:

    generator A = toy_generator(kernel_a) latency -> L_A
    generator B = toy_generator(kernel_b) latency -> L_B

    require positive_latency_a: L_A >= 1
    require positive_latency_b: L_B >= 1
    require total_deadline: T_total <= 8

    component pair(x) latency -> T_pair {
        static par {
            invoke A(x)
            invoke B(x)
        }
    }

    component tail(x) latency -> T_tail {
        static seq {
            invoke A(x)
        }
    }

    component pipeline(x) latency -> T_total {
        static seq {
            invoke pair(x)
            invoke tail(x)
        }
    }

    entry pipeline

Important:

- There are zero explicit `let` timing bindings.
- `T_pair`, `T_tail`, and `T_total` name exported component timing interfaces.
- Their concrete values are inferred from component control semantics.
- `pipeline` refers only to `pair` and `tail`, not A or B.

---

## 5. Abstraction boundary

Each resolved component exports a timing interface:

    ComponentTimingInterface(
        component=<name>,
        latency=<resolved integer>
    )

For example under C1:

    pair -> 5
    tail -> 2

The parent resolver receives:

    pair -> 5
    tail -> 2

It must NOT receive or traverse:

    pair.body
    tail.body
    A/B references inside pair
    A reference inside tail

The parent therefore computes:

    pipeline = seq(pair, tail)
             = 5 + 2
             = 7

from interfaces alone.

---

## 6. Symbolic IR additions

Introduce a reusable component declaration.

Conceptually:

    ComponentDecl
        name: str
        args: tuple[str, ...]
        latency_var: TimingVar
        body: StaticPar | StaticSeq

`SymbolicProgram` becomes conceptually:

    SymbolicProgram
        generators
        components
        constraints
        entry

V1.0/V1.1/V1.2 compatibility must be preserved.

The implementation may internally normalize the historical single-component
representation, but historical source programs and canonical V1.0 hashes must
remain unchanged.

---

## 7. Resolved IR additions

Introduce:

    ResolvedComponent
        name
        args
        latency
        body

and a deliberately smaller public timing summary:

    ComponentTimingInterface
        component
        latency

The distinction matters.

A resolved child may contain its body for lowering/debugging, but a parent
timing resolver must depend only on `ComponentTimingInterface`.

---

## 8. Resolution algorithm

### 8.1 Leaf timing

Generator elaboration remains unchanged:

    generator declaration
        ->
    physical RTL + GeneratorResult
        ->
    TimingEnvironment

Example:

    L_A = 2
    L_B = 5

### 8.2 Component dependency graph

Build a directed dependency graph among user components.

For the canonical program:

    pair     -> no user-component dependencies
    tail     -> no user-component dependencies
    pipeline -> pair, tail

Generator invocations are leaves and do not create component-graph edges.

### 8.3 Restriction

V1.3 supports an acyclic component graph only.

Recursive component invocation is rejected.

This is deliberate.

Recursive timing semantics are outside V1.3 scope.

### 8.4 Bottom-up component resolution

Resolve components in topological order.

For `pair`:

    invoke A -> L_A
    invoke B -> L_B
    static par -> max(L_A, L_B)
    export result as T_pair

For `tail`:

    invoke A -> L_A
    static seq -> L_A
    export result as T_tail

Create timing interfaces:

    pair -> T_pair
    tail -> T_tail

For `pipeline`, provide only those interfaces:

    invoke pair -> interface(pair)
    invoke tail -> interface(tail)
    static seq -> sum(...)
    export result as T_total

### 8.5 Constraint checking

After component timing interfaces have been inferred, exported timing
variables are available to normal timing constraints.

For example:

    require total_deadline: T_total <= 8

No special deadline logic should exist in the component resolver.

The ordinary constraint mechanism evaluates the inferred value.

---

## 9. Canonical configuration experiment

Use the same five generator configurations as V1.2.

### C1

    L_A = 2
    L_B = 5

Expected:

    T_pair = 5
    T_tail = 2
    T_total = 7

Result:

    ACCEPT

### C2

    L_A = 5
    L_B = 2

Expected:

    T_pair = 5
    T_tail = 5
    T_total = 10

Result:

    REJECT total_deadline

### C3

    L_A = 3
    L_B = 3

Expected:

    T_pair = 3
    T_tail = 3
    T_total = 6

Result:

    ACCEPT

### C4

    L_A = 4
    L_B = 7

Expected:

    T_pair = 7
    T_tail = 4
    T_total = 11

Result:

    REJECT total_deadline

### C5

    L_A = 8
    L_B = 3

Expected:

    T_pair = 8
    T_tail = 8
    T_total = 16

Result:

    REJECT total_deadline

---

## 10. Central C1/C2 modularity test

C1 and C2 contain the same leaf-latency multiset:

    {2, 5}

They also expose the same `pair` timing interface:

    T_pair = 5

But they expose different `tail` interfaces:

    C1: T_tail = 2
    C2: T_tail = 5

The parent `pipeline` is unchanged and has no knowledge of A/B internals.

Therefore:

    C1:
        pair -> 5
        tail -> 2
        pipeline -> 7
        ACCEPT

    C2:
        pair -> 5
        tail -> 5
        pipeline -> 10
        REJECT

This is the primary V1.3 experiment.

---

## 11. Anti-cheating invariants

The prototype must satisfy all of the following.

### Invariant A — no handwritten timing equations

The canonical source contains no explicit timing bindings implementing:

    max(L_A, L_B)
    T_pair + T_tail
    or equivalent arithmetic

### Invariant B — parent contains no generator references

The `pipeline` component must not directly invoke A or B.

### Invariant C — parent timing resolution uses interfaces only

When resolving `pipeline`, child component bodies must not be traversed.

The resolver should consume a mapping conceptually equivalent to:

    {
        "pair": ComponentTimingInterface(...),
        "tail": ComponentTimingInterface(...),
    }

### Invariant D — source remains unchanged across configurations

C1-C5 use exactly one LAIR source file.

### Invariant E — symbolic IR remains unchanged across configurations

Generator configuration must enter only during generator elaboration.

### Invariant F — physical timing is independently validated

As in V1.1/V1.2, generated RTL latency must be checked independently.

### Invariant G — rejected configurations emit no Calyx

Generator RTL may exist because elaboration happens first.

Higher-level Calyx hardware must not be emitted after timing rejection.

---

## 12. Backend strategy

V1.3 timing semantics and V1.3 physical lowering are separate concerns.

The timing resolver must preserve component abstraction regardless of backend
implementation.

Preferred backend target:

    pair     -> separately lowered component
    tail     -> separately lowered component
    pipeline -> invokes pair and tail

However, Calyx/Piezo syntax and static-component invocation capabilities must
be confirmed before locking this implementation strategy.

If separate static component lowering requires substantial unrelated backend
work, V1.3 may initially lower resolved child bodies through an implementation
mechanism that preserves timing-interface semantics in the compiler.

But the following rule is non-negotiable:

    parent timing inference must never inspect child bodies.

Backend convenience must not weaken the compiler abstraction boundary.

---

## 13. What V1.3 does NOT attempt

V1.3 does not attempt:

- recursive components
- arbitrary parameterized timing formulas
- symbolic algebra across unresolved components
- general port/interface inference
- arbitrary generator families
- real FFT/DFT kernels
- synthesis/PPA evaluation
- novelty claims
- general performance claims

Those are later questions.

---

## 14. Required tests

At minimum:

1. Component declarations preserve names, arguments, timing variables, bodies.
2. Duplicate component names are rejected.
3. Generator/component namespace collisions are rejected.
4. Unknown component invocation is rejected.
5. Recursive component dependency is rejected.
6. Topological resolution resolves leaf components before parents.
7. `pair` C1 resolves to 5.
8. `tail` C1 resolves to 2.
9. `pipeline` C1 resolves to 7.
10. C2 resolves `pair=5`, `tail=5`, `pipeline=10`, then rejects deadline.
11. Parent resolution succeeds from component timing interfaces without child
    bodies.
12. TimingEnvironment cannot override inferred component interface timing.
13. V1.0 canonical symbolic hash remains unchanged.
14. Existing V1.0-V1.2 tests remain green.
15. One V1.3 source and one symbolic IR hash hold across C1-C5.

---

## 15. Physical experiment requirements

For accepted configurations C1 and C3:

- generator RTL latency independently validated
- Calyx emitted
- Verilator executes successfully
- expected memory output preserved

For rejected C2/C4/C5:

- generator RTL physically valid
- inferred component timings recorded
- `total_deadline` fails
- no Calyx emitted

Cycle counts are recorded empirically.

Do not assume the V1.2 cycle formula if backend component lowering changes.

---

## 16. Success criteria

V1.3 succeeds if all of the following hold:

1. One unchanged source expresses reusable `pair`, `tail`, and `pipeline`
   components.

2. The source contains zero explicit timing equations.

3. `pair`, `tail`, and `pipeline` export compiler-inferred timing interfaces.

4. The parent `pipeline` contains no direct generator references.

5. Parent timing is inferred only from child timing interfaces.

6. C1 and C2 expose the same `pair` timing but different `pipeline` timing.

7. C1 is accepted and C2 is rejected under the unchanged deadline.

8. Existing compiler regressions remain green.

9. Accepted configurations execute correctly in hardware.

10. Evidence is archived in a reproducible sweep.

---

## 17. Kill criteria

V1.3 should be reconsidered or redesigned if:

- the parent resolver must inspect child component bodies;
- component timing is manually restated in the source;
- timing-interface values are supplied through configuration rather than
  derived by the compiler;
- reusable components provide no abstraction beyond renaming nested control;
- supporting module boundaries requires duplicating timing logic outside the
  IR;
- the experiment produces no stronger modularity evidence than V1.2.

A failed kill criterion is useful evidence and should be documented rather
than hidden.

---

## 18. Research interpretation if successful

A successful V1.3 would support the narrower statement:

    Generator-resolved timing can be propagated through reusable accelerator
    component interfaces, allowing parent control timing and constraints to be
    resolved without exposing child implementation structure.

It would strengthen the argument that timing propagation belongs in an IR
abstraction rather than in one-off generator glue.

It would NOT establish:

- novelty relative to all prior compiler systems;
- superiority over every possible Python workflow;
- generality to realistic numerical generators;
- performance benefit on real applications.

Those require separate evidence.

---

## 19. Implementation order

Implement V1.3 in this order:

1. Component/interface AST
2. Component dependency analysis
3. Bottom-up interface resolver
4. Unit tests for abstraction boundary
5. Parser syntax
6. Compiler integration
7. Backend strategy validation
8. Physical C1 execution
9. C2 reversal rejection
10. C3/C4/C5 sweep
11. Same-source / same-IR evidence
12. Findings archive
13. Final regression
14. Git checkpoint

Do not begin the next stage until the previous abstraction invariant is
verified.

---

## 20. V1.3 design freeze statement

The defining property of V1.3 is:

    A parent component derives its timing from exported child timing
    interfaces, not from child implementation structure.

Everything else is secondary.

If an implementation choice violates this statement, the implementation is
wrong even if the numerical timing result is correct.

---

## 21. Abstraction-firewall requirement

The component-interface boundary must be enforced by API structure, not only
by convention.

Timing resolution should expose an operation conceptually equivalent to:

    resolve_component_control(
        body,
        generator_latencies,
        component_interfaces,
    )

where:

    generator_latencies:
        timing facts for generator instances directly visible to this
        component body

    component_interfaces:
        already-resolved timing interfaces for directly invoked user
        components

The canonical parent `pipeline` must be resolvable with:

    generator_latencies = {}

    component_interfaces = {
        "pair": ComponentTimingInterface(
            component="pair",
            latency=5,
        ),
        "tail": ComponentTimingInterface(
            component="tail",
            latency=2,
        ),
    }

and produce:

    T_total = 7

without receiving:

    pair.body
    tail.body
    L_A
    L_B
    generator A
    generator B

This is a required V1.3 unit test.

A numerical result of 7 is insufficient if the parent-resolution API still
has access to child implementation structure.

---

## 22. Timing-name ownership

All compiler-visible timing names must be unique.

The following namespaces participate in collision checking:

- generator latency variables
- explicit legacy timing bindings
- structural timing-region variables
- exported component timing variables

For the canonical V1.3 source:

    L_A
    L_B
    T_pair
    T_tail
    T_total

must denote five distinct timing facts.

The implementation must reject:

- two components exporting the same timing variable;
- a component export colliding with a generator latency variable;
- a component export colliding with a legacy explicit binding;
- an internal structural timing variable colliding with an exported component
  timing variable unless they intentionally denote the same compiler-owned
  result by construction.

The preferred V1.3 representation is that a component's exported timing
variable names the latency of its body directly rather than requiring a
separate duplicate timing fact.

---

## 23. Legacy canonical-IR compatibility

V1.0-V1.2 source programs must retain their historical canonical
representations.

Adding V1.3 component/interface support must therefore not introduce empty
V1.3-only fields into historical `to_dict()` output.

For example, fields such as:

    components
    entry

must be omitted when absent if including them would change historical
canonical serialization.

The existing V1.0 canonical hash regression remains a hard requirement.

V1.3 may extend the serialized representation for V1.3 programs, but it must
not retroactively rewrite the canonical representation of earlier versions.

---

## 24. Strong V1.3 boundary test

The central abstraction test is stronger than checking the complete-program
answer.

The implementation must separately demonstrate:

1. Resolve `pair` from generator timing facts.

       L_A = 2
       L_B = 5

       pair -> 5

2. Resolve `tail` from generator timing facts.

       L_A = 2

       tail -> 2

3. Discard child bodies from the parent-resolution context.

4. Construct only:

       pair -> 5
       tail -> 2

5. Resolve the unchanged `pipeline` body from those interfaces alone.

       pipeline -> 7

6. Repeat with C2:

       pair -> 5
       tail -> 5

       pipeline -> 10

The parent-resolution test should fail if child component bodies are required.

This test is the primary evidence that V1.3 adds a module-level timing
abstraction rather than merely recursively traversing a larger syntax tree.

---

## 25. Design-freeze acceptance checklist

The V1.3 design is considered frozen when all of the following are agreed:

- [x] Child timing is inferred from child implementation structure.
- [x] Child timing is exported through `ComponentTimingInterface`.
- [x] Parent timing consumes interfaces rather than child bodies.
- [x] Parent `pipeline` contains no generator invocation.
- [x] C1/C2 provide the principal structural-reversal experiment.
- [x] Component dependencies are acyclic in V1.3.
- [x] Timing-name collision rules are explicit.
- [x] Historical canonical IR representations must remain stable.
- [x] Backend implementation convenience cannot weaken timing abstraction.
- [x] Physical RTL validation remains independent.
- [x] Novelty and real-application claims remain outside V1.3.

With these conditions, the V1.3 research design is frozen.

Implementation changes may refine representation details, but they must not
weaken the abstraction-firewall requirement without explicitly revisiting the
design.

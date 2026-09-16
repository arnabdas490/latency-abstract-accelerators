from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from lair.ast import SymbolicProgram
from lair.calyx_backend import write_resolved_program_calyx
from lair.environment import TimingEnvironment
from lair.generator_elaboration import (
    ElaborationResult,
    ToyGeneratorConfig,
    elaborate_toy_generators,
    timing_environment_from_elaboration,
)
from lair.parser import parse_lair_file
from lair.resolver import (
    ResolvedComponentProgram,
    ResolvedProgram,
    resolve_component_program,
    resolve_program,
)


@dataclass(frozen=True)
class CompilationResult:
    """
    Successful end-to-end V1.1 compilation result.

    A CompilationResult exists only after:
      1. parsing,
      2. generator elaboration,
      3. automatic timing-environment construction,
      4. timing resolution / constraint checking,
      5. Calyx lowering.
    """

    source: Path
    rtl_output: Path
    calyx_output: Path
    elaboration: ElaborationResult
    timing_environment: TimingEnvironment
    resolved: (
        ResolvedProgram
        | ResolvedComponentProgram
    )
    extern_rtl: str



@dataclass(frozen=True)
class TimingCompilationResult:
    """
    Compilation state after parsing, generator elaboration, timing
    resolution, and constraint checking, but before backend lowering.
    """

    source: Path
    rtl_output: Path
    elaboration: ElaborationResult
    timing_environment: TimingEnvironment
    resolved: (
        ResolvedProgram
        | ResolvedComponentProgram
    )


def resolve_symbolic_program(
    symbolic: SymbolicProgram,
    environment: TimingEnvironment,
) -> (
    ResolvedProgram
    | ResolvedComponentProgram
):
    """
    Select the timing-resolution path without weakening historical
    V1.0-V1.2 behavior.
    """

    if symbolic.components:
        return resolve_component_program(
            symbolic,
            environment,
        )

    return resolve_program(
        symbolic,
        environment,
    )


def compile_lair_to_resolved(
    source: Path,
    config: ToyGeneratorConfig,
    *,
    rtl_output: Path,
) -> TimingCompilationResult:
    """
    Run LAIR through the complete frontend/timing pipeline while
    deliberately stopping before Calyx lowering.

    This stage is useful independently of backend support.
    """

    symbolic = parse_lair_file(
        source
    )

    elaboration = elaborate_toy_generators(
        symbolic,
        config,
        rtl_output,
    )

    environment = (
        timing_environment_from_elaboration(
            elaboration
        )
    )

    resolved = resolve_symbolic_program(
        symbolic,
        environment,
    )

    return TimingCompilationResult(
        source=source,
        rtl_output=rtl_output,
        elaboration=elaboration,
        timing_environment=environment,
        resolved=resolved,
    )


def compile_lair_file(
    source: Path,
    config: ToyGeneratorConfig,
    *,
    rtl_output: Path,
    calyx_output: Path,
) -> CompilationResult:
    """
    Compile a V1.1 LAIR source program to concrete Calyx.

    Generator configuration enters only through the generator
    elaboration stage. The compiler does not manually construct
    generator timing facts.

    If timing resolution or constraint checking fails, no Calyx output
    is emitted. Generated RTL is intentionally retained because
    generator elaboration occurred before higher-level timing checking.
    """

    # Never allow a stale successful Calyx program to survive a failed
    # compilation attempt.
    calyx_output.unlink(
        missing_ok=True
    )

    # 1. Textual LAIR -> symbolic program.
    symbolic = parse_lair_file(
        source
    )

    # 2. Generator declarations -> actual RTL + GeneratorResult objects.
    elaboration = elaborate_toy_generators(
        symbolic,
        config,
        rtl_output,
    )

    # 3. GeneratorResult objects -> compiler timing environment.
    environment = (
        timing_environment_from_elaboration(
            elaboration
        )
    )

    # 4. Symbolic timing resolution + constraint checking.
    resolved = resolve_symbolic_program(
        symbolic,
        environment,
    )

    # 5. Resolved IR -> concrete Calyx.
    relative_rtl = Path(
        os.path.relpath(
            rtl_output,
            start=calyx_output.parent,
        )
    ).as_posix()

    write_resolved_program_calyx(
        resolved,
        calyx_output,
        extern_rtl=relative_rtl,
    )

    return CompilationResult(
        source=source,
        rtl_output=rtl_output,
        calyx_output=calyx_output,
        elaboration=elaboration,
        timing_environment=environment,
        resolved=resolved,
        extern_rtl=relative_rtl,
    )

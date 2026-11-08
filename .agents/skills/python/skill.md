---
name: python-development
description: Implement and review Python transformations, repositories, workers, command-line tools, subprocess integrations, and file processing in this repository. Use Git history when clarification of prior behavior or design decisions is necessary.
---

# Python Development Guidelines

Read AGENTS.md and the documentation relevant to the changed feature.
Use the SQLAlchemy and FastAPI skills for persistence, migrations, authentication,
and transaction handling. Use any domain-specific skill when changing specialized source files.

## Structure and Data Contracts

- Preserve the existing separation between transformations, repositories,
  orchestration, and command-line entry points.
- Keep transformations deterministic and independent of database, network,
  and filesystem access where practical.
- Keep command-line argument parsing separate from reusable implementation.
  Avoid executing commands or starting external resources on module import.
- Add useful type annotations to changed interfaces. Use dataclasses or
  TypedDict when they clarify structured data; do not introduce a modeling
  framework solely for typing.
- Validate external JSON, CSV, database, and subprocess payloads at their
  boundaries. Type annotations are not runtime validation.
- Preserve distinctions between missing values, null, empty strings, zero,
  and false where the domain contract distinguishes them.
- Preserve identifier, date, numeric, and terminology semantics. Do not
  guess domain codes, units, timezones, or missing values.
- Keep dates distinct from timestamps. Follow the feature's timezone and
  serialization contract rather than applying implicit local conversions.

## Configuration and Dependencies

- Use the application settings/configuration layer for runtime
  configuration.
- Pass configuration explicitly into reusable helpers where practical;
  avoid scattered environment reads and hardcoded executable paths.
- Follow the repository's supported Python and dependency versions.
- Keep runtime dependencies in requirements-runtime.txt and development-only
  dependencies in the existing development requirements.
- Reuse existing libraries and helpers before adding dependencies.
- Do not introduce a new formatter, linter, package manager, or broad style
  rewrite as part of an unrelated implementation change.

## Raw PostgreSQL and Resource Ownership

- Use the established tenant-aware repositories and connection factories.
  Do not construct an alternative tenant-routing mechanism.
- Bind SQL values as parameters. Compose dynamic identifiers with
  psycopg.sql.Identifier rather than string interpolation.
- Keep operations that share a transaction or connection-scoped lock on
  the same connection.
- Use context managers or explicit finally blocks for connections, cursors,
  files, and temporary resources.
- Follow the existing worker and pool initialization lifecycle. Do not
  introduce live database connections shared across process boundaries.
- Preserve lock ordering, transaction boundaries, and rollback behavior
  when refactoring repository code.

## Subprocess Integration

- Pass commands as argument sequences with an explicit working directory.
  Avoid shell interpolation of user-controlled values.
- Use the configured Node or Java executable and existing integration
  helpers rather than creating a parallel execution path.
- Check return codes and validate output before treating execution as
  successful. Use an explicit encoding for text protocols.
- Provide appropriate timeouts. For cancellable execution, preserve the
  existing polling, termination, forced-stop, and process-reaping behavior.
- Drain subprocess pipes safely and account for output size when deciding
  whether to capture output in memory.
- Do not expose sensitive payloads, credentials, or unrestricted subprocess
  output in user-facing errors or logs.
- Preserve Windows development and Linux deployment compatibility.

## Files, Artifacts, and Caches

- Use pathlib and explicit text encodings.
- Resolve externally influenced paths and verify that they stay within the
  intended storage root before reading, writing, or deleting files.
- Use scoped temporary directories and close file handles before handing
  files to another process or replacing them.
- For shared caches and generated indexes, follow the existing temporary
  file and atomic-replacement pattern so readers cannot see partial files.
- Include the relevant version, revision, context, and configuration inputs
  in cache identity where they affect the result.
- Validate cached content before reuse. Follow the feature's recovery
  behavior for missing or corrupt artifacts.
- Restrict cleanup to artifacts owned by the current operation; preserve
  files belonging to active or completed jobs.

## Bounded Work and Failure Handling

- Use bounded batches, iterators, and streaming for large datasets.
  Avoid repeated serialization and unnecessary copies of large payloads.
- Do not introduce nested thread or process pools without assessing the
  existing Celery concurrency and database connection budget.
- Catch specific expected exceptions near the boundary that can handle
  them. Preserve causes with `raise ... from exc` when translating errors.
- Do not convert failures into empty successful results.
- Retry only appropriate transient failures through the existing recovery
  mechanism. Keep cancellation distinct from failure.
- Use monotonic time for elapsed-time deadlines and performance counters
  for timings; use timezone-aware timestamps for persisted event times.
- Log operational identifiers, counts, stages, and durations rather than
  sensitive payloads.

## Verification

- Test observable behavior and contracts rather than private implementation
  details.
- Use focused unit tests for transformations and parsing; mock external
  boundaries rather than the core behavior under test.
- Use integration tests when correctness depends on PostgreSQL, Node,
  Java translation, or filesystem behavior.
- Cover relevant malformed input, empty input, Unicode, numeric and date
  boundaries, subprocess failure, timeout, cancellation, and cleanup.
- Use disposable directories and the established scratch-database helpers.
- For performance changes, compare equivalent inputs and configurations;
  distinguish synthetic benchmarks from end-to-end measurements.
- Follow AGENTS.md documentation and verification requirements.
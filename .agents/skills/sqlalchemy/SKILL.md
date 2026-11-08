---
description: Implement SQLAlchemy 2.x persistence with PostgreSQL,
  including ORM mappings, queries, sessions, transactions, connection
  pools, and Alembic migrations. Use when changing database models or
  data-access behavior.
name: sqlalchemy
---

# SQLAlchemy Skill

## 1. Scope and defaults

-   Follow `AGENTS.md`, architecture documentation, the FastAPI skill
    for HTTP concerns, and the Python and testing skills.
-   Use SQLAlchemy **2.x typed declarative mappings** and its 2.x
    query/execution APIs.
-   **Default to synchronous SQLAlchemy** with `Session` and a
    synchronous PostgreSQL driver. Use `AsyncSession` and an async
    driver only when asynchronous database I/O has a clear benefit or
    the user explicitly requests it.
-   Do not convert existing synchronous code to async merely for
    consistency or fashion. Do not mix sync and async engines, sessions,
    drivers, or lifecycle patterns.
-   Inspect installed SQLAlchemy, driver, and Alembic versions before
    using version-specific APIs.

## 2. ORM mappings and queries

-   Use `Mapped[...]`, `mapped_column()`, and typed declarative models.
-   Use `select()`, `insert()`, `update()`, and `delete()` with the 2.x
    execution model. Do not introduce legacy `Query`-based code.
-   Keep ORM models separate from Pydantic API schemas. Do not expose
    ORM objects directly as API contracts.
-   Model primary keys, foreign keys, nullability, uniqueness, check
    constraints, indexes, and relationship deletion behavior explicitly
    according to domain requirements.
-   Define relationship loading deliberately. Avoid accidental
    lazy-loading loops, N+1 queries, and loading large relationships
    when only identifiers or aggregates are needed.
-   Filter and paginate in the database. Avoid loading whole tables into
    Python for filtering, sorting, or aggregation.
-   Use bound parameters for textual SQL. Never interpolate
    user-controlled values into SQL strings.
-   Use bulk operations only after verifying their effects on ORM
    events, relationships, defaults, and business invariants.
-   Do not create a repository class for every model automatically.
    Follow existing project patterns and add abstractions only when they
    provide a clear benefit.

## 3. Sessions and transaction boundaries

-   Create engines and session factories in centralized database
    infrastructure, not inside request handlers, services, or individual
    tasks.
-   Use one session per independent unit of work. A `Session` or
    `AsyncSession` must not be shared across concurrent requests,
    threads, asyncio tasks, or independent Celery tasks.
-   In synchronous request handling, provide sessions through a
    context-managed or generator dependency that reliably closes them.
-   Make transaction ownership explicit. Prefer a clear service-level
    transaction boundary for a logical operation involving multiple
    writes.
-   Do not commit inside every repository function when the operations
    belong to one transaction.
-   Use `flush()` when generated values or constraint checks are needed
    before commit. `flush()` is not `commit()`.
-   Roll back failed transactions and propagate or translate exceptions
    deliberately. After a failed flush, do not continue using the
    session until its transaction has been rolled back.
-   Keep transactions short. Do not hold locks or open transactions
    across slow external calls, long calculations, or background
    execution.
-   Use `with_for_update()` or other locking mechanisms only where
    required by the concurrency contract. Understand lock scope and
    transaction isolation.
-   Preserve optimistic concurrency checks, revisions, leases, fencing,
    and idempotency when they are part of existing behavior.
-   Dispatch dependent work only after commit. If reliable delivery
    across process crashes is required, preserve the existing durable
    dispatch mechanism or use a transactional outbox.

## 4. Master and tenant database isolation

The application uses a master PostgreSQL database and separate tenant
databases.

-   Use distinct, explicit master and tenant engine/session-factory
    infrastructure according to the project's database architecture.
-   Resolve tenant identity through trusted server-side tenant context,
    such as the validated hostname and master registry. Never accept an
    arbitrary database name or connection string from a client.
-   Validate tenant existence and access before acquiring a tenant
    session. Fail closed if tenant context is missing or invalid.
-   Never reuse a session or transaction across tenants. Do not silently
    fall back to a default tenant.
-   Make tenant context explicit in service and worker calls;
    request-local context must not be assumed to survive after the
    request.
-   Keep master-database responsibilities and tenant-database
    responsibilities explicit. Do not write tenant-specific data to the
    master database unless the schema explicitly requires it.
-   Recognize that a transaction in one PostgreSQL database cannot
    atomically commit changes in another database. For cross-database
    workflows, use an explicit consistency, retry, and recovery
    strategy.
-   Prevent tenant leakage through cached sessions, connection state,
    ORM identity maps, query results, and application caches.
-   Add tests for invalid tenant context and cross-tenant isolation when
    modifying tenant-aware persistence.

## 5. Connection pools and resource limits

-   Create each engine once per intended process/database configuration,
    not per request.
-   Calculate total possible connections across application processes,
    Uvicorn workers, Celery processes, tenant engines, pool size, and
    overflow.
-   Keep tenant connection pools bounded and avoid retaining unbounded
    numbers of engines for inactive tenants.
-   Configure pool timeouts, recycling, health checks, and disposal
    based on the deployment environment and PostgreSQL/PgBouncer
    configuration.
-   Verify the chosen pool mode is compatible with prepared statements,
    session-level state, and transaction assumptions.
-   Do not use `NullPool`, unlimited overflow, or frequent engine
    disposal as a generic fix without evidence and a documented reason.
-   Ensure worker processes create or initialize their own database
    resources appropriately after process startup; do not share live
    connections across forked processes.

## 6. Async-specific rules

Apply this section only when async SQLAlchemy is justified or explicitly
requested.

-   Use `create_async_engine()`, `async_sessionmaker`, and
    `AsyncSession` with a compatible async driver.
-   Await database operations and use async context managers for session
    and transaction lifecycles.
-   Never share an `AsyncSession` across concurrent tasks. Create a
    separate session per independent concurrent unit of work.
-   Avoid implicit lazy loads or expired-attribute access that triggers
    unexpected I/O. Use deliberate eager-loading strategies and explicit
    refreshes as needed.
-   Do not call synchronous SQLAlchemy methods or blocking database
    drivers as if they were asynchronous.
-   Do not introduce async database access into Celery workers unless
    the worker execution model and resource lifecycle explicitly support
    it.
-   Measure whether async access benefits the actual workload. It does not make CPU-bound workloads faster and does not remove database connection limits.

## 7. Schema management and Alembic

- Inspect the actual database schema, constraints, indexes, defaults, and data before mapping existing tables.
- Map SQLAlchemy models to the adopted schema; do not rename, drop, or redesign tables as an incidental part of ORM adoption.
- Alembic is the sole owner of application schema changes. Keep master and tenant migration histories separate where their lifecycles differ.
- Baseline Alembic against an existing schema only after validating the objects and version state. Review autogenerated migrations manually before applying them.
- Plan migration execution for every applicable tenant database as well as the master database. Make execution observable, resumable, and safe to retry.
- Verify actual database objects and representative data; never assume ORM metadata fully describes the deployed schema.
- Back up and rehearse risky migrations and recovery before production rollout.

## 8. Performance and correctness

-   Diagnose before optimizing. Inspect query counts, generated SQL,
    `EXPLAIN` plans, indexes, transaction duration, lock waits, and pool
    utilization as appropriate.
-   Use database-side filtering, aggregation, and pagination when
    practical.
-   Select eager-loading strategies based on access patterns; avoid both
    N+1 queries and unnecessarily large joined result sets.
-   Keep indexes aligned with query predicates and ordering, accounting
    for write overhead.
-   Use database constraints for invariants that must hold under
    concurrency; application-only checks are not sufficient for every
    uniqueness or consistency requirement.
-   Do not introduce caching, denormalization, raw SQL, bulk writes, or
    isolation-level changes without a justified requirement and
    validation.
-   Never log credentials, connection strings, access tokens, or
    unnecessary patient/clinical data.

## 9. Testing and definition of done

-   Follow the project testing skill and use isolated test databases or
    controlled fixtures.
-   Test persistence behavior, constraints, rollback, concurrent
    updates, and query semantics relevant to the change.
-   Test tenant isolation for tenant-aware operations and cross-database
    consistency behavior for workflows spanning master and tenant
    databases.
-   Test migrations against a representative existing schema and data
    set where practical.
-   Run the relevant project-defined formatting, linting, type-checking,
    migration checks, and tests. Report actual results without claiming
    unexecuted checks passed.
-   Review transaction ownership, session cleanup, pool impact, and
    compatibility with application services and worker execution.
-   Summarize schema changes, migration steps, validation results, and
    remaining operational risks.

---
description: Build and maintain FastAPI HTTP APIs, routing,
  dependencies, validation, authentication integration, error handling,
  and OpenAPI contracts. Use when implementing API endpoints or FastAPI
  application structure.
name: fastapi
---

# FastAPI Skill

## 1. Scope and shared rules

-   Follow `AGENTS.md`, project architecture documentation, and the
    project's Python and testing skills.
-   This skill governs HTTP/API concerns. Follow the SQLAlchemy skill
    for ORM models, queries, sessions, transactions, and database
    connection management.
-   Prefer small, focused changes. Preserve established behavior and API
    compatibility unless the task explicitly authorizes a change.
-   Reuse existing business services; do not move substantial business
    logic into route handlers or duplicate existing behavior.
-   Inspect the installed FastAPI, Pydantic, and dependency versions
    before using version-specific features.

## 2. Endpoint execution model

-   **Default to synchronous `def` path operations and dependencies.**
-   Use `async def` only when the endpoint has a clear asynchronous
    benefit (for example, concurrent I/O through genuinely asynchronous
    clients) or the user explicitly requests it.
-   Do not use `async def` merely because FastAPI supports it or because
    an endpoint is an API.
-   Never perform blocking synchronous database, filesystem,
    HTTP-client, or other I/O directly inside an `async def` handler.
    Use the appropriate async client or a suitable thread-pool boundary.
-   Do not mix sync and async database APIs within the same session
    lifecycle. Follow the SQLAlchemy skill.
-   If an async endpoint calls a synchronous service, verify that the
    call will not block the event loop; do not assume FastAPI
    automatically offloads arbitrary helper functions.

## 3. API structure and contracts

-   Organize endpoints into feature-based `APIRouter` modules. Keep
    application setup, router registration, dependencies, schemas, and
    business services separate according to project conventions.
-   Use Pydantic v2 schemas for request validation and response
    serialization. Keep API schemas separate from ORM models.
-   Declare response models explicitly for structured responses. Return
    only fields the caller is authorized to see; do not expose internal
    ORM fields by default.
-   Follow the project's API versioning convention; use `/api/v1/` for
    new routes when consistent with the project API versioning convention.
-   Apply consistent conventions for pagination, filtering, sorting,
    timestamps, empty results, and error payloads.
-   Use appropriate HTTP methods and status codes. Distinguish malformed
    input, unauthenticated requests, forbidden operations, missing
    resources, and state conflicts.
-   Keep OpenAPI descriptions and examples accurate. Update or
    regenerate the TypeScript client when the project uses one and an
    API contract changes.
-   Avoid unbounded result sets, oversized payloads, and implicit
    response shapes.

## 4. Dependencies and request context

-   Use FastAPI dependencies for shared request-scoped concerns such as
    authenticated principal, validated tenant context, and database
    session acquisition.
-   Keep dependencies focused and composable. Avoid hidden side effects
    in dependencies.
-   Make resource lifetimes explicit. Do not pass request-scoped
    resources into work that outlives the request.
-   Resolve tenant context on the server using the validated hostname
    and master tenant registry, following the project's tenant
    architecture.
-   Never trust a tenant database name, connection string, role, or
    authorization claim supplied only by the frontend.
-   Fail closed when tenant context is missing, invalid, inactive, or
    inconsistent. Never silently fall back to a default tenant.

## 5. Authentication and authorization

-   Preserve the established identity and authorization model unless the
    task explicitly changes it.
-   Do not replace established allauth/onboarding/invitation behavior
    with a basic JWT endpoint as a shortcut.
-   Keep authentication, tenant membership, role checks, suspension
    status, and resource-level authorization distinct.
-   Enforce authorization on every protected read, write, download,
    job-status, and cancellation operation. Frontend route guards are
    not security controls.
-   Keep authentication integration behind clear dependencies or service
    interfaces so it can be tested and changed without coupling unrelated features.
-   Preserve CSRF protection when using cookie-based authentication.
    Restrict CORS to known origins only when cross-origin requests are
    needed.
-   Return safe client errors; never expose stack traces, secrets, SQL,
    tokens, or internal connection details.

## 6. Business services and background work

- Reuse existing business services and keep route handlers focused on HTTP concerns. Avoid duplicating domain logic across endpoints.
- Keep long-running calculations and durable background work in the existing Celery system. Do not replace Celery with FastAPI `BackgroundTasks` without an explicit architectural decision.
- Do not pass ORM instances, request objects, or request-scoped sessions to Celery. Pass durable identifiers and validated execution context; create fresh worker-side resources.
- Preserve job state transitions, idempotency, retries, cancellation, leases, locks, fencing, recovery, and commit-dependent dispatch semantics.

## 7. Errors, security, and observability

-   Use centralized exception handling for consistent error responses.
    Translate expected domain errors deliberately; do not swallow
    unexpected exceptions.
-   Validate inputs at the API boundary and enforce domain invariants in
    the service/database layers as appropriate.
-   Log useful correlation identifiers and exception context without
    logging secrets or unnecessary patient/clinical data.
-   Apply request size limits, timeouts, and upload/download
    authorization appropriate to the endpoint.
-   Keep patient data and report files private; authorize each access
    rather than relying on obscure URLs.
-   Do not add caching, retries, concurrency, or rate-limiting behavior
    without checking correctness and operational implications.

## 8. Testing and definition of done

-   Follow the project's testing skill. Implement relevant tests with
    feature code unless the task explicitly separates the work.
-   Test request/response contracts, validation, status codes,
    authentication, authorization, and failure paths.
-   For tenant-aware endpoints, test missing or invalid tenant context,
    inactive tenants, and cross-tenant access.
-   Test transaction and job-dispatch behavior when the endpoint changes
    writes or triggers background work.
-   Use controlled test dependencies and isolated test databases. Never
    run destructive tests against production or shared environments.
-   Run the relevant project-defined formatter, linter, type checker,
    and tests. Report what actually ran and its result; never claim
    unexecuted validation passed.
-   Update API documentation and generated TypeScript contracts when
    required.
-   Summarize changes, validation results, compatibility considerations,
    and unresolved risks.

# AI Coding Agent Instructions

Read this file first, then the repository documentation index (if present) and only the task-relevant documentation and skills.

## Project and development objective

- Build a web-based, voice-only chatbot using Pipecat. Support English only; user authentication is out of scope for now.
- Develop in VS Code on Windows with Docker Desktop; deploy Linux containers using Docker Compose on Linux. Keep development and deployment configuration aligned and document platform differences.
- Target the user's Intel Core Ultra 5 processor and Intel Arc graphics. Confirm the exact CPU/GPU models, RAM, graphics memory, drivers, and device visibility before selecting models or claiming acceleration. Evaluate an NPU only if present and supported.
- Prioritize effective hardware use and low conversational latency. Evaluate Intel-compatible inference such as OpenVINO, model quantization, and CPU/GPU placement against measured latency, quality, memory, and concurrent-session performance. Keep a working CPU fallback; do not assume CUDA or Intel GPU passthrough through Docker Desktop.
- Preserve Pipecat's established streaming/asynchronous pipeline, interruption handling, cancellation, and resource cleanup. Voice-only interaction may include accessible session controls and status; do not add typed chat, video, other languages, or authentication without a scope change.
- Treat the root [README.md](README.md) as the project overview and initial documentation entry point. Update it in the same change whenever objectives, architecture, setup, hardware support, configuration, deployment, or verification instructions change. Clearly separate planned capabilities from implemented and tested behavior; document only commands that exist.
- Follow the repository's established synchronous or asynchronous execution model. Introduce async execution only when justified by workload requirements or explicitly requested.

## Database and tenancy

- Identify the authoritative database(s) and ownership boundaries before making schema or data changes. Verify the effective connection and target database before database-changing commands.
- Keep shared/master data separate from tenant-specific data when the application uses database-per-tenant or master/tenant architecture. Never bypass routing or write data to the wrong database.
- State whether each schema change affects shared data, tenant data, or both. Keep migration ownership and histories explicit where lifecycles differ.
- Apply tenant schema changes to every applicable tenant database; report each status and support safe retry/recovery. Provisioning must apply the current schema before activation.
- Review generated migrations for existing objects, constraints, indexes, defaults, and data compatibility.
- Review destructive or irreversible changes before execution. Preserve data/schema compatibility; validate representative data and rehearse recovery for risky changes.

## API contracts and feature completeness

- Treat the repository's published API specification (such as OpenAPI) as the authoritative contract for implemented endpoints.
- Before implementing or modifying a frontend feature, verify the required workflow against available backend endpoints, schemas, permissions, validations, and data effects.
- Identify missing or incomplete backend capabilities; do not silently omit required behavior because an API is unavailable. Coordinate frontend and backend work against an agreed contract.
- Generate and use client API types from the current API specification where supported. Do not invent request/response contracts independently.
- Verify end-to-end behavior, including authorization, validation, error handling, and important workflow states.

## System invariants

- Preserve established service boundaries, queue boundaries, durable dispatch/recovery, and worker isolation.
- Do not expose private files through unauthenticated static paths or commit secrets to tracked files, images, or deployment configuration.
- Do not change lifecycle, revision, fencing, lease, cancellation, or idempotency semantics without reviewing the owning feature documentation and tests.
- Before creating a file, identify its intended location from the repository structure and applicable instructions. Never create files at arbitrary locations.

## Testing and completion

- Follow the repository's testing skill for test organization, discovery and execution conventions, test quality, phase separation, required checks, and completion reporting.
- Use Playwright for user-facing browser flows when applicable; cover changed behavior, validation, and important failure states with accessible locators and deterministic data.
- For substantial UI changes, follow the UI/UX skill and inspect screenshots at desktop and narrower widths. A passing build alone is not visual acceptance.
- Update affected docs when behavior, contracts, schemas, configuration, deployment, or operations change. Before completion, check documentation accuracy, links, duplication, and source-of-truth consistency.

## Documentation and skill routing

Use the repository documentation index for the task-oriented documentation map. Keep docs concise; maintain one authoritative source per rule and link to it. Code is authoritative for implementation behavior; docs are authoritative for architectural intent, business rules, contracts, operations, and non-obvious constraints. Investigate conflicts instead of blindly overwriting either.

Load only the smallest relevant documentation cluster. Use the skills available in the repository for implementation guidance; do not duplicate framework-specific instructions across skills.

---
name: testing
description: Cross-technology policy for test organization, authoring, discovery, execution, and verification.
---

# Testing Skill

## 1. Test Organization and Discovery

Use the repository's established test structure and naming conventions. Keep tests easy to discover by purpose, module, and scope.

```text
tests/
├── backend/
│   ├── focused/<module_name>/
│   ├── regression/
│   └── performance/
├── user_interface/
│   ├── focused/<module_name>/
│   ├── regression/
│   └── performance/
├── end_to_end/
│   ├── critical_workflows/
│   └── cross_module/
├── scripts/
│   ├── backend/
│   ├── user_interface/
│   └── start_all_regression.ps1
└── README.md
```

- Use descriptive module and directory names, and explicit test names that state the behavior or scenario being verified.
- **Angular unit tests stay colocated** with their source files and use `*.spec.ts`. Do not duplicate them under `tests/`.
- Use `tests/user_interface/` for targeted or cross-component browser tests (for example, Playwright) when browser behavior needs verification.
- Put backend focused tests in `tests/backend/focused/<module_name>/`. They may test one module and its immediate dependency interactions, including isolated API behavior.
- Put dedicated cross-module and end-to-end regression scenarios in the relevant `regression/` directories or `tests/end_to_end/`, according to their scope.
- End-to-end tests must exercise complete, real application workflows through Angular, FastAPI, authentication, and PostgreSQL where applicable. Do not replace integration with mocks when the purpose is to verify the real workflow.
- A test may be both module-focused and regression-relevant. Use the project's test markers/tags to classify regression coverage without duplicating tests solely for that reason.

## 2. Single Discovery and Execution Convention

The repository must document one predictable way to discover and run each test category, regardless of where test files live.

- Treat the relevant test runner's configuration and the repository's `tests/README.md` as the source of truth for discovery rules, markers/tags, environment requirements, reports, and commands.
- Expose consistent root-level commands through `package.json` and PowerShell launchers. Use `package.json` scripts as the common entry point where available; scripts should delegate to the appropriate runner/launcher rather than reimplement test logic.
- Provide focused commands by module, plus backend/UI regression, performance, end-to-end, and all-regression commands. Use descriptive names such as `test:backend:focused:module-a`, `test:ui:regression`, and `test:regression`; adapt names to existing project conventions.
- Keep launchers under `tests/scripts/`. Use descriptive names such as `start_backend_focused_module_a.ps1`, `start_backend_regression.ps1`, `start_ui_focused_module_a.ps1`, `start_ui_performance.ps1`, and `start_all_regression.ps1`.
- PowerShell launchers are orchestration only: invoke the correct test runner, pass filters/configuration, set or validate required environment variables, produce reports, clean up resources where appropriate, and return a meaningful non-zero exit code on failure. Do not put test logic in launch scripts.
- Keep `tests/README.md` aligned with actual runner configuration and commands. Do not invent commands or assume a test runner; inspect the repository's `package.json`, runner configuration, and existing scripts first.

## 3. Test Policy and Required Checks

- **When modifying a testable unit**, identify and run its associated tests. For Angular components, services, directives, pipes, and other testable units, find and run the corresponding colocated `*.spec.ts` tests using the Angular test runner configured by the project and commands exposed in `package.json`.
- **When creating a testable unit**, create appropriate unit tests alongside it. For Angular, add the `*.spec.ts` file beside the source. For other technologies, follow the repository's focused-test convention.
- After a code change, run the narrowest relevant tests first, then the applicable module-focused suite and broader regression checks. Run UI or end-to-end tests when the change affects browser behavior, API contracts, authentication, tenant isolation, or cross-module workflows.
- Before declaring a change complete, run the required checks available for the change: relevant unit/focused tests, applicable regression tests, and relevant lint/type-check/build checks. Run performance tests when performance-sensitive code or explicit performance requirements are involved.
- Backend regression coverage should include applicable previously discovered defects, critical business rules, authorization, tenant isolation, API contracts, and important workflows. UI regression coverage should protect critical screens and interactions.
- Performance tests should measure relevant response latency, throughput, resource consumption, and concurrency behavior. Use repeatable conditions and report the environment and key parameters.
- Follow the configured runner's discovery rules so colocated Angular specs and tests under `tests/` are both discoverable through the documented commands. Do not assume a single directory contains every test.

## 4. Test Quality and Phase Separation

- Follow existing project conventions and derive assertions from requirements and independently verified expected behavior.
- Cover normal behavior, boundary cases, invalid inputs, error handling, and relevant regressions. Prefer deterministic tests that verify observable behavior.
- **Implementation phase:** modify production code and run relevant existing tests; do not also create or modify tests unless explicitly asked to implement functionality and tests together.
- **Test-authoring phase:** create or modify tests only; do not change production code to make tests pass. Keep implementation and test changes logically separated and independently reviewable.
- Update existing tests only when requirements intentionally change, not merely because implementation fails them.
- Never weaken, skip, delete, or suppress tests merely to obtain passing results.

## 5. Execution Results and Completion Report

- Distinguish new failures from pre-existing failures and environmental issues. Never claim tests passed unless they were actually executed successfully.
- If a test cannot run, state why and identify what remains unverified. Do not silently change code or tests to conceal failures.
- Briefly report the changes made, test commands executed and results, unresolved issues, and the next step if another phase is required.

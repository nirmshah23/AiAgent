---
name: angular-core
description: Develop maintainable applications using Angular Core 21, TypeScript, modern Angular APIs, routing, forms, HTTP, and reactive state.
---

# Angular Core Development

## 1. Project Rules
- Target Angular Core 21.2.25.
- Treat `package.json`, the lockfile, and existing source code as the source of truth.
- Inspect relevant components, services, routes, models, and tests before making changes.
- Follow existing project architecture and naming conventions.
- Keep changes focused. Avoid unrelated refactoring and unnecessary dependencies.
- Do not upgrade, downgrade, or replace dependencies without explicit approval.
- Use strict TypeScript typing. Avoid `any`, unnecessary type assertions, and non-null assertions.

## 2. Angular 21 Conventions
- Prefer standalone components, directives, and pipes for new development.
- Use built-in template control flow: `@if`, `@else`, `@for`, and `@switch`.
- Use stable `track` expressions in `@for` loops.
- Prefer `input()` and `input.required()` for inputs and `output()` for custom events.
- Use `model()` only when two-way component binding is appropriate.
- Use `signal()` for writable local state and `computed()` for derived state.
- Reserve `effect()` for appropriate side effects and external synchronization rather than routine state derivation.
- Prefer `inject()` when consistent with project conventions.
- Use `ChangeDetectionStrategy.OnPush` for new components unless a documented reason justifies otherwise.
- Use Angular lifecycle and cleanup APIs, including `DestroyRef` and `takeUntilDestroyed()`, when appropriate.
- Do not migrate existing code to newer APIs solely for stylistic consistency.

## 3. Components and Architecture
- Keep components focused on a single responsibility.
- Keep templates readable and move complex business logic into appropriate services or component methods.
- Define explicit interfaces and types for domain models and API responses.
- Avoid duplicating components, validation rules, API calls, and business logic.
- Use lazy-loaded routes when appropriate.
- Follow existing dependency-injection and error-handling conventions.

## 4. State and Asynchronous Operations
- Use signals for local UI state and derived values.
- Use RxJS for asynchronous streams, HTTP composition, and stream-oriented workflows.
- Avoid converting observables to signals or promises without a clear reason.
- Keep server state distinct from transient UI state.
- Do not introduce global state management libraries without a clear requirement.
- Handle subscriptions and component lifecycles correctly.
- Do not swallow errors silently.

## 5. Forms
- Prefer typed reactive forms for complex forms and data-entry workflows.
- Use template-driven forms when appropriate for simpler features or established project conventions.
- Define validators explicitly and reuse validation logic where appropriate.
- Keep client-side validation consistent with backend contracts.
- Display understandable validation messages and preserve entered values when recoverable errors occur.
- Prevent duplicate submissions when necessary.
- Never rely exclusively on client-side validation for security or data integrity.

## 6. HTTP and API Integration
- Use `HttpClient` and typed services for backend communication.
- Follow existing API contracts, interceptors, authentication mechanisms, and environment configuration.
- Inspect services, schemas, or documentation instead of inventing endpoints, payloads, or response fields.
- Never hardcode credentials, tokens, or environment-specific API URLs.
- Handle loading, success, empty, and error states explicitly.
- Do not display raw technical errors to users.

## 7. Accessibility and Responsiveness
- Use semantic HTML and meaningful headings, labels, and descriptions.
- Ensure keyboard accessibility and visible focus indicators.
- Provide meaningful accessible names for interactive controls.
- Associate validation errors with their respective controls.
- Do not rely on color alone to communicate errors or status.
- Use ARIA attributes when needed without duplicating native HTML semantics.
- Build responsive layouts for desktop, tablet, and mobile.
- Follow the application's existing CSS/SCSS conventions.

## 8. Testing and Validation
- Follow the repository's configured testing framework and existing test conventions.
- Inspect existing tests and test utilities before introducing new patterns.
- Add or update tests when requested, when behavior changes, or when necessary to verify correctness.
- Test observable behavior rather than private implementation details.
- Cover important business logic, validation, interactions, and error handling.
- Do not weaken or delete tests merely to make them pass.
- Run relevant test, lint, type-check, and build commands available in the project.
- Report which commands were actually executed and their results.
- If a command cannot run, explain why. Never claim unexecuted validation succeeded.

## 9. Development Workflow
1. Inspect relevant implementation, dependencies, API contracts, and tests.
2. Identify the smallest change that satisfies the requirement.
3. Implement using Angular 21 APIs and established project conventions.
4. Review the changes for correctness and unintended modifications.
5. Run relevant validation commands.
6. Summarize files changed, implementation decisions, validation results, and remaining limitations.

## 10. Definition of Done
- The requested behavior is implemented.
- Code follows project conventions and supported Angular 21 APIs.
- Relevant tests are added or updated when appropriate.
- Applicable validation commands have been executed, or their inability to run is reported.
- No unrelated changes, unnecessary dependencies, or fabricated API assumptions have been introduced.

## 11. Restrictions
- Do not change framework versions without approval.
- Do not bypass TypeScript errors, lint rules, or failing tests merely to complete a task.
- Do not perform broad refactoring when a focused change is sufficient.
- Ask for clarification when consequential ambiguity or architectural conflicts prevent a reliable implementation.

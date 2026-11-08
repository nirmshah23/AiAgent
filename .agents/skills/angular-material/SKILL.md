---
name: angular-material
description: Build maintainable, accessible Angular 21 interfaces using Angular Material 21, modern Angular APIs, theming, forms, tables, dialogs, and navigation.
---

# Angular and Angular Material Development

## 1. Project Rules
- Target Angular Core 21.2.25 and Angular Material 21.2.14.
- Treat `package.json`, the lockfile, existing code, API contracts, tests, and configured Material theme as the source of truth.
- Inspect relevant components, services, routes, models, theme configuration, and tests before changing code.
- Follow established architecture and naming conventions. Keep changes focused; avoid unrelated refactoring and unnecessary dependencies.
- Do not change framework versions or introduce another UI library without explicit approval.
- Use strict TypeScript typing; avoid `any`, unnecessary assertions, and non-null assertions.

## 2. Angular Conventions
- Prefer standalone components, directives, and pipes for new development.
- Use `@if`, `@else`, `@for`, and `@switch`; provide stable `track` expressions in `@for`.
- Prefer `input()` / `input.required()`, `output()`, and `model()` only when two-way binding is appropriate.
- Use `signal()` for writable local state and `computed()` for derived state. Reserve `effect()` for appropriate side effects.
- Prefer `inject()` when consistent with project conventions.
- Use `ChangeDetectionStrategy.OnPush` for new components unless there is a documented reason not to.
- Use `DestroyRef` and `takeUntilDestroyed()` for subscription cleanup when appropriate.
- Do not migrate existing code to newer APIs solely for stylistic consistency.

## 3. Component Selection
Choose the component that best fits the interaction. Prefer Angular Material over custom controls unless an explicit requirement, accessibility, usability, or established project pattern justifies otherwise.

### Forms and Inputs
- Calendar date: use `MatDatepicker`; date range: use the Material date range picker.
- Date and time: combine a date picker with an appropriate time input or picker; the standard date picker does not select time.
- Boolean: use a checkbox for independent selection and a slide toggle for an immediate on/off setting.
- Single choice: use `mat-select`; use radio buttons when a small set of mutually exclusive options should remain visible.
- Multiple choices: use checkboxes for a small set; use a suitable multi-select pattern for larger sets.
- Searchable or large/remote choices: use autocomplete with appropriate filtering, loading, and empty states.
- Free-form text: use an input; multiline text: use a textarea.
- Numeric values: use an appropriate input and explicit validation. Do not use `type="number"` by default for identifiers, postal codes, or values where leading zeros matter.
- Passwords: use a password input and consider an accessible visibility control.
- Use visible labels, suitable input types, clear validation messages, and field-level errors. Do not rely only on snackbars for validation.

### Data and Layout
- Structured rows and columns: use `MatTable`.
- For large datasets, consider server-side filtering, sorting, and pagination when supported by the API; follow existing client/server data patterns.
- Use cards for meaningful groups of related information and expansion panels for supplementary content that benefits from being collapsible.
- Use tabs only for a small number of related peer sections, not as a substitute for clear page hierarchy.
- Provide helpful empty states rather than unexplained blank areas.
- Make wide tables and layouts usable on smaller screens without hiding important information.

### Actions, Navigation, and Feedback
- Make the primary action visually clear and secondary actions less prominent.
- Make destructive actions explicit and request confirmation when warranted.
- Use `MatDialog` for focused modal tasks or confirmations; use `MatSnackBar` for brief feedback that users do not need to retain.
- Use menus for grouped contextual actions that need not remain visible.
- Follow the application's established toolbar and navigation pattern.
- Show suitable progress feedback for long-running operations and prevent duplicate submissions when appropriate.

## 4. Material APIs, Theming, and Styling
- Import only the Material components, directives, services, and providers needed by the feature; follow existing standalone/import conventions.
- Reuse shared UI components instead of creating duplicates.
- Verify unfamiliar APIs against Angular Material 21 documentation; do not assume older examples or deprecated APIs are compatible.
- Follow the configured Material theme and existing color, typography, spacing, and elevation conventions. Prefer supported theme APIs and tokens over hardcoded values or ad hoc overrides.
- Keep feature styles scoped. Avoid `::ng-deep`, excessive `!important`, and selectors that depend on Material's internal DOM or implementation-specific classes.
- Do not create a competing design system or use undocumented Material internals.

## 5. Forms, State, and API Integration
- Follow existing reactive or template-driven form conventions; prefer typed reactive forms for complex forms.
- Reuse validators where appropriate and keep client-side validation aligned with backend rules. Client-side validation is not a security boundary.
- Inspect existing services, schemas, and documentation instead of inventing endpoints, payloads, or response fields.
- Use `HttpClient` and typed services; follow existing interceptors, authentication, and environment configuration.
- Never hardcode credentials, tokens, or environment-specific API URLs.
- Use signals for local UI state and derived values; use RxJS for asynchronous streams and HTTP composition.
- Keep components focused on UI behavior and delegate reusable business logic and data access to services.
- Handle loading, success, empty, and error states explicitly. Do not silently swallow errors or display raw technical errors to users.
- For date fields, inspect the project's date adapter, locale, display format, timezone, and API serialization conventions. Apply required min/max dates and date filters; avoid unintended date shifts.

## 6. Accessibility and Responsive Design
- Use semantic HTML and Material controls according to their intended interaction patterns.
- Provide accessible names for icon-only buttons and controls without visible labels.
- Preserve keyboard operation, visible focus indicators, and appropriate focus management in dialogs and overlays.
- Use suitable table headers, labels, descriptions, and field-associated validation messages.
- Do not add redundant or incorrect ARIA roles or communicate status through color alone.
- Consider desktop, tablet, and mobile layouts. Verify accessibility when customizing default component behavior.

## 7. Testing and Validation
- Follow the repository's configured test framework and existing test conventions.
- Add or update tests when behavior changes, when requested, or when needed to verify correctness.
- Test user-visible behavior such as form validation, date selection, dialogs, table operations, loading states, and error handling where relevant.
- Prefer Angular-supported testing APIs and Angular Material component harnesses when available and appropriate.
- Do not weaken or delete tests merely to make them pass.
- Run relevant test, lint, type-check, and build commands available in the project. Report commands actually run and their results; explain anything that could not run.

## 8. Workflow and Definition of Done
1. Inspect relevant implementation, API contracts, theme configuration, and tests.
2. Identify the smallest change that satisfies the requirement and reuse existing patterns.
3. Implement with supported Angular 21 and Material 21 APIs.
4. Review for correctness, accessibility, responsiveness, and unintended changes.
5. Run relevant validation commands.
6. Summarize changed files, key decisions, validation results, and remaining limitations.

A change is complete when the requested behavior is implemented, relevant tests are updated when appropriate, applicable checks have been run or their limitations reported, and no unrelated changes or fabricated API assumptions remain.

## 9. Restrictions
- Do not bypass TypeScript errors, lint rules, or failing tests merely to finish a task.
- Do not replace Material components with custom controls without a clear reason and required approval.
- Do not perform broad refactoring when a focused change is sufficient.
- Ask for clarification when consequential ambiguity or architectural conflicts prevent a reliable implementation.

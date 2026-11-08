---
name: playwright
description: "Write, run, debug, and maintain reliable Playwright browser tests for the web application. Use when creating or modifying end-to-end tests, verifying UI behavior in a real browser, diagnosing browser-test failures, or adding visual regression coverage."
---

# Playwright Skill

## Scope

- Use Playwright Test with TypeScript for browser-level tests.
- Follow the repository's existing test structure, configuration, scripts, fixtures, and conventions. Inspect them before adding new patterns.
- Keep browser tests separate from Angular unit/component tests unless the repository already uses a different established structure.
- Leave overall workflow, required quality gates, repair-loop policy, and definition of done to `AGENTS.md`.
- Follow the Angular and Angular Material skills for application implementation and component-selection rules.

## Test design

- Test observable user behavior and meaningful outcomes, not implementation details.
- Cover the relevant happy path, validation, empty/loading states, and important failure paths for the feature under test.
- Prefer a small number of high-value, end-to-end user journeys over many brittle tests of incidental details.
- Make tests independent: each test must establish its own required state and must not rely on another test's order or side effects.
- Use deterministic data. Reset or seed state using the repository's supported test mechanisms.
- Avoid production services and shared mutable data in routine browser tests. Mock API responses when the purpose is to verify frontend behavior; retain appropriate integration coverage for important real API interactions.
- Do not add tests that merely confirm an element exists when the requirement is about behavior. Assert the result, such as the selected value, validation message, updated row, navigation destination, or saved state.

## Locators and assertions

- Prefer locators in this order when suitable:
  1. `getByRole()` with an accessible name.
  2. `getByLabel()` for form controls.
  3. `getByPlaceholder()` or `getByText()` when user-facing text is the clearest stable target.
  4. A deliberate `data-testid` for elements without a stable accessible/user-facing locator.
- Use exact matches where ambiguity is possible.
- Keep locators scoped to the relevant dialog, form, row, or component when repeated labels exist.
- Avoid selectors based on Angular internals, generated IDs, DOM depth, positional CSS selectors, or Angular Material's internal CSS classes and markup. Use them only when no stable user-facing alternative exists and explain why.
- Use Playwright's web-first assertions, such as `await expect(locator).toBeVisible()`, `toHaveText()`, `toHaveValue()`, and `toBeEnabled()`.
- Do not use fixed sleeps (`waitForTimeout`) to hide synchronization problems. Wait for a meaningful state, response, URL, or locator assertion.
- Do not weaken or remove an assertion solely to make a failing test pass. Confirm the requirement and diagnose the underlying cause first.

## Angular Material guidance

- Test components through their accessible behavior rather than their internal DOM structure.
- For date pickers, verify opening the calendar, selecting the intended date, the resulting field value, validation, and submission when relevant. Do not assume the calendar's accessible name or date format; inspect the actual app configuration and localization.
- For selects and autocompletes, verify the intended option can be selected and the resulting value is correct. For autocomplete, test filtering and invalid/free-text input when relevant to the requirement.
- For dialogs and menus, scope locators to the opened overlay and verify the expected action, close behavior, and focus behavior where relevant.
- For tables, verify meaningful sorting, filtering, pagination, row actions, empty states, and updated data as applicable.
- For forms, verify required fields, validation feedback, disabled states, keyboard interaction, and successful or rejected submission as applicable.
- Do not assume a component is correct merely because it renders. Verify the user-visible interaction and resulting state.
- Prefer accessible names and labels. If a component has no stable accessible locator, add a purposeful `data-testid` only when appropriate; avoid adding test IDs indiscriminately.

## Test structure and fixtures

- Reuse existing fixtures, authenticated states, helpers, and page objects where they improve clarity and reduce duplication.
- Keep abstractions small. Create a helper or page object when repeated workflows justify it; do not wrap every locator in a helper.
- Keep test setup separate from the assertions that describe the behavior under test.
- Use Playwright fixtures and `test.use()` for shared configuration instead of global mutable state.
- Use isolated browser contexts and unique test data when tests can change server-side state.
- Do not store credentials or secrets in source files. Use the repository's documented environment-variable or secret-management approach.
- Keep tests readable enough that another agent can infer the requirement from the test name and assertions.

## API and asynchronous behavior

- Use `page.route()` or the repository's existing API-mocking helpers when deterministic frontend-only behavior is required.
- Match API routes precisely enough that unrelated requests are not accidentally intercepted.
- When verifying a real request, wait for the relevant response or resulting UI state; do not rely on arbitrary delays.
- Assert both the visible outcome and important request details when the request contract is part of the requirement.
- Do not silently ignore failed requests or console errors. If a test captures them, distinguish known/intentional errors from unexpected failures.

## Visual regression

- Use screenshot assertions only for stable, high-value pages or components where visual regressions matter.
- Establish baselines in a consistent browser, operating system, font, viewport, locale, and timezone environment.
- Stabilize dynamic content, animations, timestamps, and asynchronous loading before capturing screenshots.
- Prefer a focused component or page screenshot over a large full-page screenshot when it gives a clearer signal.
- Review screenshot diffs before updating baselines. Update them only when the visual change is intentional and approved by the task requirements.
- Do not automatically accept every changed snapshot just to obtain a passing test.

## Debugging and diagnostics

- Reproduce failures with the narrowest relevant test before running the full suite.
- Use Playwright's HTML report, trace viewer, screenshots, and error context to identify the failure cause.
- Inspect browser console errors and failed network requests when relevant.
- Distinguish application defects, test defects, environment/configuration problems, and genuinely changed requirements.
- Fix the root cause. Avoid retries as a substitute for fixing flaky tests; use retries only where repository policy explicitly calls for them and investigate repeated failures.
- After changing a test, verify that it still detects the defect or behavior it was intended to cover.

## Commands

Use the package scripts and Playwright configuration already present in the repository. Common commands include:

```bash
npx playwright test
npx playwright test path/to/example.spec.ts
npx playwright test --ui
npx playwright test --debug
npx playwright show-report
```

Use the configured project/browser when running a targeted test. Do not assume the app's base URL, startup command, port, or authentication setup; read `playwright.config.ts` and repository documentation first.

## Test quality checklist

Before considering a browser test complete, confirm that:

- The test verifies the requested behavior and a meaningful result.
- Locators are stable and accessible where practical.
- Setup and test data are deterministic and isolated.
- Assertions use Playwright's auto-waiting behavior rather than fixed sleeps.
- The test does not depend on execution order or hidden external state.
- Failures provide useful diagnostic information.
- Visual baselines, if any, are reviewed rather than blindly regenerated.

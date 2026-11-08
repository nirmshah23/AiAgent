---
description: Design, implement, and review clear, accessible,
  high-quality healthcare web interfaces in Angular 21 and Angular
  Material 21. Use for new screens, redesigns, UI reviews, design-system
  decisions, responsive behavior, and visual regression work.
name: ui-ux-design
---

# UI/UX Design for Healthcare Applications

## Purpose and scope

This skill is the source of truth for product UX, visual design decisions, healthcare-specific presentation, and visual acceptance. It complements rather than duplicates:
- `.agents/skills/angular-core/SKILL.md` for Angular architecture and implementation conventions.
- `.agents/skills/angular-material/SKILL.md` for Material APIs, component selection, theming implementation, and technical accessibility conventions.
- `.agents/skills/playwright/skill.md` for browser-test setup and Playwright conventions.

Do not restate those skills' framework-specific instructions here. Consult them when implementing. This skill defines **what experience the interface should provide and how its visual quality is evaluated**.

Use the installed `material-design-3-ui` and `ui-ux-pro-max` skills as supporting references when available. They are not independent sources of truth.

### Decision precedence

1. Product requirements, user workflows, clinical/administrative correctness, privacy, and authorization.
2. Existing project architecture, established application patterns, and supported APIs.
3. The healthcare product and visual standards defined in this skill.
4. Relevant recommendations from Material Design 3 and UI/UX Pro Max.
5. General aesthetic preference.

Do not blindly copy generated styles. Resolve conflicts in favor of user tasks, healthcare data integrity, accessibility, and consistency. Avoid framework-specific implementation advice here when it is already covered by the Angular or Angular Material skills.

## Core operating principle

Do not treat "the page compiles" or "the components render" as UI
completion. The result must help the intended user complete their task
accurately, efficiently, and confidently.

Design in this order: 1. Understand users, goals, decisions, and risks.
2. Establish information architecture and page hierarchy. 3. Choose the
layout and navigation. 4. Define content, labels, and interaction
behavior. 5. Apply project design tokens and semantic Material
components. 6. Define loading, empty, error, success, permission, and
long-running states. 7. Check accessibility and responsive behavior. 8.
Implement. 9. Inspect the running interface with Playwright screenshots
and browser interactions. 10. Correct observed defects and repeat
review.

Do not begin by choosing colors, adding cards, or decorating a
screenshot.

## Required workflow for every screen or substantial UI change

### 1. Inspect before changing

-   Read `AGENTS.md` and relevant documentation.
-   Read the Angular, Angular Material, and Playwright skills as
    relevant.
-   Inspect the current route, component, shared shell, theme
    configuration, reusable components, API services, and tests.
-   Determine the actual user role and task: e.g. administrator, operational user, clinician, or data operator.
-   Verify API contracts and permissions. Do not design controls for
    unavailable actions or invent data.
-   Identify existing patterns to reuse and any usability problems that
    should be corrected.
-   For a redesign, capture a baseline screenshot before editing.

### 2. Plan the experience before coding

For a new or materially redesigned screen, briefly establish: - Primary
user and primary task. - Most important decision or outcome. - Primary
action and secondary actions. - Information that must be visible
immediately versus information that can be progressively disclosed. -
Main sections and their order. - Table/chart/filter/search needs. -
Important loading, empty, error, permission-denied, and success
states. - Responsive behavior and accessibility considerations.

If requirements are clear, make reasonable design decisions and proceed;
do not block progress with unnecessary questions. Ask only when a
consequential product decision cannot be inferred safely.

### 3. Implement against the approved experience

- Follow the project's Angular and Angular Material skills for framework, component, theming, and implementation conventions.
- Reuse the application's existing shell, navigation, design tokens, and shared components.
- Use realistic content lengths and data shapes. Avoid lorem ipsum and invented production values.
- Do not introduce a visual redesign unrelated to the requested feature.
- The design should be expressed through the existing component system, not through a parallel UI library or arbitrary one-off styling.

### 4. Verify the real browser UI

For user-visible changes: - Run the application using the repository's
documented commands and inspect the changed route in a real browser
using Playwright. - Capture screenshots at a consistent desktop viewport
and at least one narrower viewport appropriate to the feature. - Check
visual hierarchy, typography, alignment, spacing, content density,
clipping, horizontal overflow, responsive navigation, and
empty/error/loading states. - Exercise primary interactions, keyboard
navigation, form validation, and dialogs/menus where relevant. - Inspect
browser console errors and failed network requests. - Compare with
existing screenshots or the visual standards defined in this skill. Do not use a
screenshot as the only functional test. - Fix issues found and repeat
the check. Do not declare success after merely generating a
screenshot. - Do not automatically update visual baselines until the
visual difference has been reviewed and is intentional.

Never put real patient information, secrets, access tokens, or other
sensitive data into screenshots, logs, fixtures, or committed visual
baselines. Use synthetic or de-identified data.

## Healthcare application UX principles

This is a healthcare application, not a consumer wellness app. Prefer a calm, trustworthy, information-dense but
readable enterprise interface. Optimize for accurate review,
traceability, and completion of operational tasks.

### Information hierarchy

-   Make the page purpose obvious with a clear title and, when useful, a
    short contextual subtitle.
-   Place the primary task or decision near the top.
-   Use summary metrics only when they answer a real question and have a
    clear definition, period, and population.
-   Distinguish operational status from domain performance and
    from data freshness.
-   Show reporting period, tenant/context, data version, last-updated
    timestamp, and filters when they materially affect interpretation.
-   Put actionable exceptions and work requiring attention ahead of
    secondary reference information.
-   Use tables for detailed comparison and row-level work; use charts
    when they make a pattern easier to understand than a table.
-   Avoid repeating the same facts in cards, charts, and tables unless
    repetition supports a clear workflow.
-   Use progressive disclosure for advanced filters, technical metadata,
    and infrequent actions; do not hide critical warnings or
    patient-safety information.

### Healthcare data integrity and trust

-   Never invent clinical values, counts,
    clinical facts, or workflow statuses. Clearly identify mock/demo
    data.
-   Preserve the meaning of clinical and operational data. Do not relabel domain concepts for visual simplicity.
-   Distinguish "not calculated," "no data," "not applicable," "zero,"
    and "failed." They are not interchangeable.
-   Display data freshness and calculation status where users need them
    to assess reliability.
-   Where results can be stale or asynchronous, show when the result was
    calculated and whether a newer run is pending or failed.
-   Use plain language for user-facing errors; retain a traceable
    technical reference when useful, without exposing stack traces or
    secrets.
-   Confirm destructive or irreversible operations and explain their
    impact. Preserve auditability for sensitive operational actions.
-   Enforce authorization in the backend. Hiding a button is not an
    authorization control.
-   Keep tenant context unmistakable and never visually imply that data
    from different tenants is combined unless the product explicitly
    supports that behavior.
-   Do not expose patient identifiers or protected health information in
    dashboard summaries, URLs, browser logs, analytics, or screenshots
    unless required and authorized for the workflow.

### Healthcare status and color

-   Color must never be the sole signal for status. Pair it with text
    and/or a meaningful icon.
-   Reserve strong red for serious errors, failed operations, or
    genuinely critical exceptions; do not use it as routine decoration.
-   Use amber for attention/warning and green for confirmed
    positive/completed states only when those meanings are accurate.
-   Use neutral styling for routine metadata and inactive states.
-   Do not imply that a result is clinically safe, compliant, or
    officially certified solely through visual styling.
-   Keep status colors consistent across dashboard cards, tables,
    badges, charts, and detail pages.

### Tables and dense data

-   Make tables readable before making them compact.
-   Use clear column headings, consistent alignment, sufficient row
    height, and predictable number/date formatting.
-   Right-align numeric counts and rates where that improves comparison;
    align labels and descriptive text to the left.
-   Keep important identifiers and row actions discoverable without
    overcrowding every row.
-   Use server-side filtering, sorting, and pagination when required by
    data size and supported by the API.
-   Provide meaningful no-results and empty states, including how to
    change filters or start the next task.
-   Avoid tiny text, overly compressed rows, unexplained abbreviations,
    and tables that become unusable on smaller screens.
-   For wide tables, choose an intentional responsive strategy:
    horizontal scrolling with context preserved, column prioritization,
    or a dedicated detail view. Do not silently discard important data.

### Dashboards and analytics

-   A dashboard should answer: "What is the current state?", "What needs
    attention?", and "What can I do next?"
-   Prefer a small number of meaningful KPIs over a wall of metric
    cards.
-   Give each metric a label, value, and relevant context (period,
    population, trend, or definition).
-   Use charts only when the visual encoding is accurate and readable.
    Label axes, units, periods, and series.
-   Do not use decorative charts, 3D charts, arbitrary gradients, or
    color palettes that obscure comparisons.
-   Make chart colors consistent with the design system and accessible
    in contrast and non-color distinctions.
-   Provide a tabular or textual alternative for important chart values
    where feasible.
-   Separate patient distribution, domain performance, data ingestion,
    and execution health when they answer different questions; do not
    force unrelated categories into one visual group.
-   Prioritize exceptions and actionable worklists over decorative
    visualizations.
-   Make "refresh" behavior, data freshness, and asynchronous
    calculation status understandable.

### Forms and operational workflows

-   Group fields by the user's mental model and task sequence.
-   Use persistent labels; placeholders are examples or supplementary
    hints, not substitutes for labels.
-   Explain required fields and validation rules before users submit
    when possible.
-   Show validation near the affected field, preserve entered values
    after recoverable errors, and provide a clear correction path.
-   Use suitable input types, date controls, searchable selectors for
    large lists, and explicit units for numeric values.
-   Distinguish saving from submitting, publishing, executing, or
    finalizing.
-   Disable duplicate submission while a request is in progress and
    communicate progress for long-running operations.
-   For uploads and long-running processing, show accepted formats, limits,
    progress, completion summary, and actionable failures when those
    details are supported by the backend.
-   Ask for confirmation only when the action is destructive,
    consequential, or difficult to reverse; do not overuse confirmation
    dialogs.
-   Preserve keyboard focus and return focus appropriately after dialogs
    and overlays.

## Visual design rules

### Hierarchy and density

-   Each page should have one clear primary heading and a coherent
    section hierarchy.
-   Use spacing, typography, alignment, and restrained surface changes
    to express grouping before adding borders or cards.
-   Do not wrap every section in a card. Use a card only when it
    meaningfully groups independent content or supports an interaction.
-   Avoid excessive horizontal separators, nested cards, and repeated
    rounded containers.
-   Avoid large empty areas caused by arbitrary fixed widths or heights,
    as well as cramped areas caused by tiny fonts.
-   Use consistent page gutters, content widths, grid gaps, and section
    spacing.
-   Keep the primary action visually prominent; secondary and
    destructive actions must not compete with it.
-   Prefer clear text labels for important navigation. Icon-only actions
    need accessible names and should be used only when their meaning is
    familiar.

### Typography and readability

-   Use the project's typography tokens and a consistent type scale.
-   Body text and table text must remain comfortably readable at normal
    desktop zoom. Do not shrink text to fit more information.
-   Use weight and size to establish hierarchy; avoid using all-caps,
    excessive bolding, or low-contrast muted text for important content.
-   Use tabular numerals for aligned numeric metrics where supported.
-   Keep line length reasonable for explanatory text and use concise,
    meaningful labels.
-   Check readability at 100% zoom and under browser text scaling.

### Color, surfaces, shape, and elevation

-   Use semantic Material 3 color roles and project theme tokens rather
    than arbitrary hard-coded values.
-   Keep primary color for key actions and selected/active states; do
    not color every heading, icon, or container with the primary color.
-   Use surface roles and subtle borders to create hierarchy. Reserve
    elevation/shadows for elements that need to appear above surrounding
    content.
-   Use a restrained, consistent shape scale. Do not turn every button,
    field, card, and panel into a pill.
-   Use gradients and decorative imagery only when they support the
    product identity or task; they are not substitutes for hierarchy.
-   Maintain consistent light/dark theme behavior if both themes are
    supported by the project.

### Navigation

-   Organize navigation around stable user tasks and domain areas, not a
    long line of unrelated text links.
-   Keep primary navigation distinct from page-level tabs, filters, and
    contextual actions.
-   Show the active location clearly and provide meaningful page titles
    and breadcrumbs when useful.
-   Use a responsive navigation pattern appropriate to the viewport and
    existing application shell.
-   Do not introduce a sidebar or restructure global navigation without
    checking existing product requirements and approved shell
    conventions.
-   Keep tenant selection and tenant context easy to identify without
    letting them overwhelm the page.

### Responsive behavior

-   Design for the actual web application, including wide desktop
    workspaces and smaller laptop/tablet widths.
-   Reflow layouts intentionally; do not merely scale down desktop
    content.
-   Define sensible minimum widths and wrapping behavior for KPI grids,
    filters, navigation, dialogs, and tables.
-   Avoid fixed pixel widths for major layout regions unless a genuine
    constraint requires them.
-   Check for horizontal page overflow, clipped actions, overlapping
    labels, and inaccessible off-screen controls.
-   Ensure dialogs fit smaller viewports and remain usable with keyboard
    and assistive technology.

## Accessibility as a design requirement

Accessibility implementation details are governed by the Angular Material skill. From a UX and visual-design perspective:

- Do not communicate status, requiredness, errors, or chart categories through color alone; use clear labels and/or meaningful symbols.
- Maintain readable contrast and text sizing; verify against WCAG 2.2 AA rather than guessing.
- Ensure focus states, text scaling, and interactive target spacing remain visually clear in the actual interface.
- Avoid unnecessary motion and respect reduced-motion preferences.
- Do not claim full accessibility compliance without evidence from review and testing.

## Motion and feedback

-   Motion must communicate state change, hierarchy, or continuity;
    never add animation merely to make a page feel modern.
-   Respect `prefers-reduced-motion`.
-   Use loading indicators appropriate to the wait: inline progress for
    local actions, skeletons only when they help communicate page
    structure, and progress feedback for long-running jobs.
-   Avoid layout shifts while data loads.
-   Use snackbars for brief confirmation, not as the only place where
    important errors or validation details appear.
-   Make pending, success, partial success, failure, cancellation, and
    retry states distinct when the workflow supports them.

## Avoid these anti-patterns

Do not: - Produce a page that is technically functional but visually
unreviewed. - Use tiny fonts or overly dense tables to fit everything
above the fold. - Put every section in a rounded card. - Make all
navigation items look like small inline hyperlinks. - Use arbitrary
colors, inconsistent spacing, or unrelated component styles. - Fill a
dashboard with cards without clear decision value. - Use charts as
decoration or show numbers without definitions/context. - Hide important
actions or errors behind hover-only interactions. - Use color as the
only status indicator. - Use placeholder text instead of field labels. -
Create fake data or silently omit a workflow because an endpoint is
missing. - mark screenshots as approved without inspecting them. -
Blindly accept changed visual snapshots. - Include real PHI,
credentials, tokens, or secrets in test artifacts. - Change the global
shell or design system during a narrow feature task unless necessary and
explicitly reported.

## Forms, tables, and workflows

-   Persistent field labels; helper text for ambiguous requirements;
    validation close to the field.
-   Primary action must be clear, with secondary actions less prominent
    and destructive actions separated.
-   Tables must have readable headings, adequate row height, aligned
    values, clear sorting/filtering/pagination, and a defined
    narrow-screen strategy.
-   Empty states should explain what is absent and the next useful
    action.
-   Long-running uploads and long-running operations need clear progress and
    final status.
-   Avoid confirmation dialogs for routine reversible actions; use them
    for destructive or consequential actions.

## Responsive behavior

Treat breakpoints as structural changes, not just scaling. Preserve
access to primary actions, tenant context, table operations, and
important data. At narrow widths, reflow summary grids, stack filters
when needed, and use a deliberate strategy for wide tables. Test actual
breakpoints in the running app; do not rely solely on a CSS breakpoint
guess.

## Accessibility and privacy

-   Target WCAG 2.2 AA practices for contrast, keyboard use, focus
    visibility, semantic structure, labels, and non-color status
    communication.
-   Support keyboard operation for navigation, menus, dialogs, tables,
    and forms.
-   Respect reduced motion.
-   Do not include real PHI, credentials, tokens, or sensitive tenant
    data in screenshots, fixtures, logs, or visual baselines.
-   Make tenant context clear and do not imply cross-tenant aggregation
    unless explicitly supported.
-   Visual presentation does not replace server-side authorization.

## Reusable patterns

Build or reuse shared components only when they represent stable product
patterns, for example: - Page header with title, context, and primary
action. - Filter/search toolbar. - KPI summary that includes label,
value, and context. - Status label with text and icon. - Data table
wrapper with loading, empty, error, and pagination states. - Async
job/execution status panel. - Empty state with explanation and a
supported next action. - Confirm-action dialog for consequential
changes.

Avoid creating generic abstractions for one-off elements that have no
demonstrated reuse.

## Quality gate

Every substantial screen change must be inspected in a real browser. Use
Playwright to capture and review screenshots at the project's standard
desktop viewport and a narrower viewport. Verify primary interactions,
keyboard focus, loading/empty/error states, visual consistency, and
overflow. Review screenshot differences before updating baselines.

A passing build is necessary but not sufficient for UI acceptance.

## UI review checklist

Before reporting completion, review the changed screen against all
applicable items:

1.  **Task clarity:** Is the user's primary task obvious within a few
    seconds?
2.  **Hierarchy:** Is there a clear page title, section order, and
    primary action?
3.  **Readability:** Are labels, body text, metrics, and tables
    comfortably readable?
4.  **Density:** Is information grouped without excessive cards,
    separators, or empty space?
5.  **Meaning:** Do all metrics, statuses, charts, and labels preserve
    business meaning?
6.  **Consistency:** Are navigation, typography, spacing, colors,
    shapes, and controls consistent?
7.  **States:** Are loading, empty, error, success, disabled, and
    permission states handled where relevant?
8.  **Accessibility:** Are keyboard use, focus, labels, contrast, and
    non-color status cues adequate?
9.  **Responsiveness:** Does the layout work at the tested viewport
    sizes without clipping or accidental overflow?
10. **Healthcare trust:** Is tenant context clear and is patient data
    protected in the UI and artifacts?
11. **Functional behavior:** Do actions work and show a meaningful
    outcome?
12. **Visual verification:** Were screenshots captured, inspected, and
    corrected rather than merely generated?

Report any unchecked item and why it could not be verified. Never claim
visual acceptance solely because the build or tests pass.

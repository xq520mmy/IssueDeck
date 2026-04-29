# Design System - IssueDeck

## Product Context

- **What this is:** IssueDeck is a lightweight, self-hosted development tracker for small teams and AI coding workflows. It tracks work items, releases, relationships, search, and migrations across multiple projects through REST, MCP, and a web dashboard.
- **Who it's for:** Builders who live close to code: solo developers, small engineering teams, Claude Code / MCP users, and teams that want structure without adopting heavyweight project management software.
- **Space/industry:** Developer tools, issue tracking, self-hosted project management, AI coding operations.
- **Project type:** Open-source developer tool with an internal dashboard and technical documentation.
- **Memorable thing:** Lighter than Jira. More stable than Markdown.

## Aesthetic Direction

- **Direction:** Industrial Developer Ledger.
- **Decoration level:** Intentional. Use grid lines, compact panels, status marks, monospace identifiers, and ledger-like structure. Avoid decorative illustrations, gradient blobs, and generic SaaS ornament.
- **Mood:** Serious, fast, local, and trustworthy. The product should feel like an engineering logbook that can survive daily work, migrations, and release history.
- **Positioning:** IssueDeck should not try to look like a smaller Linear or a smaller Plane. It should own the narrow lane between loose Markdown notes and heavyweight issue trackers.
- **Reference landscape:** Linear for speed and AI-workflow confidence; Plane for open-source self-hosting; GitHub Issues for proximity to code and Markdown; Jira/YouTrack/OpenProject as examples of the heavyweight workflow category IssueDeck deliberately avoids.

## Typography

- **Display/Hero:** General Sans. Use for product name, page titles, major section headings, and key metrics. It is clean and modern without collapsing into the default Inter-like SaaS look.
- **Body:** Source Sans 3. Use for descriptions, documentation, labels, forms, and longer item bodies. It reads well at small sizes and keeps the UI from feeling brittle.
- **UI/Labels:** Source Sans 3 with 600-700 weight for labels, buttons, badges, and navigation.
- **Data/Tables:** IBM Plex Mono with tabular numbers. Use for `FEAT-0001`, versions, commit SHAs, cursors, timestamps, API paths, and compact metadata.
- **Code:** JetBrains Mono. Use for command blocks, config examples, CLI snippets, and code-like content.
- **Loading:** Prefer self-hosted font assets for production/offline deployments. During preview or development, Google Fonts or Bunny Fonts are acceptable. If self-hosting, place fonts under the dashboard static assets and define `@font-face` in one shared stylesheet.

## Type Scale

- **Page title:** 28px / 34px, General Sans 700.
- **Dashboard hero title:** 48-68px / 0.96, General Sans 700, only on marketing or preview surfaces. Do not use hero-scale type inside compact app panels.
- **Section heading:** 15-18px / 24px, General Sans 700.
- **Body:** 15-16px / 22-24px, Source Sans 3 400.
- **Compact body:** 13-14px / 18-20px, Source Sans 3 400-500.
- **Metadata:** 11-12px / 16px, IBM Plex Mono or Source Sans 3 700 uppercase with modest tracking.
- **Code:** 13px / 20px, JetBrains Mono 400.

## Color

- **Approach:** Restrained plus semantic. Color is used to communicate state, release, and action. It should not decorate the page for its own sake.
- **Primary:** `#0F766E` - ink-teal for active navigation, primary actions, selected states, and important focus lines.
- **Primary dark/light mode:** In dark mode, use `#2DD4BF` for active states and `#99F6E4` for high-emphasis text on dark surfaces.
- **Accent / Ship:** `#B45309` - amber for release, version, shipped state, and warnings that are not errors.
- **Background:** `#F7F7F2` - warm off-white, chosen to feel like a ledger rather than a generic gray dashboard.
- **Surface:** `#FFFFFF` - primary panels and forms.
- **Surface Alt:** `#FBFCF8` - table headers, filter strips, secondary panels.
- **Ink:** `#161A1D` - primary text.
- **Ink Soft:** `#394046` - secondary text.
- **Muted:** `#687076` - timestamps, helper text, inactive labels.
- **Line:** `#D8DED8` - standard borders.
- **Line Strong:** `#AEB8AF` - active separators, controls, and stronger structure.
- **Success:** `#15803D`.
- **Warning:** `#B45309`.
- **Error:** `#B42318`.
- **Info:** `#2563EB`.

## Dark Mode

- **Background:** `#0C0F0E`.
- **Panel:** `#141817`.
- **Panel Alt:** `#101412`.
- **Line:** `#27302D`.
- **Line Strong:** `#3B4943`.
- **Ink:** `#E7ECE8`.
- **Ink Soft:** `#C2CBC5`.
- **Muted:** `#8C9891`.
- **Strategy:** Do not merely invert colors. Dark mode should feel like a low-glare control room: slightly green-black surfaces, restrained contrast, and saturated status colors only where they carry meaning.

## Spacing

- **Base unit:** 4px.
- **Density:** Compact but breathable.
- **Scale:** 2xs 2px, xs 4px, sm 8px, md 16px, lg 24px, xl 32px, 2xl 48px, 3xl 64px.
- **Buttons:** 32-36px tall for normal app actions; 40px only for prominent empty-state or onboarding actions.
- **Table rows:** 40-48px for dense lists; 56px when descriptions/previews are shown.
- **Cards/panels:** 12-16px internal padding for dense app panels; 20-24px for top-level overview panels.
- **Kanban cards:** 96-128px preferred height. Content should truncate rather than expand the board unpredictably.

## Layout

- **Approach:** Grid-disciplined.
- **Primary app frame:** Left sidebar, top utility bar, central work area. Optional right detail panel on wide screens.
- **Dashboard overview:** Metrics first, then recent activity and charts. Avoid marketing-style hero sections inside the actual app.
- **List view:** Dense table/list hybrid. Local ID and status must be visible without opening the detail view.
- **Detail view:** Main content plus metadata blocks and timeline/release history. Relationships should feel like dependencies, not comments.
- **Kanban view:** Compact columns with stable card dimensions. Dragging should not resize surrounding content.
- **Max content width:** `1280px` for app views unless a table needs full width.
- **Grid:** 12-column conceptual grid on desktop; one-column stacked layout below tablet width.
- **Border radius:** sm 4px, md 6px, lg 8px, full 9999px only for pills/badges. Do not use large bubbly radii.
- **Cards:** Use cards only for repeated items, dashboards panels, modals, and framed tools. Do not nest cards inside cards.

## Components

- **Navigation:** Active route uses a left inset line or strong border, not a large filled pill. Counts use muted monospace or compact numeric badges.
- **Badges:** Kind badges are squared pills with low-saturation backgrounds. Status badges use semantic colors and optionally a small dot.
- **IDs and versions:** Always monospace. IDs are first-class scan anchors.
- **Tables/lists:** Favor horizontal structure, thin dividers, hover rows, and fixed columns. Dynamic text truncates with clear detail access.
- **Buttons:** Primary action is solid teal. Secondary actions are outlined. Destructive actions use text or outline until confirmed.
- **Forms:** Labels above fields, compact helper text, validation messages close to the field. Avoid large blank forms that feel like enterprise admin software.
- **Toasts:** Short, functional, bottom-right. Do not use motion-heavy notification choreography.
- **Charts:** Use restrained colors and thin grid lines. Charts should explain project state, not decorate the overview.
- **Command/code blocks:** Dark terminal surface, JetBrains Mono, clear prompt line. This is a brand asset for IssueDeck.

## Motion

- **Approach:** Minimal-functional.
- **Easing:** enter `ease-out`, exit `ease-in`, move `ease-in-out`.
- **Duration:** micro 50-100ms, short 150-220ms, medium 250-350ms.
- **Use motion for:** HTMX swaps, sidebar open/close, row hover, drag/drop, toast entrance, theme transitions.
- **Avoid motion for:** Decorative page entrances, scroll choreography, bouncing interactions, or anything that slows repeated work.

## Writing And Tone

- **Product voice:** Builder-to-builder. Direct, practical, precise.
- **Tagline:** Lighter than Jira. More stable than Markdown.
- **Avoid:** Corporate transformation language, vague productivity claims, and "all-in-one" positioning.
- **Prefer:** Specific workflow language: MCP tools, Markdown export, SQLite, release records, relationships, branches, commits, self-hosting.

## Safe Choices

- Keep familiar issue-tracker views: list, kanban, detail, search, and project overview.
- Keep status colors and kind badges because users need to scan state quickly.
- Keep Markdown and code-adjacent language prominent because developer trust comes from staying close to code.

## Deliberate Risks

- Use a ledger/control-room visual language instead of the common polished SaaS card dashboard.
- Use ink-teal and amber instead of the usual blue/purple AI-tool palette.
- Make density a feature. IssueDeck should feel efficient for daily work, not spacious for screenshots.

## Preview Artifact

- Initial preview was generated during design exploration; regenerate locally when needed.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-28 | Positioning: "Lighter than Jira. More stable than Markdown." | Competitive research showed Linear owns polished AI product development, Plane owns open-source Jira replacement, and GitHub Issues owns code-adjacent simplicity. IssueDeck should occupy the lightweight structured ledger space. |
| 2026-04-28 | Aesthetic: Industrial Developer Ledger | Matches self-hosted developer-tool positioning and gives the dashboard a memorable product face without adding decorative noise. |
| 2026-04-28 | Typography: General Sans, Source Sans 3, IBM Plex Mono, JetBrains Mono | Gives the product a distinct UI face, readable long-form content, and strong code/data treatment. |
| 2026-04-28 | Palette: warm ledger background with ink-teal primary and amber release accent | Avoids generic blue/purple SaaS language while reinforcing stability, state, and release history. |

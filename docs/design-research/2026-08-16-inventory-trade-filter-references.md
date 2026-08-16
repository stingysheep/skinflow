# UI Reference Brief

## Context

- Feature: Inventory trade-status filtering and availability column
- Primary user task: Narrow recorded holdings to items that can be listed now or are still cooling down, then select quantities for a listing preview.
- Platform and target viewport: Windows desktop WebView, 1440 x 900 primary viewport, 1100px minimum width.
- Existing design constraints: Dense operational table, restrained light palette, IBM Plex typography, green positive and amber warning tokens already defined.
- Must preserve: Current command bar, row density, item imagery, price and quantity columns, listing workflow, and no nested cards.
- Must avoid: Keeping non-matching rows with a zero numerator, adding decorative dashboard cards, or using color without text/count reinforcement.

## Evidence

| Source | Type | Link | Observed interface | Transferable principle | Do not copy |
| --- | --- | --- | --- | --- | --- |
| Steam Community Market | Shipped product | https://steamcommunity.com/market/ | Search and market actions are presented as a compact work surface tied directly to inventory objects. | Keep status treatment close to the tradable object and preserve Steam-domain imagery. | Steam branding, dark theme, or exact market layout. |
| GitHub Issues | Shipped product | https://github.com/microsoft/vscode/issues | Filters remove unrelated issues while labels explain the state of rows that remain. | Filtering changes membership; labels do not substitute for filtering. | GitHub label shapes, colors, or repository chrome. |
| Shopify Polaris | Official product framework | https://shopify.dev/docs/api/polaris | Status feedback uses semantic tone with concise text and avoids large colored surfaces. | Use low-chroma positive/warning surfaces plus readable text. | Shopify component code or brand-specific green. |
| Linear Filters | Shipped product documentation | https://linear.app/docs/filters | Filters narrow a current view to only work relevant to the selected property. | Apply the secondary filter even when a primary saved/recorded scope is active. | Linear navigation, shortcuts, or translucent visual style. |
| Stripe Dashboard | Shipped product documentation | https://docs.stripe.com/dashboard/basics | Dense financial tables keep status scannable and secondary to the primary amount/object fields. | Make the number primary and the state explanation secondary. | Stripe purple, navigation, or payment terminology. |
| Microsoft Fluent Badge | Official product design system | https://fluent2.microsoft.design/components/web/react/core/badge/usage | Badges encode compact status with semantic color and text together. | Never rely on hue alone; pair color with a label or quantity. | Fluent component geometry or token names. |
| Atlassian Lozenge | Official shipped-product design system | https://atlassian.design/components/lozenge/ | Lozenges represent stable workflow states with restrained fills and short labels. | Reserve colored capsules for categorical state, not every numeric value. | Atlassian lozenge casing or exact palette. |
| Datadog Facets | Shipped product documentation | https://docs.datadoghq.com/logs/explorer/facets/ | Facet filters and result counts stay synchronized in dense operational views. | The visible group count must reflect filtered rows, not unfiltered data. | Datadog purple, sidebar layout, or telemetry terminology. |

## Extracted Decisions

- Primary work surface: Preserve the existing full-width inventory table.
- Information hierarchy: Item identity first, tradable count second, cooldown explanation third.
- Navigation model: Primary inventory scope and secondary trade status remain independent, composable filters.
- Data density and alignment: Keep the 150px status column and monospace numeric alignment.
- Typography rhythm: 14px primary count, 13px semantic annotation, no larger type.
- Material and separation treatment: Existing row borders; semantic color appears only inside the status cell.
- Color semantics: Green means listable now; amber means present but not currently tradable.
- Feedback and motion: Filtering updates rows immediately without animation or layout shift.

## Visual Directions

### Direction A - Ratio With State Line

- Layout skeleton: Two-line cell with a colored `tradable / available` ratio above a short semantic state line.
- Evidence used: Stripe numeric hierarchy, Shopify semantic tone, Linear filter membership.
- First-view hierarchy: Ratio first, then `全部可交易` or `19 件冷却中`.
- Design memory point: A calm green/amber state rail at the left of the cell.
- Anti-template result: Pass. It changes only the domain-specific status cell and preserves the operational table.

### Direction B - Availability Meter

- Layout skeleton: Numeric ratio above a narrow proportional green/amber meter with a compact legend.
- Evidence used: Datadog quantitative facets, Steam inventory quantities, Fluent semantic reinforcement.
- First-view hierarchy: Ratio, distribution bar, then labels.
- Design memory point: A 4px split meter that shows mixed availability at a glance.
- Anti-template result: Pass. The meter is meaningful inventory data, not decorative progress.

### Direction C - Paired State Counts

- Layout skeleton: Two compact inline state blocks, one green `可交易 26` and one amber `冷却 0`.
- Evidence used: GitHub row labels, Atlassian lozenges, Shopify badge tones.
- First-view hierarchy: Categorical counts rather than a ratio.
- Design memory point: Stable paired labels keep both states visible in every row.
- Anti-template result: Pass with stated compromise. It is clearest but slightly denser than the current table.

## Approval

- Selected direction: Direction B - Availability Meter
- Approved at: 2026-08-16
- Approved deviations: Green grows from the left, amber grows from the right, and both segments fill the full bar proportionally. Hover or keyboard focus expands cooldown batches below the bar; fully tradable groups have no expansion.

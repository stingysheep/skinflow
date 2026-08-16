# UI Reference Brief

## Context

- Feature: Listings records grouping, bulk selection, cancellation, and status visibility.
- Primary user task: Reconcile Steam listing state, scan identical items as one group,
  select every cancellable child in that group, and cancel with a clear scope.
- Platform and target viewport: Skinflow desktop WebView, 1440px primary viewport,
  1100px minimum application width.
- Existing design constraints: IBM Plex typography, continuous work surfaces, compact
  operational tables, square thumbnails, semantic status colors, 3-5px radii.
- Must preserve: Existing header and command bar, current Listings API actions,
  per-asset status and Steam listing identifier, keyboard access, explicit cancellation
  confirmation.
- Must avoid: Card dashboards, hidden bulk-action scope, treating group rows as real
  listing records, or mixing listed inventory with trade cooldown.

## Evidence

| Source | Type | Link | Observed interface | Transferable principle | Do not copy |
| --- | --- | --- | --- | --- | --- |
| AWS Cloudscape grouped resources | Official design system | https://cloudscape.design/patterns/resource-management/view/table-with-grouped-resources/ | Expandable group rows expose aggregate values and counters; selecting a group selects every eligible resource even when collapsed | Put group checkbox, eligible/selected count, and aggregates on the parent row; selection scope must include hidden children | AWS styling, wording, or layout chrome |
| IBM Carbon data table | Official design system | https://carbondesignsystem.com/components/data-table/usage/ | Selection activates a batch-action bar; expandable rows progressively disclose details | Replace the passive command strip with explicit selected-count context during bulk mode; keep child details inside the table rhythm | Carbon component appearance or iconography |
| W3C ARIA treegrid example | Standards example | https://www.w3.org/WAI/ARIA/apg/patterns/treegrid/examples/treegrid-1/ | Parent rows expose `aria-expanded`; keyboard focus and expansion remain predictable | Use a real button for disclosure, preserve checkbox independence, and support Enter/Space expansion | The email example's content and visual styling |
| Steam Community Market | Shipped product | https://steamcommunity.com/market/ | My listings and market history are separate operational views; price and quantity stay compact and scan-first | Keep listing status, Steam identity, price, and quantity as first-class columns rather than burying them in prose | Steam branding, dark palette, or navigation |
| Jira Cloud bulk operations | Shipped product documentation | https://support.atlassian.com/jira-software-cloud/docs/edit-multiple-issues-at-the-same-time/ | Users first select a bounded set, then review and confirm the operation; constraints are explicit | Cancellation must state exactly how many eligible asset listings will be affected and require confirmation | Jira workflow steps or terminology |
| GitLab issue bulk editing | Shipped product documentation | https://docs.gitlab.com/user/project/issues/managing_issues/#bulk-edit-issues | Row checkboxes activate a contextual editing surface while the dense list remains visible | Keep the grouped list visible during bulk mode and disable only ineligible child rows, with a visible reason/status | GitLab sidebar, branding, or field layout |

## Extracted Decisions

- Primary work surface: A dense listing record surface grouped by market hash name,
  with asset rows disclosed on demand.
- Information hierarchy: Group name and image, eligible/total count, aggregate cost and
  listed price, status mix, then per-asset Steam details.
- Navigation model: Single page; group disclosure remains inline. No detail route.
- Data density and alignment: Stable grid columns, monospaced numeric values, 44-56px
  parent rows, 38-44px child rows.
- Typography rhythm: Existing 13-14px table typography; group names use 14px semibold;
  metadata stays 12-13px and muted.
- Material and separation treatment: Continuous white table surface, header bands,
  one-pixel borders, subtle selected background. No nested cards.
- Color semantics: Green sold/success, blue active/listed, amber pending confirmation,
  red failed/cancel action, gray cancelled.
- Feedback and motion: Disclosure rotates the chevron and reveals children without
  moving column widths; bulk mode changes the command bar without resizing the page.

## Visual Directions

### Direction A: Aggregate Tree Table

- Layout skeleton: One full-width table; each item group is a selectable expandable row;
  child assets sit directly below in the same columns.
- Evidence used: Cloudscape grouped resources, Carbon expansion/batch actions, W3C
  treegrid, existing Skinflow transaction history.
- First-view hierarchy: Bulk command bar, column headers, aggregate group rows, one open
  group showing per-asset cancellation eligibility.
- Design memory point: A narrow blue status rail on active group rows and a parent
  checkbox with `selected / eligible` count.
- Anti-template result: Pass. The first view is unmistakably a listing reconciliation
  tree table, not a generic dashboard.

### Direction B: Status Bands

- Layout skeleton: Continuous vertical bands for Active, Pending, and Closed; identical
  items group inside each band and expand in place.
- Evidence used: Steam separation of listings/history, Jira bounded bulk operations,
  Carbon contextual batch actions.
- First-view hierarchy: Status totals, active band, grouped item rows, then pending and
  closed summaries.
- Design memory point: Status is the top-level navigation and each band carries its own
  selection counter.
- Anti-template result: Pass with stated compromise. Fast for status triage, but one
  item type can appear in more than one band.

### Direction C: Reconciliation Split View

- Layout skeleton: Compact grouped list on the left and a fixed asset inspector on the
  right with child checkboxes, Steam IDs, and cancellation scope.
- Evidence used: GitLab contextual edit surface, Steam listing identity, Jira review and
  confirmation.
- First-view hierarchy: Group list and status mix on the left; selected group assets and
  action controls on the right.
- Design memory point: The selected group becomes a persistent reconciliation queue in
  the inspector.
- Anti-template result: Pass. The split view is task-specific and avoids summary cards,
  though it shows fewer groups at once.

## Approval

- Selected direction: Direction B, Status Bands.
- Approved at: 2026-08-17.
- Approved deviations: Status is the parent level (Active, Sold, Cancelled/Failed),
  item type is the second expandable level, and individual assets are the third level.
  Every level displays a selection checkbox; parent selection applies only to eligible
  cancellable descendants. Item rows retain aggregate cost, listed price, proceeds,
  ratio, and an active-versus-sold progress bar.

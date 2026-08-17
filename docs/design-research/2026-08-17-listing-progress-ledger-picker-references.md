# UI Reference Brief

## Context

- Feature: Background Steam listing submission progress and inventory-backed ledger entry selection.
- Primary user task: Confirm a listing once, continue using any page while submission advances, and record a purchase or sale by selecting a known item instead of retyping its name.
- Platform and target viewport: Skinflow desktop WebView, 1440px primary viewport, 1100px minimum application width.
- Existing design constraints: Dense operational tables, IBM Plex typography, light workspace, restrained radii, semantic status colors, and a shared modal/notification layer.
- Must preserve: Steam mobile-confirmation as a separate phase, persisted listing request state, current FIFO ledger rules, keyboard access, and existing feature navigation.
- Must avoid: Blocking the preview until every Steam request finishes, claiming success before Steam verifies the listing, card-dashboard composition, hidden background work, or coupling purchase recording to inventory synchronization rules.

## Evidence

| Source | Type | Link | Observed interface | Transferable principle | Do not copy |
| --- | --- | --- | --- | --- | --- |
| AWS Cloudscape loading and refreshing | Official product design system | https://cloudscape.design/patterns/general/loading-and-refreshing/ | Long refreshes keep the current data surface visible, communicate automatic refresh, and preserve actions while work continues | Keep Skinflow usable during submission and update task state in place instead of reopening the preview | AWS console chrome or terminology |
| GitHub Primer ProgressBar | Official product design system | https://primer.style/product/components/progress-bar/ | A labeled determinate bar pairs completion percentage with concise task context | Show completed/total assets beside one stable bar; do not rely on animation alone | GitHub colors, component markup, or branding |
| Atlassian Flag | Official product design system | https://atlassian.design/components/flag/ | Global flags stack in a predictable viewport location and distinguish informational, success, and error outcomes | Use one cross-page task surface that changes from progress to a final result | Atlassian styling or copy |
| IBM Carbon Notification | Official product design system | https://carbondesignsystem.com/components/notification/usage/ | Toast, inline, actionable, and callout variants have different persistence and action expectations | Keep active progress persistent; auto-dismiss only the terminal success message and let failures remain actionable | Carbon visual appearance |
| Shopify Choice List | Official product documentation | https://shopify.dev/docs/api/app-home/web-components/forms/choice-list | Defined sets use explicit single-selection controls with labels, help text, and validation | Treat inventory items as a visible selectable set, with search as a supplement | Shopify merchant terminology or component styling |
| Microsoft Fluent 2 Combobox | Official product design system | https://fluent2.microsoft.design/components/web/react/core/combobox/usage | Searchable selection supports keyboard navigation and separates the chosen value from the query | Preserve a searchable fallback while making the selected inventory item unmistakable | Fluent component skin or navigation |
| Steam Community Market | Shipped product | https://steamcommunity.com/market/ | Item thumbnail, market name, price, quantity, active listings, and history are kept scan-first | Keep Steam item identity and count visible in progress and ledger selection | Steam branding, dark palette, or market layout |
| Material 3 Snackbar | Official product design system | https://m3.material.io/components/snackbar/guidelines | Temporary messages stay peripheral to the current task and use concise result language | Keep completion feedback above page content without stealing focus | Material shape, elevation, or motion |

## Extracted Decisions

- Primary work surface: The current page remains dominant; listing progress lives in a global peripheral layer and ledger entry uses one enlarged focused modal.
- Information hierarchy: Listing item group and asset count, submission phase, completed/total, progress bar, mobile-confirmation count, then final result. Ledger selection prioritizes thumbnail, Chinese name, market hash name, available quantity, then numeric form fields.
- Navigation model: No new route. Preview closes immediately after the API accepts a durable request; progress follows the user across routes.
- Data density and alignment: A 360-420px progress surface and a 960-1100px ledger dialog; compact 44-56px item rows; numeric values use tabular alignment.
- Typography rhythm: Existing 12-14px operational labels, 16-18px dialog title, concise one-line phase text.
- Material and separation treatment: Continuous list surfaces, one-pixel dividers, one focused modal, and no nested cards.
- Color semantics: Blue means submitting, amber means awaiting mobile confirmation, green means active/success, red means failed, neutral gray means queued.
- Feedback and motion: Determinate width changes only; reduced-motion users receive no entrance or progress animation. Progress remains until terminal state.

## Visual Directions

### Direction A: Corner Task Tray + Split Ledger

- Layout skeleton: A compact persistent task tray floats at the lower-right of any page. The enlarged ledger modal splits into a searchable inventory list on the left and the entry form on the right.
- Evidence used: Atlassian Flag, Carbon Notification, Steam item identity, Fluent Combobox.
- First-view hierarchy: Existing page, active listing task, then selected inventory item and form values side by side.
- Design memory point: One task tile changes color and phase in place; the ledger dialog behaves like a small workbench.
- Anti-template result: Pass. Both surfaces are task-specific and leave the operational page intact.

### Direction B: Activity Rail + Horizontal Item Shelf

- Layout skeleton: A fixed right activity rail hosts background and completed tasks. The ledger modal uses a horizontal inventory shelf across the top with a full-width form below.
- Evidence used: Cloudscape continuous refresh, Primer ProgressBar, Shopify Choice List.
- First-view hierarchy: Page content narrows to expose the activity rail; item choice precedes all ledger fields in a left-to-right sequence.
- Design memory point: Background work becomes a small queue with explicit stages and recent completion history.
- Anti-template result: Pass with stated compromise. Excellent for multiple concurrent tasks, but permanently reserves horizontal space while active.

### Direction C: Global Task Strip + Inventory Table

- Layout skeleton: A thin full-width task strip appears below navigation. The ledger modal is dominated by a compact inventory table, with a sticky form and actions below it.
- Evidence used: Cloudscape loading, Primer ProgressBar, Steam market lists, Material Snackbar.
- First-view hierarchy: Global submission state first, then a scan-dense item table, then ledger values.
- Design memory point: The submission behaves like an application-wide status line and selection behaves like a miniature inventory register.
- Anti-template result: Pass. The skeleton is a status strip plus a dense selector, not a dashboard.

## Approval

- Selected direction: Direction A - Corner Task Tray + Split Ledger.
- Approved at: 2026-08-17 (user selected “a”).
- Approved deviations: The task tray is global and persists until terminal state; the purchase picker reads current inventory groups while the ledger FIFO and sale rules remain unchanged.

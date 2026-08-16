# UI Reference Brief

## Context

- Feature: Edit the current holding average cost and remove the remaining open holding.
- Primary user task: Correct a manually entered cost without changing recorded sale history, or remove an erroneous open holding.
- Platform and target viewport: Skinflow desktop WebView, 1440px primary viewport, 1100px minimum width.
- Existing design constraints: Dense operational table, IBM Plex typography, light workspace, icon-first row tools, existing shared dialog.
- Must preserve: FIFO sale history, current holdings columns, expandable Steam market detail, keyboard access, explicit destructive confirmation.
- Must avoid: Editing historical sale fills, silent destructive actions, card dashboards, always-visible forms that make the table harder to scan.

## Evidence

| Source | Type | Link | Observed interface | Transferable principle | Do not copy |
| --- | --- | --- | --- | --- | --- |
| Actual Budget | Shipped product documentation | https://actualbudget.org/docs/ | Transaction work stays in a dense register and corrections remain close to the affected row | Keep maintenance attached to the holding row and preserve scan density | Product branding or budget categories |
| GnuCash transaction register | Shipped product manual | https://www.gnucash.org/docs/v5/C/gnucash-manual/trans-enter.html | Spreadsheet-like records are edited in context with explicit commit behavior | Let the user see the current value while editing the replacement cost | Register layout and accounting terminology |
| Zoho Books | Shipped product help | https://www.zoho.com/books/help/ | Record maintenance is exposed from the relevant list/detail surface | Put edit and delete on the holding itself, not in global settings | Zoho navigation and visual styling |
| Xero | Shipped product guides | https://www.xero.com/us/guides/ | Corrections distinguish current records from historical accounting outcomes | Explain that only the unsold position changes | Xero copy or branding |
| QuickBooks Online | Shipped product page | https://quickbooks.intuit.com/accounting/ | Dense financial records use explicit editing and guarded destructive actions | Confirm deletion with the exact item and quantity affected | Marketing composition |
| Odoo Accounting | Shipped product page | https://www.odoo.com/app/accounting | Operational accounting lists prioritize repeated row actions and fast correction | Use compact row tools instead of a separate maintenance page | Odoo modules and colors |
| Wave Accounting | Shipped product page | https://www.waveapps.com/accounting | Simple transaction correction keeps the primary list visible | Use one focused modal rather than navigating away | Product-specific layout |
| GitHub Primer ActionMenu | Official product design system | https://primer.style/product/components/action-menu/ | Secondary row actions fit an icon/menu trigger; dangerous actions are separated | Keep destructive action visually distinct and name it precisely | GitHub iconography and menu styling |
| Fluent 2 Dialog | Official product design system | https://fluent2.microsoft.design/components/web/react/core/dialog/usage | Modal confirmation contains a clear title, consequence, cancel, and primary action | Require confirmation before deleting an open holding | Fluent component appearance |
| Carbon data table | Official product design system | https://carbondesignsystem.com/components/data-table/usage/ | Batch actions appear only after selection; tables retain stable columns | If selection is used, reveal commands contextually without shifting the table | Carbon styling and toolbar copy |

## Extracted Decisions

- Primary work surface: Existing holdings table remains dominant.
- Information hierarchy: Item identity, holding quantities/costs, Steam link, maintenance action.
- Navigation model: No new route; edit/delete happens in place or in a focused dialog.
- Data density and alignment: Add at most one compact action column; numeric columns remain monospaced and right-aligned.
- Typography rhythm: Existing 13-14px table text and compact labels.
- Material and separation treatment: Continuous table, one-pixel dividers, no nested cards.
- Color semantics: Neutral edit action; red reserved for delete and its confirmation.
- Feedback and motion: Dialog/expanded row only; no decorative animation.

## Visual Directions

### Direction A: Row Tools + Focused Dialog

- Layout skeleton: Existing table gains a final tools column with pencil and trash icons; edit opens a compact dialog.
- Evidence used: Zoho, Wave, Primer ActionMenu, Fluent Dialog.
- First-view hierarchy: Holdings table, Steam link, row tools; dialog shows current and replacement average cost.
- Design memory point: A quiet two-icon tool cell with deletion separated by color and confirmation.
- Anti-template result: Pass. The screen stays a ledger table rather than becoming a dashboard.

### Direction B: Selection Command Bar

- Layout skeleton: Checkbox column plus contextual command bar for editing or deleting the selected holding.
- Evidence used: Carbon data table, Odoo, Actual Budget.
- First-view hierarchy: Select a holding, then commands appear in the existing top action bar.
- Design memory point: The top bar states the exact selected item and open quantity.
- Anti-template result: Pass with compromise. Strong for future bulk actions, but adds persistent checkbox weight for single-item edits.

### Direction C: Expanded Maintenance Row

- Layout skeleton: Expanding a holding reveals a maintenance strip above the existing Steam market detail.
- Evidence used: GnuCash register, Xero correction model, QuickBooks guarded edits.
- First-view hierarchy: Table row, expanded average-cost editor, delete command, then market detail.
- Design memory point: Current cost and replacement cost remain visible side by side.
- Anti-template result: Pass with compromise. Context is excellent, but combines market inspection and ledger maintenance in one expansion.

## Approval

- Selected direction: Direction A — Row Tools + Focused Dialog.
- Approved at: 2026-08-17 (user request “a” confirmed Direction A).
- Approved deviations: Delete uses an explicit confirmation dialog; the shared table row remains expandable for market details.

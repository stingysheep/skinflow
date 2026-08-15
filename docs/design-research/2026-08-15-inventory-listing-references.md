# Inventory Grouping and Listing Preview UI Research

## Scope

Skinflow is a desktop-first CS2 inventory and listing tool. The repeated task is to select a quantity of identical items, compare ask/bid depth, set a price, and review proceeds before submitting Steam listings. The design must remain dense enough for pricing work while making the selected item and quantity obvious.

## Reference Evidence

### 1. Xcode

- Source: https://developer.apple.com/xcode/
- Captured evidence: `assets/market-listing/xcode-og.jpg`
- Information architecture: project navigator, central editor/work surface, fixed utility/inspector region, persistent toolbar.
- Visual tension: a narrow utility rail and strong vertical alignment make the central work surface feel authoritative; hierarchy comes from typography and dividers rather than cards.
- Transferable to Skinflow: keep the inventory grid continuous, use a fixed right-side inspector for the selected group, and put quantity/price actions in one command strip.
- Do not copy: Xcode iconography, Apple blue, source-code editor conventions, or branded panel labels.

### 2. Final Cut Pro

- Source: https://support.apple.com/guide/final-cut-pro/welcome/mac
- Information architecture: media/event browser, large central preview/timeline, contextual inspector.
- Visual tension: the timeline is one uninterrupted surface; inspectors are visually quieter but always available.
- Transferable to Skinflow: treat the price table as the uninterrupted work surface and open a contextual listing inspector without navigating away.
- Do not copy: timeline metaphor, dark editing palette, or video transport controls.

### 3. Logic Pro

- Source: https://www.apple.com/logic-pro/
- Captured evidence: `assets/market-listing/logic-pro-og.jpg`
- Information architecture: track/list region, central arrangement surface, contextual controls.
- Visual tension: repeated rows establish rhythm while a small number of accent colors indicate active/armed states.
- Transferable to Skinflow: use row rhythm, mono numeric columns, and reserve accent colors for executable, risky, or unavailable pricing states.
- Do not copy: skeuomorphic mixer controls, instrument branding, or music-specific metaphors.

### 4. TradingView Advanced Chart

- Source: https://www.tradingview.com/chart/
- Information architecture: symbol/search and timeframe controls above a continuous chart, tool rail at the edge, data overlays in the work surface.
- Visual tension: dense controls are compact and aligned; the chart receives the majority of the viewport.
- Transferable to Skinflow: price depth and cumulative ratio should occupy the main area, with compact filter controls and no KPI-card row.
- Do not copy: TradingView symbol list, chart studies, or market-specific colors.

### 5. Bloomberg Terminal

- Source: https://www.bloomberg.com/professional/solution/bloomberg-terminal/
- Information architecture: command/search layer, dense tabular modules, contextual analytics and alerts.
- Visual tension: information density and strict numeric alignment create confidence; status is embedded in the data surface.
- Transferable to Skinflow: show ask/bid ladders side by side, keep labels short, and use persistent column alignment for price, quantity, fee, and proceeds.
- Do not copy: Bloomberg keyboard commands, proprietary typography, yellow branding, or multi-window legacy chrome.

### 6. DataGrip

- Source: https://www.jetbrains.com/datagrip/
- Captured evidence: `assets/market-listing/datagrip-og.jpg`
- Information architecture: narrow project/database tree, central result grid, bottom or side detail panels.
- Visual tension: grids are allowed to be visually plain because selection, sorting, and inspector context carry the interaction.
- Transferable to Skinflow: make grouped inventory rows selectable, preserve selection while filtering, and show details in a stable inspector rather than nested cards.
- Do not copy: database tree terminology, IDE tool windows, or JetBrains product chrome.

### 7. Figma Dev Mode

- Source: https://www.figma.com/dev-mode/
- Captured evidence: `assets/market-listing/figma-dev-mode-og.jpg`
- Information architecture: canvas/work surface with a persistent inspect panel and compact top controls.
- Visual tension: the selected object is the focus; context appears in the inspector without obscuring the canvas.
- Transferable to Skinflow: selecting a grouped item should update a right inspector with thumbnail, depth, fees, and editable listing price.
- Do not copy: canvas handles, design-token terminology, or Figma purple branding.

### 8. Linear Method

- Source: https://linear.app/method
- Captured evidence: `assets/market-listing/linear-method-og.jpg`
- Information architecture: keyboard-friendly command surface, list-first content, contextual details.
- Visual tension: restrained surfaces and short labels keep attention on the current task.
- Transferable to Skinflow: use a compact command bar, clear empty/loading states, and avoid decorative dashboard summaries.
- Do not copy: Linear issue taxonomy, keyboard shortcut names, or Linear indigo palette.

## Extracted Design Decisions

- Primary work surface: one continuous grouped-inventory grid; no KPI card row.
- Selection model: one row per `market_hash_name`, with quantity stepper and available/tradable counts.
- Inspector: fixed-width right panel showing thumbnail, custom price, ask ladder, bid ladder, moving-average cost, fees, and proceeds.
- Numeric treatment: IBM Plex Mono for prices, quantities, fees, ratios, and timestamps; right-aligned columns.
- Materials: neutral light canvas, white work surface, hairline dividers, restrained shadows, no gradients or glass effects.
- Accent usage: blue for active selection/actions, green for executable proceeds, orange for incomplete depth, red for blocked submission.
- Failure/empty states: inline in the work surface, never a page-level marketing panel.

## Anti-Template Check

- No four-card KPI strip.
- No wide default sidebar.
- No card-inside-card hierarchy.
- The three directions below change the spatial skeleton, not merely colors or radii.

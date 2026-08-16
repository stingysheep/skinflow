# Skinflow Development Rules

## Scope

Skinflow is a local CS2 trading workspace. Work is organized by user-facing
capability. Keep each change inside one module unless a shared contract must
change.

## Module workflow

- Start feature work from `master` or the latest coordinator branch.
- Use one branch per capability: `feature/inventory`, `feature/scan`,
  `feature/listings`, `feature/ledger`, or `feature/settings-auth`.
- Keep commits small and use Conventional Commits.
- Run focused tests first, then the full Python and Web checks before
  integration.
- Do not push or merge without an explicit approval and a confirmed remote.

## Dependency direction

- `apps/api/skinflow_api/domain` contains pure business concepts and must not
  import routes, database code, HTTP clients, or Web code.
- `application` owns use cases and ports; it may depend on `domain`.
- `infrastructure` implements application ports and owns persistence and
  platform integrations.
- `routes` and `bootstrap` compose the API; routes must not contain domain
  rules.
- `apps/web/src/features` owns user-facing feature flows and talks to the API
  through feature API clients.
- `apps/web/src/shared` contains reusable UI, API, and hooks only; feature
  decisions stay in feature folders.
- `apps/desktop` owns the desktop shell and launch tooling; it may host the API
  and Web build but must not duplicate business logic.

## Shared-file ownership

The coordinator owns changes to `pyproject.toml`, root `package.json`,
`package-lock.json`, API route registration, Web router registration, shared
tokens/components, and this guidance. A feature branch must describe the
contract change before editing a shared file.

## Forbidden changes during feature work

- Do not move modules merely to satisfy a branch layout.
- Do not mix formatting-only changes with behavior changes.
- Do not commit `.env`, credentials, local databases, caches, logs, build
  output, or generated QA artifacts.

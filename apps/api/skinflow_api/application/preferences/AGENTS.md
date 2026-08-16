# Settings and Auth Module

Read the root `AGENTS.md` and `docs/architecture/module-boundaries.md` first.

Own local preferences, startup authentication, Steam session lifetime, the
Settings Web feature, and the desktop startup/auth bridge when needed. Allowed
paths are this directory, `infrastructure/preferences/`, preference/auth/
Steam-session routes and tests, `apps/web/src/features/settings/`,
`apps/web/src/app/bootstrapAuth.ts`, and the relevant desktop launcher code.

Never persist Steam credentials to disk, logs, databases, or browser storage.
Coordinate before editing router registration, shared clients, root config, or
other modules. Run focused security/session tests and Web checks. Use
`feat(settings-auth): ...` or `fix(settings-auth): ...`; do not merge.

# TurnWidget contributor guide

## Layout
`src/` contains the React dashboard and security-critical schemas/parser. `server/` contains the API and public runtime. `tests/` contains Vitest checks, `integrations/` platform adapters, and `docs/` operational guidance.

## Commands
- Build/dev: `pnpm install`, `pnpm dev`, `pnpm build`
- Migration/seed: `pnpm migrate`, `pnpm seed`
- Quality: `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm test:e2e`

## Nonnegotiable rules
- Derive tenant scope from the authenticated server session; never trust a browser-supplied organization ID.
- AI may alter presentation but **never an EHR action binding**. Only deterministic adapters create locked identity fields.
- Never execute pasted content, accept arbitrary launch URLs, store PHI, expose credentials, or log secrets.
- Use calm, accessible design tokens and shared renderers; support keyboard focus and reduced motion.
- Definition of done: schemas and authorization tested, lint/typecheck/tests/build pass, docs reflect reality, no secret or PHI is committed.

# Turn Anything Into a Widget
A working security-first V1 slice: paste a confirmed TelehealthUS action, verify and lock it, visually customize a widget, publish it, and receive isolated universal embed code. A mock EHR catalog demonstrates the V2 selection boundary honestly.

## Start
```bash
cp .env.example .env
pnpm install
pnpm migrate && pnpm seed
pnpm dev
```
Open <http://localhost:5173>. API health is <http://localhost:4100/api/health>. The demo persona is `clinicadmin-a@example.test` / `TurnWidget-Demo-Only!`; identity is illustrative and the current slice does not implement a login boundary.

## Demo
For V1 choose **Create**, paste any supplied route format, Analyze, confirm the locked IDs, edit copy/color, and use the Desktop/Tablet/Mobile controls. Click the preview CTA to inspect the locked launch action, then Publish and copy the generated embed. For the V2 boundary call `/api/ehr/clinics`; it returns distinct Desert Wellness and Modern Men's Health mock catalogs, while `/api/ehr/status` clearly reports `Mock`.

The copied loader is cross-origin capable: it resolves public API requests against the loader script's own origin rather than the website embedding it. Modal launch requires TelehealthUS to permit framing as described in `docs/EMBEDDING_AND_CSP.md`.

## Quality
```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

See the [status](docs/STATUS.md), [security boundary](docs/SECURITY_AND_DATA_BOUNDARY.md), [embedding constraints](docs/EMBEDDING_AND_CSP.md), and [real connector requirements](docs/REAL_TELEHEALTHUS_INTEGRATION.md). This is not production-ready until the explicitly listed persistence/auth/tenant work is completed.

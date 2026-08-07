# Embedding and CSP
The universal custom element uses Shadow DOM for host-CSS isolation. A cross-origin EHR iframe cannot be inspected or resized without cooperation. TelehealthUS must permit the embedding origins via `Content-Security-Policy: frame-ancestors` and must not send conflicting `X-Frame-Options`.

Future child messages must use `TURNWIDGET_READY`, `TURNWIDGET_HEIGHT`, `TURNWIDGET_NAVIGATED`, or `TURNWIDGET_COMPLETED`, contain no patient data, and be accepted only after exact origin and schema validation. Until headers are verified, use redirect or new-tab behavior; never proxy the EHR to evade browser controls.

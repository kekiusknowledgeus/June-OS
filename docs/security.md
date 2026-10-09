# Security and privacy

June runs as the current Windows user, never deliberately as administrator. The model cannot grant permission, modify policy through a tool, or supply an approval token. Approvals originate from the authenticated user interface or terminal.

Risk levels are `OBSERVE=0`, `LOCAL=1`, `MODIFY=2`, `EXTERNAL=3`, `SENSITIVE=4`, `CRITICAL=5`. Levels 2–5 require a separate user decision for each exact action. The preview contains sanitized complete arguments. Approvals expire after five minutes, are single use, bind a SHA-256 digest of the tool and arguments, and are invalidated by restart or cancellation. Privacy and sensor gates are checked again after approval.

Arbitrary PowerShell always requires level 4 approval. It is **not an OS sandbox**: an approved shell command has the current user's authority, including network and filesystem access beyond the structured-tool roots. Review the complete command. GUI interactions require level 3 approval because their external effects cannot reliably be classified from coordinates or keystrokes. No privilege elevation or destructive Git tools are provided.

File tools resolve paths, confine access to registered allowed roots, reject UNC/alternate streams, and protect `.env*`, `.git`, `.ssh`, `.aws`, `.codex`, `.venv`, `.cache`, runtime data, models and common credential files. Binary and oversized text reads fail. Updates require a current content hash. Directory deletion and recursive deletion are not exposed. This policy is not a substitute for OS access controls against a malicious local process racing filesystem changes.

Research and browser network access require action approval. Private/loopback/metadata destinations and nonstandard ports are rejected. Redirect targets are rechecked. Playwright uses a fresh isolated context, without importing your personal browser profile. Public-DNS checks reduce SSRF risk but are not a network sandbox or a complete defense against DNS rebinding. Do not give the runtime unrestricted access to sensitive network environments.

The local API binds only `127.0.0.1`, validates Host/Origin, rejects chunked/oversized requests, and requires a random bearer token. It is stored in `data/api-token`, which file tools cannot read. Dashboard launch passes it in a fragment (not an HTTP query); the page removes the fragment and keeps it in session storage. No third-party scripts/CDNs are used. Never expose this API through port forwarding or a reverse proxy.

Secrets come from environment variables, the explicitly approved `.env.local` bootstrap file, or Windows Credential Manager through `keyring`. `.env.local` is plaintext and ignored by Git; do not share it. Additional credentials can be stored encrypted by the OS with `python -m june vault --name NAME`. Known secrets, secret environment values and common key patterns are redacted from context/audits. Arbitrary unknown secrets cannot be identified perfectly. Local vault deletion is not remote provider revocation; revoke provider keys in that provider's account settings.

Privacy mode cancels active jobs, stops microphone and speech, closes the controlled browser, disables screen/camera capture, blocks network tools and hosted inference, and pauses proactive work. It cannot retract data already sent or undo completed actions. Exiting privacy does not automatically re-enable sensors. Local records remain available.

Prompt injection text is treated as untrusted evidence. This is reinforced by explicit tool permissions, not claimed to be solved by prompting. Automated tests verify malicious text remains tool data and that modification/external paths are gated; they do not constitute a comprehensive model red-team certification.

# Integrations and hardware

`Integration` defines connect, disconnect, capabilities, execute and health. All provider code is isolated from core orchestration. Connections are request-scoped and closed after calls. Health reports credential/configuration readiness, not a verified remote login. Live service integration tests have not run because credentials were not supplied.

Configure nonsecret service settings in protected `data/integrations.json`:

```json
{
  "email": {"username": "you@example.com", "imap_host": "imap.example.com", "smtp_host": "smtp.example.com", "smtp_port": 465},
  "calendar": {"username": "you@example.com", "url": "https://calendar.example.com/dav/calendars/you/default/"}
}
```

Store secrets interactively in Windows Credential Manager:

```
.\.venv\Scripts\python.exe -m june vault --name EMAIL_PASSWORD
.\.venv\Scripts\python.exe -m june vault --name CALENDAR_PASSWORD
.\.venv\Scripts\python.exe -m june vault --name GITHUB_TOKEN
```

Email supports IMAP inbox/search/read, local draft content and SMTP-over-TLS send. Providers requiring OAuth must use a compatible app-password setup or a future OAuth adapter; June does not pretend the account is connected. Sending requires exact-action approval. Email content is untrusted.

Calendar supports CalDAV REPORT retrieval and conditional iCalendar create/modify, using ETags for modifications and If-None-Match for creates. The model can summarize calendar XML/ICS returned by the provider. GitHub supports repositories, issues, pull requests, commits and notifications using a scoped token. Authentication expiration or revocation causes a reported failure; automatic OAuth refresh is not implemented.

`Device`, `Sensor`, `Actuator`, `Command`, `State` and `Robot` describe hardware contracts. `HttpDevice` can connect to a user-provided gateway with allowlisted commands. No hardware gateway is registered by default and no robot actions are exposed to the agent. A physical adapter must enforce independent safety interlocks, emergency stop and appropriate critical-action policy outside the language model before enabling motion.

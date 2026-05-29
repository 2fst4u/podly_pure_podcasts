## 2025-01-20 - Legacy Route Authorization Bypass
**Vulnerability:** Found a legacy GET route (`/set_whitelist/<p_guid>/<val>`) that lacked `require_admin` authorization checks, allowing unauthenticated users to toggle whitelist status.
**Learning:** Legacy frontend integration routes (especially GET requests with side effects) might have been overlooked when global authorization was added. Always verify that state-changing routes have explicit auth/admin checks.
**Prevention:** Ensure that all endpoints causing state changes (like modifying database records) have explicit `require_admin` or `require_auth` guards, even if they are accessed via GET for convenience in old code.

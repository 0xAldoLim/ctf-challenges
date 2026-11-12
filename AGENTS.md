# CTF archive import rules

Follow [the import policy](docs/IMPORT_POLICY.md) for every import.

- Identify the original competition, its organizer, the challenge authors, and a pinned source revision.
- Verify redistribution permission before adding upstream challenge materials. Record a provenance-only entry when permission is unclear.
- Preserve existing competitions, avoid duplicate imports, and use stable paths and task IDs. Preserve provenance and make each import independently auditable.
- For every import, update the root README with the competition name, source repository, organizing team, challenge list, and each challenge's original authors. Update the competition README with the same provenance.
- Preserve authorized player attachments and original names. Track player-visible and operator-only files separately. Record missing files, dependencies, and challenges requiring preparation.
- Exclude all standalone solutions, flags, writeups, solver scripts, and answer keys from repository history. Keep private archives outside this repository and benchmark workspaces.
- Transfer files without upstream Git history. Never execute challenge materials or solve, exploit, reverse-engineer, or analyze vulnerabilities during ingestion.
- Review the staged tree and resulting commit before publishing. Resolve validator errors and document the disposition of manual review findings.

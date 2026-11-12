# AGENTS.md

Conventions for this repository.

## Layout

```
README.md                      root index: competitions, challenges, credits
AGENTS.md
competitions/<year>/<competition>/
    README.md                  competition description, credits, challenge index
    challenges/<original-dir>/
        README.md              original title and description only
        manifest.json          source, authors, status, file list with size and SHA-256
        static/                participant-facing files
        server/, vm/, sources/ operator and source material, kept separate
```

- Keep the upstream directory names and file names.
- Do not create empty directories.
- Add a new competition under its year, update its README, then update the root README.

## Import rules

- Import from a pinned upstream commit, without upstream Git history.
- Record the competition name, organizer, challenge authors, source URL, and commit in each manifest.
- Keep the original title and description. Remove writeups, solution sections, solver and exploit scripts, and explicit answer keys.
- Keep server and challenge logic functional. Replace reference flags in server configuration with `SAS{placeholder}`.
- Keep removed material in a private folder outside this repository. Never commit it.
- Do not execute challenge materials.
- List any artifact that could not be retrieved in the manifest's `missing_or_external_dependencies`. Never substitute a metadata-only placeholder for a real file.
- Status values: `ready` (participant files present), `incomplete` (a required file is missing or external), `source_only` (no participant attachment upstream).
- Verify the import: file counts, sizes, SHA-256 of unchanged files, and that binary files are not empty.

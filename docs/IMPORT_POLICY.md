# CTF import policy

## Source and rights

Inspect the destination first. Record the competition name, organizer, author credits, source URL, exact source commit, and original directory for every entry. Keep the original challenge directory names under `competitions/<year>/<competition>/challenges/`. Use the competition slug and original directory in each stable challenge ID. Assign stable IDs to distinct tasks in shared directories and record their relationship. Check existing paths and IDs before importing.

Verify redistribution permission for descriptions, individual attachments, and dependencies. Preserve applicable notices and document the permission and scope. If permission is unclear, record a provenance-only entry without upstream descriptions, attachments, or infrastructure. GitHub public visibility alone does not establish permission to redistribute materials. [GitHub licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)

## Contents and review

Keep original wording and player instructions for authorized descriptions. Check that local references point to the intended published files. Preserve legitimate puzzle data and examples, even when they resemble an answer. Exclude solution sections, answer keys, walkthroughs, solver utilities, and spoiler links or media. Classify files by intended audience and purpose. Record omissions and unavailable dependencies explicitly. Perform static review without executing challenge contents or investigating vulnerabilities.

Keep any separately authorized private reference archive outside this repository and any benchmark workspace. If configured, use `CTF_PRIVATE_VAULT` and verify its access controls. Keep private material out of Git, remotes, releases, Git LFS, and solver access.

## Entry format and isolation

A challenge entry has a README and a JSON manifest. The manifest records its stable ID, title, competition, year, categories, credited authors, pinned source, original path, status, and known missing or external dependencies. List paths relative to the challenge entry in `player_files` and `operator_files`. Supply a SHA-256 digest for each listed artifact. Use `ready`, `incomplete`, `manual_preparation`, or `provenance_only` as the preparation status. Explain any status other than `ready` in `status_reason`. Mark dependencies unverified if no dependency review was performed. Use `parts` for a shared directory with multiple task IDs.

Keep authorized player files under `player/` and separately reviewed operator files under `operator/`. Include only infrastructure safe and permitted to publish. Record a manual preparation requirement if sensitive values cannot be removed safely. PRESTIGE's runner owns isolation and network controls. A benchmark agent's inputs must be limited to the selected challenge's player-visible description and files. Repository metadata, upstream sources, unrelated challenges, operator files, and private answers belong outside that scope. Unrestricted internet access is incompatible with solution-blind evaluation.

## Publication

Update both competition indexes. Review attribution, license evidence, expected files, exclusions, and the complete Git diff. Run these commands from the repository root to inspect the staged index and the commit, respectively.

```sh
python scripts/validate_corpus.py --index
python scripts/validate_corpus.py --commit HEAD
```

The validator reads Git objects without checking out content. It checks manifests, hashes, common Markdown references, suspicious filenames, probable secret literals, and supported archive member metadata. Treat warnings as findings to adjudicate. Heuristics cannot establish redistribution rights or certify opaque data as answer-free. Review the actual files and the complete candidate diff before publishing. Publish only reviewed changes on the appropriate destination branch and verify the remote commit.

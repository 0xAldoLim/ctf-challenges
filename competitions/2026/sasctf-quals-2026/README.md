# SAS CTF 2026 Quals

Challenges from the SAS CTF 2026 Quals, a 24-hour jeopardy CTF. Event: [ctf.thesascon.com](https://ctf.thesascon.com), [CTFtime](https://ctftime.org/event/3109).

Source: [Team-Drovosec/sasctf-quals-2026](https://github.com/Team-Drovosec/sasctf-quals-2026) at commit `4a4c403f80ee1772185a967aa6ad7226d6708968`.

Archived: 23 challenge directories, 24 tasks (Escape from Guba I and II share `game-guba/`). Participant-ready packages: 15.

## Credits

Organizers ([upstream README](https://github.com/Team-Drovosec/sasctf-quals-2026/blob/4a4c403f80ee1772185a967aa6ad7226d6708968/README.md)):
- Project Lead: [@bzvr](https://github.com/bzvr)
- Development Lead: [@kumfc](https://github.com/kumfc)
- DevOps/Backend: [@kochanac](https://github.com/kochanac) and [@SS4ar](https://github.com/SS4ar)
- Platform frontend: [@kumfc](https://github.com/kumfc) (PASECA Sans by [@twosd](https://t.me/twosd))
- Partners: Kaspersky Academy, Yandex.Cloud, Drovosec, cR4.sh

Challenge authors are listed per challenge below. Published by [Team-Drovosec](https://github.com/Team-Drovosec).

## Layout

- `static/`: participant-facing attachments.
- `server/`, `vm/`, `sources/`: operator and source material, kept separate from `static/`.
- Each challenge `manifest.json` lists every file with its size and SHA-256.

Removed from the packages: writeups, solution sections, solver and exploit scripts, and explicit answer keys. Reference flags in server configuration are replaced with `SAS{placeholder}`. The removed material is kept outside this repository.

Status: `ready` means participant files are present. `incomplete` means a required file is external and not included. `source_only` means the upstream published no participant attachment.

## Known gaps

- `game-guba/`: two external archives referenced by the upstream README are not included (`ctf_guba_...bsp`, about 189 MB; `v3.7z`, about 2.6 GB).
- `rev-cerum/`: `sources/Cerum/resources/flag.jpg` (a BMP resource) is excluded pending review.
- `web-naas/`: `sources/client/cmd/solver.go` (a hidden `solver` subcommand) is excluded pending review. The Go client may not build without it.
- `mlw-cyrill/`: the upstream has no attachments; only the README is present.

## Challenge index

| Challenge | Category | Authors | Status | Path |
| --- | --- | --- | --- | --- |
| Backrooms | game | [@kumfc](https://github.com/kumfc), [@Ezzh](https://github.com/Ezzh) | source_only | [`game-backrooms/`](challenges/game-backrooms/README.md) |
| Escape the Guba I & II | game | [@kumfc](https://github.com/kumfc), [@Ezzh](https://github.com/Ezzh) | incomplete | [`game-guba/`](challenges/game-guba/README.md) |
| CBT | misc | [@MaksTresh](https://github.com/MaksTresh), [@kumfc](https://github.com/kumfc) | source_only | [`misc-cbt/`](challenges/misc-cbt/README.md) |
| Gatekeeper v2.0 | misc, pwn | [@m4drat](https://github.com/m4drat) | ready | [`misc-gatekeeper/`](challenges/misc-gatekeeper/README.md) |
| Kolobok | misc | [@Chillov3k](https://github.com/Chillov3k) | source_only | [`misc-kolobok/`](challenges/misc-kolobok/README.md) |
| Readyiss or not | misc, pwn | [@SS4ar](https://github.com/SS4ar) | source_only | [`misc-readyssornot/`](challenges/misc-readyssornot/README.md) |
| Behind the Buffet | misc | [@kumfc](https://github.com/kumfc) | source_only | [`misc-tgs/`](challenges/misc-tgs/README.md) |
| Backfloppa | malware | [@cotsom](https://github.com/cotsom) | ready | [`mlw-backfloppa/`](challenges/mlw-backfloppa/README.md) |
| First Day First | malware | [@bzvr](https://github.com/bzvr) | source_only | [`mlw-cyrill/`](challenges/mlw-cyrill/README.md) |
| Incident 67 | network | [@cfrt-dev](https://github.com/cfrt-dev) | ready | [`net-incident-67/`](challenges/net-incident-67/README.md) |
| JSculator | pwn, 0day | [@s41nt0l3xus](https://github.com/s41nt0l3xus) | ready | [`pwn-jsculator/`](challenges/pwn-jsculator/README.md) |
| Sasenger | pwn | [@m4drat](https://github.com/m4drat) | ready | [`pwn-sasenger/`](challenges/pwn-sasenger/README.md) |
| Snaking | pwn | [@YariKartoshe4ka](https://github.com/YariKartoshe4ka) | ready | [`pwn-snaking/`](challenges/pwn-snaking/README.md) |
| Snaking Revenge | pwn | [@YariKartoshe4ka](https://github.com/YariKartoshe4ka) | ready | [`pwn-snaking-revenge/`](challenges/pwn-snaking-revenge/README.md) |
| Cerum | reverse | [@avoidcode](https://github.com/avoidcode) | ready | [`rev-cerum/`](challenges/rev-cerum/README.md) |
| Lut, I am your father | reverse | [@cfrt-dev](https://github.com/cfrt-dev) | ready | [`rev-fpga/`](challenges/rev-fpga/README.md) |
| Venom Protect | reverse | [@lockheeed](https://github.com/lockheeed) | ready | [`rev-venom/`](challenges/rev-venom/README.md) |
| Gav | web | [@SS4ar](https://github.com/SS4ar) | ready | [`web-gav/`](challenges/web-gav/README.md) |
| Nexus as a Service | web | [@SS4ar](https://github.com/SS4ar) | ready | [`web-naas/`](challenges/web-naas/README.md) |
| paradoxy | web | [@cotsom](https://github.com/cotsom) | source_only | [`web-paradoxy/`](challenges/web-paradoxy/README.md) |
| Redis Nightmare | web | [@FrakenboK](https://github.com/FrakenboK) | ready | [`web-sentinel/`](challenges/web-sentinel/README.md) |
| XOD Revenge | web | [@paul-axe](https://github.com/paul-axe) | ready | [`web-xod-revenge/`](challenges/web-xod-revenge/README.md) |
| Sanity Files | welcome | [@kumfc](https://github.com/kumfc) | ready | [`welcome-sanity-files/`](challenges/welcome-sanity-files/README.md) |

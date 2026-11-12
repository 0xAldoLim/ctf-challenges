#!/usr/bin/env python3
"""Check the staged index or a commit without reading working-tree artifacts."""

import argparse
from collections import Counter
from dataclasses import dataclass
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import subprocess
import sys
import tarfile
from urllib.parse import unquote, urlsplit
import zipfile


ROOT = Path(__file__).resolve().parents[1]
MAX_INSPECTION_BYTES = 32 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
STATUSES = {"ready", "incomplete", "manual_preparation", "provenance_only"}
CHALLENGE = re.compile(r"competitions/([0-9]{4})/([a-z0-9-]+)/challenges/([a-z0-9-]+)/(.+)")
SPOILER = re.compile(r"^(?:write[-_ ]?ups?|solutions?|solvers?|walkthroughs?|answers?|reference[-_ ]?flags?|flags?)(?:[-_ ]|[.\/]|$)", re.I)
PRIVATE_DIRS = {"private", "private-vault", "ctf-private-solutions", "answer-keys"}
WINDOWS_RESERVED = re.compile(r"^(?:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:\.|$)", re.I)
TEXT_CONFIG = {".cfg", ".conf", ".ini", ".json", ".properties", ".toml", ".yaml", ".yml"}
MARKDOWN_LINKS = (
    re.compile(r"!?\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s()]+))"),
    re.compile(r"(?m)^[ ]{0,3}\[[^\]\n]+\]:[ \t]*(?:<([^>\n]+)>|([^\s]+))"),
    re.compile(r"""(?i)\b(?:href|src)\s*=\s*["']([^"']+)["']"""),
)
ANSWER_SECTION = re.compile(r"(?im)^[ \t]{0,3}#{2,6}[ \t]+(?:solution|write[- ]?up|walkthrough|flag|answer)s?[ \t]*#*[ \t]*$")
ANSWER_LINE = re.compile(r"(?im)^[ \t]*(?:[-*][ \t]+)?\**(?:correct[ \t]+|reference[ \t]+)?(?:flag|answer)\**[ \t]*:[ \t]*[\x60*]*[A-Z0-9_-]+\{[^}\r\n]+\}")
CREDENTIAL = re.compile(r"""(?im)^[ \t]*(?:(?:-|export|env)[ \t]+)?["']?(?:[a-z0-9_]+_)?(flag|password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)["']?[ \t]*[:=][ \t]*(.+)$""")
SECRET_SIGNATURE = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----|\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16})\b")


@dataclass(frozen=True)
class Entry:
    path: str
    mode: str
    oid: str


def git(*args):
    return subprocess.check_output(["git", "--no-replace-objects", *args], cwd=ROOT)


def git_entries(commit):
    if commit is None:
        records = git("ls-files", "--stage", "-z")
    else:
        tree = git("rev-parse", "--verify", "--end-of-options", f"{commit}^{{tree}}").decode().strip()
        records = git("ls-tree", "-r", "-z", tree)

    for record in records.split(b"\0")[:-1]:
        metadata, path = record.decode("utf-8").split("\t", 1)
        fields = metadata.split()
        if commit is None:
            mode, oid, stage = fields
            if stage != "0":
                raise ValueError("resolve Git index conflicts before validation")
        else:
            mode, _, oid = fields
        yield Entry(path, mode, oid)


def blob_details(oid):
    """Hash raw Git bytes and retain only a bounded buffer for inspection."""
    size = int(git("cat-file", "-s", oid))
    if size <= MAX_INSPECTION_BYTES:
        raw = git("cat-file", "blob", oid)
        return hashlib.sha256(raw).hexdigest(), raw
    digest = hashlib.sha256()
    with subprocess.Popen(["git", "--no-replace-objects", "cat-file", "blob", oid], cwd=ROOT, stdout=subprocess.PIPE) as proc:
        for chunk in iter(lambda: proc.stdout.read(1024 * 1024), b""):
            digest.update(chunk)
        if proc.wait():
            raise ValueError("could not read Git blob")
    return digest.hexdigest(), None


def safe_path(path):
    return bool(path) and all(
        part not in {"", ".", ".."}
        and part.casefold() != ".git"
        and not part.endswith((" ", "."))
        and not WINDOWS_RESERVED.match(part)
        and not re.search(r'[\\:*?"<>|\x00-\x1f\x7f]', part)
        for part in path.split("/")
    )


def spoiler_path(path):
    return any(part.casefold() in PRIVATE_DIRS or SPOILER.match(part) for part in path.split("/"))


def strings(value):
    return isinstance(value, list) and all(isinstance(s, str) and s.strip() for s in value)


def metadata_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value or SPOILER.match(key) or key.casefold() in {"hint", "hints"}:
            raise ValueError("duplicate or disallowed metadata field")
        value[key] = item
    return value


def https_url(value):
    if not isinstance(value, str):
        return False
    try:
        url = urlsplit(value)
        return url.scheme == "https" and bool(url.hostname) and not url.username
    except ValueError:
        return False


class Validator:
    def __init__(self, entries):
        self.entries = entries
        self.digests = {}
        self.manifests = {}
        self.descriptions = {}
        self.ids = set()
        self.errors = []
        self.warnings = []
        self.counts = Counter()
        self.challenges = {}

    def check_paths(self):
        folded = {}
        vault = os.environ.get("CTF_PRIVATE_VAULT")
        if vault and Path(vault).expanduser().resolve().is_relative_to(ROOT):
            self.errors.append("CTF_PRIVATE_VAULT resolves inside the repository")
        for path, entry in self.entries.items():
            if not safe_path(path):
                self.errors.append(f"{path!r}: unsafe repository path")
            for parent in (path, *(p.as_posix() for p in PurePosixPath(path).parents)):
                other = folded.setdefault(parent.casefold(), parent)
                if other != parent:
                    self.errors.append(f"{parent!r}: case-insensitive path collision")
            if entry.mode not in {"100644", "100755"}:
                self.errors.append(f"{path!r}: symlink, submodule, or unsupported Git mode")
            parents = path.split("/")[:-1]
            if any(part.casefold() in PRIVATE_DIRS or SPOILER.match(part) for part in parents):
                self.errors.append(f"{path!r}: potential solution or private archive path")
            elif spoiler_path(path):
                self.warnings.append(f"{path!r}: possible solution or answer filename")
            match = CHALLENGE.fullmatch(path)
            if match:
                year, competition, folder, relative = match.groups()
                self.challenges.setdefault((year, competition, folder), set()).add(relative)
            elif path.startswith("competitions/") and "/challenges/" in path:
                self.errors.append(f"{path!r}: unexpected challenge path")

    def add_id(self, path, value, expected=None):
        if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9-]+(?:/[a-z0-9-]+){1,2}", value):
            self.errors.append(f"{path}: missing or invalid task ID")
        elif value in self.ids:
            self.errors.append(f"{path}: duplicate task ID")
        else:
            self.ids.add(value)
        if expected is not None and value != expected:
            self.errors.append(f"{path}: challenge ID does not match its directory")

    def check_manifest(self, location, files):
        year, competition, folder = location
        competition_root = f"competitions/{year}/{competition}"
        root = f"{competition_root}/challenges/{folder}"
        path = f"{root}/manifest.json"

        if "README.md" not in files:
            self.errors.append(f"{root}: missing challenge README")
        if f"{competition_root}/README.md" not in self.entries:
            self.errors.append(f"{competition_root}: missing competition README")
        if path not in self.manifests:
            self.errors.append(f"{root}: missing or unreadable manifest")
            return
        try:
            manifest = json.loads(self.manifests[path], object_pairs_hook=metadata_object)
            if not isinstance(manifest, dict):
                raise ValueError
        except (ValueError, UnicodeError, RecursionError):
            self.errors.append(f"{path}: invalid manifest object")
            return

        expected = f"{competition}/{folder}"
        self.add_id(path, manifest.get("id"), expected)
        for field in ("title", "competition"):
            value = manifest.get(field)
            if not isinstance(value, str) or not value.strip():
                self.errors.append(f"{path}: missing {field}")
        if manifest.get("year") != int(year):
            self.errors.append(f"{path}: invalid competition year")
        categories = manifest.get("categories")
        if not strings(categories) or not categories:
            self.errors.append(f"{path}: missing categories")
        authors = manifest.get("authors")
        if not isinstance(authors, list) or not authors or any(
            not isinstance(author, dict)
            or not isinstance(author.get("name"), str)
            or not author["name"].strip()
            or ("url" in author and not https_url(author["url"]))
            for author in authors
        ):
            self.errors.append(f"{path}: missing or invalid original-author credits")
        source_commit = manifest.get("source_commit")
        source_path = manifest.get("source_path")
        if (
            not https_url(manifest.get("source_repository"))
            or not isinstance(source_commit, str)
            or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", source_commit)
            or not isinstance(source_path, str)
            or not safe_path(source_path)
            or source_path.split("/")[-1] != folder
        ):
            self.errors.append(f"{path}: invalid pinned source provenance")
        status = manifest.get("preparation_status")
        if not isinstance(status, str) or status not in STATUSES:
            self.errors.append(f"{path}: invalid preparation status")
        else:
            self.counts[status] += 1
        reason = manifest.get("status_reason")
        if status != "ready" and (not isinstance(reason, str) or not reason.strip()):
            self.errors.append(f"{path}: missing preparation status reason")
        if not strings(manifest.get("missing_or_external_dependencies")):
            self.errors.append(f"{path}: missing or invalid dependency list")

        parts = manifest.get("parts", [])
        if not isinstance(parts, list):
            self.errors.append(f"{path}: invalid parts list")
        else:
            for part in parts:
                if not isinstance(part, dict) or not isinstance(part.get("title"), str) or not part["title"].strip():
                    self.errors.append(f"{path}: invalid part metadata")
                    continue
                part_id = part.get("id")
                self.add_id(path, part_id)
                if not isinstance(part_id, str) or part_id.rpartition("/")[0] != expected:
                    self.errors.append(f"{path}: part ID must extend its challenge ID")

        listed = set()
        for audience in ("player", "operator"):
            field = f"{audience}_files"
            paths = manifest.get(field)
            if not strings(paths):
                self.errors.append(f"{path}: invalid {field} list")
                continue
            for artifact in paths:
                if not safe_path(artifact) or not artifact.startswith(f"{audience}/") or artifact in listed:
                    self.errors.append(f"{path}: invalid, duplicated, or misplaced {audience} artifact")
                    continue
                listed.add(artifact)
                if artifact not in files:
                    self.errors.append(f"{path}: missing listed {audience} artifact {artifact!r}")

        actual = files - {"README.md", "manifest.json"}
        if actual - listed:
            self.errors.append(f"{path}: {len(actual - listed)} unlisted challenge file(s)")
        if status == "provenance_only" and (actual or listed):
            self.errors.append(f"{path}: provenance-only entry includes challenge artifacts")
        description = f"{root}/README.md"
        if description in self.descriptions:
            self.check_markdown(description, self.descriptions[description],
                                player_root=None if status == "provenance_only" else f"{root}/player/")
        hashes = manifest.get("sha256")
        if not isinstance(hashes, dict) or set(hashes) != listed:
            self.errors.append(f"{path}: SHA-256 entries do not match the artifact lists")
        else:
            for artifact in sorted(actual & listed):
                digest = self.digests.get(f"{root}/{artifact}")
                if digest is None or hashes[artifact] != digest:
                    self.errors.append(f"{path}: SHA-256 mismatch for {artifact!r}")

    def check_markdown(self, path, text, player_root=None):
        # Fenced examples can illustrate syntax, including an answer format.
        prose = re.sub(r"(?ms)^[ ]{0,3}([\x60~]{3,})[^\n]*\n.*?^[ ]{0,3}\1[ \t]*$", "", text)
        if ANSWER_SECTION.search(prose) or ANSWER_LINE.search(prose):
            self.errors.append(f"{path}: possible explicit answer or solution section")
        match = CHALLENGE.fullmatch(path)
        if match and match[4].startswith("player/"):
            player_root = path[: -len(match[4])] + "player/"
        for pattern in MARKDOWN_LINKS:
            for link in pattern.finditer(prose):
                target = next(value for value in link.groups() if value is not None)
                try:
                    url = urlsplit(target)
                except ValueError:
                    self.errors.append(f"{path}: malformed Markdown reference")
                    continue
                ref = unquote(url.path)
                if spoiler_path(ref):
                    self.warnings.append(f"{path}: Markdown reference points to a possible spoiler")
                if url.scheme or url.netloc or not ref:
                    continue
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), ref))
                if (ref.startswith("/") or "\\" in ref or not safe_path(resolved)
                        or (player_root and not resolved.startswith(player_root))):
                    self.errors.append(f"{path}: Markdown reference escapes its allowed scope")
                elif resolved not in self.entries and not any(p.startswith(f"{resolved}/") for p in self.entries):
                    self.errors.append(f"{path}: broken relative Markdown reference {ref!r}")

    def check_archive(self, path, raw, kind):
        """Inspect member names and types. Never extract files."""
        try:
            if kind == "zip":
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    for member in archive.infolist():
                        self.check_member(path, member.filename, stat.S_ISLNK(member.external_attr >> 16))
                return

            if kind == "gzip":
                with gzip.GzipFile(fileobj=io.BytesIO(raw)) as archive:
                    raw = archive.read(MAX_INSPECTION_BYTES + 1)
                if len(raw) > MAX_INSPECTION_BYTES:
                    self.warnings.append(f"{path}: expanded archive exceeds inspection limit")
                    return
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
                for member in archive:
                    self.check_member(path, member.name, not (member.isfile() or member.isdir()))
        except (OSError, EOFError, ValueError, tarfile.TarError, zipfile.BadZipFile):
            self.warnings.append(f"{path}: archive metadata could not be read")

    def check_member(self, path, name, unsafe_type):
        if name in {".", "./"} and not unsafe_type:
            return
        name = name.removeprefix("./").rstrip("/")
        if unsafe_type or not safe_path(name):
            self.errors.append(f"{path}: unsafe archive member path or type")
        elif spoiler_path(name):
            self.warnings.append(f"{path}: possible spoiler in archive member name")

    def inspect_blob(self, path, raw):
        name = PurePosixPath(path).name.casefold()
        suffix = PurePosixPath(path).suffix.casefold()
        if raw is None:
            self.warnings.append(f"{path}: blob exceeds the automated content inspection limit")
            return
        if raw.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
            self.warnings.append(f"{path}: Git LFS pointer requires separate artifact validation")
            return
        if suffix in {".zip", ".jar"} or raw.startswith(b"PK\x03\x04"):
            self.check_archive(path, raw, "zip")
        elif name.endswith((".tar.gz", ".tgz", ".tar")):
            self.check_archive(path, raw, "gzip" if name.endswith((".tar.gz", ".tgz")) else "tar")
        elif suffix in {".7z", ".rar", ".bz2", ".gz", ".xz", ".zst"}:
            self.warnings.append(f"{path}: archive format requires manual review")

        if suffix in {".md", ".markdown"}:
            markdown = raw.decode("utf-8", errors="replace")
            match = CHALLENGE.fullmatch(path)
            if match and match[4] == "README.md":
                self.descriptions[path] = markdown
            else:
                self.check_markdown(path, markdown)
        elif name == "manifest.json" and len(raw) <= MAX_MANIFEST_BYTES:
            self.manifests[path] = raw
        is_config = suffix in TEXT_CONFIG or name.startswith((".env", "dockerfile", "compose."))
        if b"\0" not in raw:
            text = raw.decode("utf-8", errors="replace")
            if SECRET_SIGNATURE.search(text):
                self.errors.append(f"{path}: possible committed credential or private key")
            if is_config:
                for credential in CREDENTIAL.finditer(text):
                    value = credential[2].split(" #", 1)[0].strip().rstrip(",").strip("\"'")
                    if value and not re.fullmatch(r"(?:\$\{[A-Z_][A-Z0-9_]*\}|\$[A-Z_][A-Z0-9_]*|<[^>]+>|null|~)", value, re.I):
                        self.warnings.append(f"{path}: review possible literal {credential[1].lower()} in configuration")
                        break

    def validate(self):
        self.check_paths()
        for path, entry in self.entries.items():
            if entry.mode not in {"100644", "100755"} or not safe_path(path):
                continue
            digest, raw = blob_details(entry.oid)
            self.digests[path] = digest
            self.inspect_blob(path, raw)
        for location, files in sorted(self.challenges.items()):
            self.check_manifest(location, files)
        for path in ("README.md", "AGENTS.md", "docs/IMPORT_POLICY.md", "scripts/validate_corpus.py"):
            if path not in self.entries:
                self.errors.append(f"{path}: required repository file is missing")
        if not self.challenges:
            self.errors.append("no challenge entries found")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    revision = parser.add_mutually_exclusive_group()
    revision.add_argument("--index", action="store_true", help="validate staged objects (default)")
    revision.add_argument("--commit", help="validate this commit tree")
    args = parser.parse_args()
    try:
        entries = {entry.path: entry for entry in git_entries(args.commit)}
        validator = Validator(entries)
        validator.validate()
    except (subprocess.CalledProcessError, UnicodeError, ValueError) as exc:
        print(f"Git tree could not be validated: {exc}", file=sys.stderr)
        return 2

    for label, messages in (("ERROR", validator.errors), ("REVIEW", validator.warnings)):
        for message in messages:
            print(f"{label} {message}")
    status_counts = ", ".join(f"{status}={validator.counts[status]}" for status in sorted(STATUSES))
    print(f"{len(entries)} files, {len(validator.challenges)} challenge directories, {status_counts}")
    print(f"{len(validator.errors)} error(s), {len(validator.warnings)} manual review finding(s)")
    return int(bool(validator.errors))


if __name__ == "__main__":
    sys.exit(main())

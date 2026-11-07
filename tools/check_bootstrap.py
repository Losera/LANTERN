#!/usr/bin/env python3
"""Offline checks for the bootstrap's Markdown subset; never run example commands.

Supported links: inline Markdown links/images and URL autolinks. Reference-style
links and raw HTML anchors are rejected rather than silently left unchecked.
Checks establish syntax and local structure, not source truth or runtime behavior.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit


SNAPSHOT = "4ffd86bf788bd5c67034ad7c3fdedaa835e42e20"
REQUIRED = (
    "README.md", "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md",
    "THIRD_PARTY_NOTICES.md", "docs/project.md", "docs/alpha.md",
    "docs/evaluation.md", "docs/research.md", "docs/status.md",
    ".github/ISSUE_TEMPLATE/task.md", ".github/pull_request_template.md",
    ".agents/skills/lantern-task/SKILL.md",
    ".agents/skills/alpha-checkpoint/SKILL.md",
    "tools/check_bootstrap.py",
    "docs/contracts.md",
    "tools/check_app.py",
)
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\n]*)$")
INLINE_CODE = re.compile(r"(`+)(.*?)\1", re.DOTALL)
LINK = re.compile(r"!?\[[^\]\n]*\]\((<[^>\n]+>|[^\s)]+)\)")
AUTOLINK = re.compile(r"<(https?://[^>\s]+)>")


def blocks(text: str) -> tuple[str, list[tuple[int, str, str]], list[str]]:
    """Blank fences/frontmatter in prose while preserving line numbers."""
    lines = text.splitlines(keepends=True)
    prose: list[str] = []
    found: list[tuple[int, str, str]] = []
    errors: list[str] = []
    active: tuple[str, str, int] | None = None
    body: list[str] = []
    frontmatter = bool(lines and lines[0].strip() == "---")
    for number, line in enumerate(lines, 1):
        if frontmatter:
            prose.append("\n")
            if number > 1 and line.strip() == "---":
                frontmatter = False
            continue
        match = FENCE.match(line.rstrip("\r\n"))
        if active:
            marker, language, start = active
            if (match and match[1][0] == marker[0]
                    and len(match[1]) >= len(marker) and not match[2].strip()):
                found.append((start, language, "".join(body)))
                active = None
                body = []
            else:
                body.append(line)
            prose.append("\n")
        elif match:
            active = (match[1], match[2].strip().lower(), number)
            prose.append("\n")
        else:
            prose.append(line)
    if active:
        errors.append(f"line {active[2]}: unclosed code fence")
    if frontmatter:
        errors.append("unclosed frontmatter")
    return "".join(prose), found, errors


def anchors(prose: str) -> set[str]:
    result: set[str] = set()
    for line in prose.splitlines():
        match = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        title = re.sub(r"[`*]", "", match[1]).lower()
        slug = re.sub(r"[^\w\- ]", "", title).replace(" ", "-")
        unique = slug
        index = 0
        while unique in result:
            index += 1
            unique = f"{slug}-{index}"
        result.add(unique)
    return result


def reject_constant(value: str) -> None:
    raise ValueError(f"non-JSON constant {value}")


def check(root: Path, *, layout: bool = True) -> tuple[list[str], set[str], Counter]:
    root = root.resolve()
    errors: list[str] = []
    external: set[str] = set()
    counts: Counter = Counter()
    documents: dict[Path, tuple[str, str]] = {}
    for path in sorted(root.rglob("*.md")):
        if any(part in {".git", "node_modules", ".venv"}
               for part in path.relative_to(root).parts):
            continue
        relative = path.relative_to(root)
        if not path.resolve().is_relative_to(root):
            errors.append(f"{relative}: file resolves outside repository")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError) as exc:
            errors.append(f"{relative}: {exc}")
            continue
        prose, examples, issues = blocks(text)
        documents[path.resolve()] = (text, prose)
        counts["documents"] += 1
        errors.extend(f"{relative}: {item}" for item in issues)
        for line, language, body in examples:
            try:
                if language == "json":
                    json.loads(body, parse_constant=reject_constant)
                    counts["JSON examples"] += 1
                elif language in {"bash", "sh", "shell"}:
                    env = {key: value for key, value in os.environ.items()
                           if key not in {"BASH_ENV", "ENV"}}
                    result = subprocess.run(
                        ["bash", "-n"], input=body, text=True,
                        capture_output=True, timeout=10, env=env,
                    )
                    if result.returncode:
                        raise ValueError(result.stderr.strip())
                    counts["shell examples"] += 1
            except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                errors.append(f"{relative}:{line}: {language}: {exc}")

    for path, (_, prose) in documents.items():
        relative = path.relative_to(root)
        visible = INLINE_CODE.sub("", prose)
        if re.search(r"\[\[[^\n]*?\]\]", visible):
            errors.append(f"{relative}: residual Obsidian link")
        if (re.search(r"!?\[[^\]\n]+\]\[[^\]\n]*\]", visible)
                or re.search(r"^ {0,3}\[[^\]\n]+\]:", visible, re.MULTILINE)):
            errors.append(f"{relative}: reference-style links unsupported; use inline links")
        if re.search(r"<(?:a|img)\b", visible, re.IGNORECASE):
            errors.append(f"{relative}: HTML links unsupported; use Markdown links")
        matches = list(LINK.finditer(visible))
        starts = {match.start() for match in matches}
        for candidate in re.finditer(r"!?\[[^\]\n]*\]\(", visible):
            if candidate.start() not in starts:
                errors.append(f"{relative}: unsupported/malformed inline link; use [label](target)")
        targets = [match[1].strip("<>") for match in matches]
        targets += AUTOLINK.findall(visible)
        for target in targets:
            counts["links"] += 1
            parsed = urlsplit(target)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                external.add(target)
                if (parsed.netloc == "github.com"
                        and parsed.path.startswith("/Losera/Obsidian-Hackathon-Research-LANTERN/")
                        and not parsed.path.startswith(
                            f"/Losera/Obsidian-Hackathon-Research-LANTERN/blob/{SNAPSHOT}/")):
                    errors.append(f"{relative}: research link must pin snapshot: {target}")
                continue
            if parsed.scheme or parsed.netloc or parsed.query:
                errors.append(f"{relative}: unsupported link: {target}")
                continue
            decoded = unquote(parsed.path)
            destination = (path.parent / decoded).resolve() if decoded else path
            if Path(decoded).is_absolute() or not destination.is_relative_to(root):
                errors.append(f"{relative}: link leaves repository: {target}")
            elif not destination.exists():
                errors.append(f"{relative}: missing link target: {target}")
            elif parsed.fragment:
                if destination not in documents:
                    errors.append(f"{relative}: cannot check non-Markdown anchor: {target}")
                elif unquote(parsed.fragment) not in anchors(documents[destination][1]):
                    errors.append(f"{relative}: missing heading anchor: {target}")

    if layout:
        for name in REQUIRED:
            if not (root / name).is_file():
                errors.append(f"missing required bootstrap file: {name}")
        manifest = root / "docs/research.md"
        if manifest in documents:
            text = documents[manifest][0]
            if f"Research snapshot: `{SNAPSHOT}`" not in text:
                errors.append("docs/research.md: missing exact research snapshot metadata")
            imported = re.search(r"^Imported: (\S+)$", text, re.MULTILINE)
            try:
                date.fromisoformat(imported[1] if imported else "")
            except ValueError:
                errors.append("docs/research.md: missing/invalid import date")
            if "Attribution:" not in text:
                errors.append("docs/research.md: missing source attribution metadata")
        policy = documents.get(root / "AGENTS.md", ("", ""))[0]
        sections = re.findall(r"^## (\d+)\.", policy, re.MULTILINE)
        if sections != [str(number) for number in range(1, 14)]:
            errors.append("AGENTS.md: require the 13 numbered engineering policy sections")
        bridge = root / "CLAUDE.md"
        if bridge in documents and documents[bridge][0].strip() != "@AGENTS.md":
            errors.append("CLAUDE.md: require only the canonical @AGENTS.md import")
        for name in ("lantern-task", "alpha-checkpoint"):
            path = root / f".agents/skills/{name}/SKILL.md"
            if path not in documents:
                continue
            text = documents[path][0]
            header = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
            if not header:
                errors.append(f"{path.relative_to(root)}: missing skill frontmatter")
                continue
            fields = dict(re.findall(r"^(name|description): (.+)$", header[1], re.MULTILINE))
            if fields.get("name") != name or not fields.get("description"):
                errors.append(f"{path.relative_to(root)}: require matching name and description")
    return errors, external, counts


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def errors(self, *, layout=False):
        return check(self.root, layout=layout)[0]

    def test_relative_encoded_and_duplicate_anchors(self):
        self.write("A B.md", "# Repeated\n# Repeated\n")
        self.write("README.md", "[one](A%20B.md#repeated) [two](A%20B.md#repeated-1)\n")
        self.assertEqual(self.errors(), [])

    def test_broken_file_and_heading(self):
        self.write("README.md", "# Good\n[missing](absent.md) [heading](#bad)\n")
        self.assertEqual(len(self.errors()), 2)

    def test_underscore_anchor_and_unsupported_link_syntax(self):
        self.write("README.md", "# case_id\n[valid](#case_id)\n")
        self.assertEqual(self.errors(), [])
        self.write("README.md", '[unsupported](absent.md "title")\n')
        self.assertTrue(self.errors())

    def test_json_accepts_valid_rejects_malformed_and_nan(self):
        self.write("README.md", '```json\n{"a": [1, true, null]}\n```\n')
        self.assertEqual(self.errors(), [])
        for bad in ('{"a":}', '{"a": NaN}'):
            with self.subTest(bad=bad):
                self.write("README.md", f"```json\n{bad}\n```\n")
                self.assertTrue(self.errors())

    def test_shell_syntax_checked_without_execution(self):
        marker = self.root / "must-not-exist"
        self.write("README.md", f"```bash\ntouch '{marker}'\n```\n")
        self.assertEqual(self.errors(), [])
        self.assertFalse(marker.exists())
        self.write("README.md", "```bash\nif then\n```\n")
        self.assertTrue(self.errors())

    def test_residual_wiki_and_unsupported_links(self):
        for bad in ("[[Old note]]", "[old][reference]", '<a href="x">x</a>'):
            with self.subTest(bad=bad):
                self.write("README.md", bad)
                self.assertTrue(self.errors())
        self.write("README.md", "`[[example]]`\n```text\n[[example]]\n```\n")
        self.assertEqual(self.errors(), [])

    def test_unclosed_fence_and_frontmatter(self):
        for bad in ("```bash\necho hello\n", "---\nname: unfinished\n"):
            with self.subTest(bad=bad):
                self.write("README.md", bad)
                self.assertTrue(self.errors())

    def test_external_is_not_contacted_and_vault_link_is_pinned(self):
        self.write("README.md", "[offline](https://nonexistent.invalid/no-network)\n")
        self.assertEqual(self.errors(), [])
        self.write("README.md", "[vault](https://github.com/Losera/Obsidian-Hackathon-Research-LANTERN/blob/main/README.md)\n")
        self.assertTrue(self.errors())

    def test_rejects_path_escape(self):
        self.write("README.md", "[escape](../outside.md)\n")
        self.assertTrue(any("leaves repository" in error for error in self.errors()))

    def test_layout_and_missing_snapshot(self):
        self.write("docs/research.md", "Imported: 2026-11-07\nAttribution: author\n")
        errors = self.errors(layout=True)
        self.assertTrue(any("snapshot metadata" in error for error in errors))
        self.assertTrue(any("required bootstrap file" in error for error in errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run temporary-fixture tests")
    parser.add_argument("--list-external", action="store_true", help="list URLs; do not contact them")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(CheckerTests)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    errors, external, counts = check(args.root)
    if args.list_external:
        print("\n".join(sorted(external)))
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    summary = ", ".join(f"{value} {key}" for key, value in counts.items())
    print(f"{'FAIL' if errors else 'PASS'}: {summary}; {len(external)} external URLs not fetched")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

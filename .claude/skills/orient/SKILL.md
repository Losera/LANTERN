---
name: orient
description: Session-start orientation for LANTERN — live repository state plus a short cold-entry briefing a human can read in under a minute. Run before substantive work in a fresh session or when returning after time away. Trigger on "where are we", "what's the status", "catch me up", "brief me", "/orient".
---

# LANTERN orientation

Produce a cold-entry briefing. Change nothing: no edits, no commits, no pushes,
no issue comments. This skill grants no architecture, commit, or integration
authority.

## 1. Read the live state

Run these together. They are read-only.

```bash
git rev-parse --show-toplevel
git branch --show-current
git status --short --branch --untracked-files=all
git log --oneline -8
git diff --stat
git diff --cached --stat
git worktree list
gh pr list --state open --limit 10
gh issue list --state open --limit 40
```

## 2. Read only what the state demands

Minimum: `README.md` for what the project is, `docs/status.md` for the dated
verification record. Read further only when the live state points there — a
modified file, an active task in recent commits, a named open question. Do not
read the Alpha or evaluation references unless the current task touches them.

If the working tree is dirty, inspect what actually changed before describing it.
For a reformat or a mechanical-looking diff, verify the claim rather than
asserting it: compare `ast.dump` of both versions for Python, and say which
method you used.

## 3. Trust rules specific to this repository

These exist because each one has already misled a session.

- **`docs/status.md` is part dated history.** Sections below the top are
  checkpoints that were true when written. Verify any claim you intend to repeat
  — a "still broken" or "still present" note may be stale.
- **The issue board overstates what is open.** Issue 65 tracks exactly this.
  Several issues describe work the repository already contains. Check the code
  before reporting an issue as live work.
- **GitHub Issues still own live task state**, with the caveat above. `docs/` owns
  decisions and verification records.
- **Never report a check as passing unless it ran this session.** Separate three
  things: what you ran, what CI reports, and what a document claims. Name the
  source.
- **Never present a local, fixture, or synthetic run as an Alpha or GPU result.**
  Correctness is `unknown` on every record; two seams must still refuse.
- **Do not delete or prune branches during orientation.** Some branches are
  deliberate retention artifacts, and one holds a commit unreachable from `main`.

## 4. Return the briefing

Human-readable means short and scannable. One screen. Target 150 words, hard
ceiling 250. Prose paragraphs, nested bullets, and tables are wrong here — the
reader wants to reorient, not to study.

Exactly this shape:

```
**LANTERN** · `<branch>` · <clean | N modified, N untracked>

**State** — one line on where the work actually stands.
**Last work** — the most recent commit or session, one line.
**Verified** — what is established, and by whom: ran this session, CI, or claimed.
**Blocked on** — the single thing most in the way.
**Next** — one concrete action, or up to three labelled as suggestions.
```

Then at most three `Risk:` lines, only for things that would cost real time or
are irreversible. Then one closing line naming what you can expand on. Those
three parts are the whole briefing; nothing else belongs in it.

Rules for the text:

- **No unsolicited Markdown.** Never deliver a briefing as a file. No `BRIEFING.md`,
  no summary note, no published artifact, no new vault page unless the human asked
  for one in this session. A briefing is terminal output; an unrequested document is
  clutter that a later reader mistakes for a record. The same applies to the output
  itself — keep it to the shape above and add no headings, tables, nested bullets, or
  horizontal rules on your own initiative.
- One fact per line. If a line needs a comma-spliced second clause, cut it.
- Numbers over adjectives: "5 PRs green, unreviewed since Nov 9" beats
  "several PRs awaiting review".
- Name a file, issue, or SHA where the reader would otherwise have to search.
- If no task is recorded or inferable, say so plainly and label any suggestion as
  a suggestion. Do not invent an active task.
- State one important uncertainty rather than hedging every line.
- Offer the detail; do not deliver it unasked. The closing line described above is
  where that offer goes, and it is the only place it goes.

## Attribution

Adapted from this machine's `soundfetch-orient` skill, generalized to LANTERN's
evidence rules and given an explicit output budget.

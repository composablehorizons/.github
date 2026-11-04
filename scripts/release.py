"""Changelog, git and workflow-output helpers shared by the release scripts."""

import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

UNRELEASED = re.compile(r"^## (\[)?Unreleased(\])?[ \t]*\n", re.MULTILINE)


def run(*args, cwd=None):
    return subprocess.check_output(args, text=True, cwd=cwd).strip()


def fail(message):
    print(f"::error::{message}")
    sys.exit(1)


def section_notes(changelog, version):
    match = re.search(
        rf"^## \[?{re.escape(version)}\]? - \d{{4}}-\d{{2}}-\d{{2}}[ \t]*\n(.*?)(?=^## |\Z)",
        changelog,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def date_unreleased(changelog, version):
    match = UNRELEASED.search(changelog)
    if not match:
        fail("CHANGELOG.md has no Unreleased section.")
    following = re.compile(r"^## ", re.MULTILINE).search(changelog, match.end())
    end = following.start() if following else len(changelog)
    notes = changelog[match.end():end].strip()
    if not notes:
        fail("The Unreleased section of CHANGELOG.md is empty, so there is nothing to release.")
    bracketed = match.group(1) is not None
    date = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    unreleased = "## [Unreleased]" if bracketed else "## Unreleased"
    heading = f"## [{version}] - {date}" if bracketed else f"## {version} - {date}"
    dated = f"{unreleased}\n\n{heading}\n\n{notes}\n\n"
    return changelog[:match.start()] + dated + changelog[end:].lstrip("\n"), notes


def changelog_text():
    path = Path("CHANGELOG.md")
    if not path.exists():
        fail("The repository has no CHANGELOG.md.")
    return path.read_text()


def output(**values):
    path = os.environ.get("GITHUB_OUTPUT")
    lines = "".join(f"{key}={value}\n" for key, value in values.items())
    if path:
        with open(path, "a") as file:
            file.write(lines)
    print(lines, end="")

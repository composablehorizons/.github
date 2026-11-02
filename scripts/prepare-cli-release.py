#!/usr/bin/env python3
"""Prepares a CLI release for the shared CLI release workflow.

Run from the CLI's root, where CHANGELOG.md and .goreleaser.yaml live. The version lives
only in vX.Y.Z tags; GoReleaser stamps it into the binaries.

Picks the version to release:
- The latest vX.Y.Z tag has no published GitHub Release: retry releasing that tag.
- Otherwise: bump the latest tag (v0.0.0 when there is none) by patch, minor or major.

For a new version, it dates the Unreleased changelog section, starts a fresh one, and
creates the release commit and an annotated tag. An empty Unreleased section stops the
release.

Writes `version`, `tag` and `mode` (new or retry) to $GITHUB_OUTPUT when set, and the
release notes to the path given by RELEASE_NOTES_FILE. Needs GH_TOKEN for the gh CLI.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from release import changelog_text, date_unreleased, fail, output, run, section_notes

TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def latest_tag():
    for tag in run("git", "tag", "--list", "v*", "--sort=-v:refname").splitlines():
        if TAG.match(tag):
            return tag
    return None


def published(tag):
    result = subprocess.run(
        ["gh", "release", "view", tag, "--json", "isDraft", "--jq", ".isDraft"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "false"


def bumped(tag, bump):
    major, minor, patch = (int(part) for part in TAG.match(tag or "v0.0.0").groups())
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def main():
    bump = sys.argv[1] if len(sys.argv) > 1 else ""
    if bump not in ("patch", "minor", "major"):
        fail("Choose patch, minor or major.")
    if run("git", "status", "--porcelain"):
        fail("The release needs a clean working tree.")
    notes_file = Path(os.environ.get("RELEASE_NOTES_FILE", "release-notes.md"))

    previous = latest_tag()
    if previous and not published(previous):
        version = previous[1:]
        run("git", "checkout", "--quiet", "--detach", previous)
        notes = section_notes(Path("CHANGELOG.md").read_text(), version)
        if not notes:
            fail(f"{previous} has no dated section in CHANGELOG.md.")
        notes_file.write_text(notes + "\n")
        print(f"{previous} has no published GitHub Release; retrying it.")
        output(version=version, tag=previous, mode="retry")
        return

    version = bumped(previous, bump)
    tag = f"v{version}"
    changelog, notes = date_unreleased(changelog_text(), version)
    Path("CHANGELOG.md").write_text(changelog)
    notes_file.write_text(notes + "\n")
    run("git", "add", "CHANGELOG.md")
    run("git", "commit", "--quiet", "-m", f"Release {version}")
    run("git", "tag", "-a", tag, "-m", f"Release {version}")
    output(version=version, tag=tag, mode="new")


if __name__ == "__main__":
    main()

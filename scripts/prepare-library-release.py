#!/usr/bin/env python3
"""Prepares a library release for the shared release workflow.

Run from the library's root, where package.yml, CHANGELOG.md and the Gradle wrapper live.

Picks the version to release:
- package.yml holds a version without a vX.Y.Z tag: release that version as-is
  (a first release, or a version prepared by hand). The bump argument is ignored.
- That version is tagged but missing from Maven Central: retry publishing the tag.
- Otherwise: bump package.yml with `kpm version <bump>`.

For a new version, it dates the Unreleased changelog section, starts a fresh one, updates
the README's dependency line, and creates the release commit and an annotated tag. An
empty Unreleased section stops the release.

Writes `version`, `tag` and `mode` (new or retry) to $GITHUB_OUTPUT when set, and the
release notes to the path given by RELEASE_NOTES_FILE.
"""

import datetime
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

UNRELEASED = re.compile(r"^## (\[)?Unreleased(\])?[ \t]*\n", re.MULTILINE)


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def fail(message):
    print(f"::error::{message}")
    sys.exit(1)


def package_field(name):
    match = re.search(rf"^{name}:\s*(\S+)\s*$", Path("package.yml").read_text(), re.MULTILINE)
    if not match:
        fail(f"package.yml has no {name}.")
    return match.group(1)


def published(group, artifact, version):
    base = os.environ.get("MAVEN_REPOSITORY_URL", "https://repo1.maven.org/maven2")
    url = f"{base}/{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}.pom"
    try:
        with urllib.request.urlopen(url, timeout=30):
            return True
    except (urllib.error.HTTPError, urllib.error.URLError, FileNotFoundError):
        return False


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


def update_readme(group, artifact, version):
    readme = Path("README.md")
    if not readme.exists():
        return False
    text, count = re.subn(
        rf"({re.escape(group)}:{re.escape(artifact)}:)[^\s\"')]+",
        lambda m: m.group(1) + version,
        readme.read_text(),
    )
    if count:
        readme.write_text(text)
    else:
        print(f"::warning::README.md has no {group}:{artifact}:<version> line to update.")
    return count > 0


def changelog_text():
    path = Path("CHANGELOG.md")
    if not path.exists():
        fail("The library has no CHANGELOG.md.")
    return path.read_text()


def output(**values):
    path = os.environ.get("GITHUB_OUTPUT")
    lines = "".join(f"{key}={value}\n" for key, value in values.items())
    if path:
        with open(path, "a") as file:
            file.write(lines)
    print(lines, end="")


def main():
    bump = sys.argv[1] if len(sys.argv) > 1 else ""
    if bump not in ("patch", "minor", "major"):
        fail("Choose patch, minor or major.")
    if run("git", "status", "--porcelain"):
        fail("The release needs a clean working tree.")

    group, artifact = package_field("groupId"), package_field("artifactId")
    version = run("kpm", "version")
    tag = f"v{version}"
    notes_file = Path(os.environ.get("RELEASE_NOTES_FILE", "release-notes.md"))

    if run("git", "tag", "--list", tag):
        if not published(group, artifact, version):
            run("git", "checkout", "--quiet", "--detach", tag)
            notes = section_notes(Path("CHANGELOG.md").read_text(), version)
            if not notes:
                fail(f"{tag} has no dated section in CHANGELOG.md.")
            notes_file.write_text(notes + "\n")
            print(f"{tag} exists but {group}:{artifact}:{version} is not on Maven Central; retrying it.")
            output(version=version, tag=tag, mode="retry")
            return
        date_unreleased(changelog_text(), version)  # stop on an empty changelog before bumping
        run("kpm", "version", bump, "--no-git-tag-version")
        version = run("kpm", "version")
        tag = f"v{version}"
        if run("git", "tag", "--list", tag):
            fail(f"{tag} already exists; update package.yml before releasing.")

    changelog, notes = date_unreleased(changelog_text(), version)
    Path("CHANGELOG.md").write_text(changelog)
    notes_file.write_text(notes + "\n")

    files = ["package.yml", "CHANGELOG.md"]
    if update_readme(group, artifact, version):
        files.append("README.md")
    run("git", "add", *files)
    run("git", "commit", "--quiet", "-m", f"Release {version}")
    run("git", "tag", "-a", tag, "-m", f"Release {version}")
    output(version=version, tag=tag, mode="new")


if __name__ == "__main__":
    main()

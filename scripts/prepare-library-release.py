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

import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from release import changelog_text, date_unreleased, fail, output, run, section_notes


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

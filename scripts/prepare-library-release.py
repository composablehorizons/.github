#!/usr/bin/env python3
"""Prepares a library release for the shared release workflow.

Run from the repository root, where CHANGELOG.md, README.md and the Gradle wrapper live.
The library's package.yml is in PACKAGE_DIRECTORY (default: the root), such as "library"
when the library is a module next to a demo app.

Packages listed in EXTRA_PACKAGES (directories, separated by spaces) are released with the
root package at the same version, such as a library's Gradle plugin. GRADLE_PLUGIN_ID names a
plugin whose `id("...") version "..."` line in the README is updated with the version.

Picks the version to release:
- package.yml holds a version without a vX.Y.Z tag: release that version as-is
  (a first release, or a version prepared by hand). The bump argument is ignored.
- That version is tagged but a package is missing from Maven Central: retry publishing the tag.
- Otherwise: bump package.yml with `kpm version <bump>`.

For a new version, it dates the Unreleased changelog section, starts a fresh one, updates
the README's dependency line, and creates the release commit and an annotated tag. An
empty Unreleased section stops the release.

Writes `version`, `tag`, `mode` (new or retry) and `publish` (the package directories to
publish) to $GITHUB_OUTPUT when set, and the release notes to the path given by
RELEASE_NOTES_FILE.
"""

import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from release import changelog_text, date_unreleased, fail, output, run, section_notes


def package_field(name, directory="."):
    path = Path(directory, "package.yml")
    match = re.search(rf"^[ \t]*{name}:\s*(\S+)\s*$", path.read_text(), re.MULTILINE)
    if not match:
        fail(f"{path} has no {name}.")
    return match.group(1)


def coordinates(directory):
    return package_field("groupId", directory), package_field("artifactId", directory)


def published(group, artifact, version):
    base = os.environ.get("MAVEN_REPOSITORY_URL", "https://repo1.maven.org/maven2")
    url = f"{base}/{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}.pom"
    try:
        with urllib.request.urlopen(url, timeout=30):
            return True
    except (urllib.error.HTTPError, urllib.error.URLError, FileNotFoundError):
        return False


def update_readme(pattern, description, version, required=True):
    readme = Path("README.md")
    if not readme.exists():
        return False
    text, count = re.subn(pattern, lambda m: m.group(1) + version, readme.read_text())
    if count:
        readme.write_text(text)
    elif required:
        print(f"::warning::README.md has no {description} line to update.")
    return count > 0


def update_readme_dependency(group, artifact, version, required=True):
    pattern = rf"({re.escape(group)}:{re.escape(artifact)}:)[^\s\"')]+"
    return update_readme(pattern, f"{group}:{artifact}:<version>", version, required)


def update_readme_plugin(plugin_id, version):
    pattern = rf"(id\(\"{re.escape(plugin_id)}\"\)\s+version\s+\")[^\"]+"
    return update_readme(pattern, f'id("{plugin_id}") version "<version>"', version)


def main():
    bump = sys.argv[1] if len(sys.argv) > 1 else ""
    if bump not in ("patch", "minor", "major"):
        fail("Choose patch, minor or major.")
    if run("git", "status", "--porcelain"):
        fail("The release needs a clean working tree.")

    main_package = os.environ.get("PACKAGE_DIRECTORY", "").strip() or "."
    packages = [main_package] + os.environ.get("EXTRA_PACKAGES", "").split()
    plugin_id = os.environ.get("GRADLE_PLUGIN_ID", "").strip()
    version = run("kpm", "version", cwd=main_package)
    tag = f"v{version}"
    notes_file = Path(os.environ.get("RELEASE_NOTES_FILE", "release-notes.md"))

    if run("git", "tag", "--list", tag):
        missing = [d for d in packages if not published(*coordinates(d), version)]
        if missing:
            run("git", "checkout", "--quiet", "--detach", tag)
            notes = section_notes(Path("CHANGELOG.md").read_text(), version)
            if not notes:
                fail(f"{tag} has no dated section in CHANGELOG.md.")
            notes_file.write_text(notes + "\n")
            names = ", ".join(":".join(coordinates(d)) for d in missing)
            print(f"{tag} exists but {names} is not on Maven Central at {version}; retrying it.")
            output(version=version, tag=tag, mode="retry", publish=" ".join(missing))
            return
        date_unreleased(changelog_text(), version)  # stop on an empty changelog before bumping
        run("kpm", "version", bump, "--no-git-tag-version", cwd=main_package)
        version = run("kpm", "version", cwd=main_package)
        tag = f"v{version}"
        if run("git", "tag", "--list", tag):
            fail(f"{tag} already exists; update package.yml before releasing.")

    changelog, notes = date_unreleased(changelog_text(), version)
    Path("CHANGELOG.md").write_text(changelog)
    notes_file.write_text(notes + "\n")

    files = ["CHANGELOG.md"]
    readme_updated = False
    for directory in packages:
        if directory != main_package:
            run("kpm", "version", version, "--no-git-tag-version", cwd=directory)
        files.append(str(Path(directory, "package.yml")))
        readme_updated |= update_readme_dependency(*coordinates(directory), version, required=directory == main_package)
    if plugin_id:
        readme_updated |= update_readme_plugin(plugin_id, version)
    if readme_updated:
        files.append("README.md")
    run("git", "add", *files)
    run("git", "commit", "--quiet", "-m", f"Release {version}")
    run("git", "tag", "-a", tag, "-m", f"Release {version}")
    output(version=version, tag=tag, mode="new", publish=" ".join(packages))


if __name__ == "__main__":
    main()

# composablehorizons/.github

Shared GitHub Actions for Composables libraries.

## Library release

`.github/workflows/library-release.yml` releases a library to Maven Central with KPM. A library calls it from its own Release workflow:

```yaml
name: Release

on:
  workflow_dispatch:
    inputs:
      bump:
        description: Which part of the version to increase
        required: true
        type: choice
        options: [patch, minor, major]

jobs:
  release:
    uses: composablehorizons/.github/.github/workflows/library-release.yml@main
    with:
      bump: ${{ inputs.bump }}
      test-command: jvmTest testAndroidHostTest iosSimulatorArm64Test
      android-packages: 'platforms;android-37.0 build-tools;37.0.0'
    permissions:
      contents: write
    secrets: inherit
```

Run **Release** in the library's Actions tab and pick patch, minor or major. The workflow:

1. Picks the version from `package.yml`. An untagged version there is released as-is (a first release or a version prepared by hand); otherwise KPM bumps it.
2. Dates the `Unreleased` section of `CHANGELOG.md`, starts a fresh one, and updates the README's `group:artifact:version` line. An empty `Unreleased` section stops the release.
3. Commits `Release X.Y.Z` and tags `vX.Y.Z`.
4. Runs `test-command` and `publishToMavenLocal` to build every publication.
5. Pushes the commit and tag, publishes with `kpm publish`, and publishes the GitHub Release with the changelog section as its text.

If publishing fails after the tag was pushed, run Release again: when the tagged version is not on Maven Central yet, it retries that tag instead of bumping.

Requirements in the library: `package.yml` with `groupId`, `artifactId` and `version`, a `CHANGELOG.md` with an `Unreleased` section, the Gradle wrapper at the root, and access to the `maven-central` environment and the organization secrets `OSSRH_USERNAME`, `OSSRH_PASSWORD`, `SIGNING_KEY_ID`, `SIGNING_PASSWORD` and `SIGNING_KEY`.

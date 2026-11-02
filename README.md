# composablehorizons/.github

Shared GitHub Actions for Composables libraries and CLIs.

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
5. Pushes the commit and tag, publishes with `kpm publish`, waits until Maven Central has validated the deployment (a rejected release fails the run), and publishes the GitHub Release with the changelog section as its text.

If publishing fails after the tag was pushed, run Release again: when the tagged version is not on Maven Central yet, it retries that tag instead of bumping.

Requirements in the library: the KPM Gradle plugin 0.6.0 or later (older versions skip the validation wait), `package.yml` with `groupId`, `artifactId` and `version`, a `CHANGELOG.md` with an `Unreleased` section, the Gradle wrapper at the root, and access to the `maven-central` environment and the organization secrets `OSSRH_USERNAME`, `OSSRH_PASSWORD`, `SIGNING_KEY_ID`, `SIGNING_PASSWORD` and `SIGNING_KEY`.

## CLI release

`.github/workflows/cli-release.yml` releases a Go CLI as prebuilt binaries on GitHub Releases with GoReleaser. A CLI calls it from its own Release workflow:

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
    uses: composablehorizons/.github/.github/workflows/cli-release.yml@main
    with:
      bump: ${{ inputs.bump }}
    permissions:
      contents: write
    secrets:
      HOMEBREW_TAP_DEPLOY_KEY: ${{ secrets.HOMEBREW_TAP_DEPLOY_KEY }}
```

Run **Release** in the CLI's Actions tab and pick patch, minor or major. The workflow:

1. Bumps the latest `vX.Y.Z` tag, or `v0.0.0` when there is none. The version lives only in tags.
2. Dates the `Unreleased` section of `CHANGELOG.md` and starts a fresh one. An empty `Unreleased` section stops the release.
3. Commits `Release X.Y.Z` and tags `vX.Y.Z`.
4. Runs `test-command` (default `go vet ./... && go test ./...`).
5. Pushes the commit and tag, then GoReleaser builds every binary and publishes the GitHub Release with the changelog section as its text.

If publishing fails after the tag was pushed, run Release again: when the latest tag has no published GitHub Release, it retries that tag instead of bumping.

Requirements in the CLI: `go.mod` at the root, a `CHANGELOG.md` with an `Unreleased` section, and a `.goreleaser.yaml` that sets `release.replace_existing_artifacts: true` so retries can replace partial uploads. Publishing to GitHub Releases needs no secrets. A CLI that publishes a Homebrew cask to `alexstyl/homebrew-tap` from `.goreleaser.yaml` needs the `HOMEBREW_TAP_DEPLOY_KEY` secret, the private half of a deploy key with write access to the tap, passed explicitly as above: `secrets: inherit` does not reach a workflow in another organization. The release fails before publishing when the key is missing.

Do not disable GoReleaser's `changelog`: that also drops the release notes taken from `CHANGELOG.md`.

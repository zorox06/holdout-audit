# Releasing

Releases are published through GitHub Actions OIDC; no PyPI API token is stored in this repository.

The PyPI trusted publisher must match these values exactly:

| Field | Value |
| --- | --- |
| PyPI project | `spliv` |
| GitHub owner | `zorox06` |
| Repository | `holdout-audit` |
| Workflow filename | `publish.yml` |
| GitHub environment | `pypi` |

## Release sequence

1. Update the version in `pyproject.toml`, `holdout_audit/__init__.py`, the JSON tool version in `core.py`, and CLI version in `cli.py`. Update the report brand, pinned notebook install, and verify-release workflow version if needed.
2. Run the test suite and verify the full GitHub Actions test matrix.
3. Commit the release, create a tag exactly matching `v<package-version>`, and push that tag. The publishing workflow checks this match before building.
4. Verify the publishing workflow and the actual PyPI release page. Once a PyPI version is published, its distribution files cannot be replaced; fixes require a new version.
5. Create the corresponding GitHub release with concise notes and distribution files.

The workflow can be manually dispatched on a release tag if required. Dispatching it on a branch fails the version check. OIDC permission is confined to the publishing job.

For a new project, use a pending trusted publisher under the PyPI account's publishing settings. Adding it does not reserve the package name. Confirm the workflow and repository identity before granting publishing authority.

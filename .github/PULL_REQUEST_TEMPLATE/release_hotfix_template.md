---
name: "Release or Hotfix Pull Request"
about: Propose changes for a release (e.g., merging a release branch to main) or a critical hotfix.
title: "chore: Release vX.Y.Z"
labels: "release, hotfix"
assignees: ""
---

## Description

<!--
Please include a summary of the change.
For releases, summarize the key features, bug fixes, and breaking changes included.
For hotfixes, describe the critical issue being addressed.
-->

## Release/Hotfix Details

- **Target Version**: (e.g., `v1.2.0`)
- **Type**: (e.g., `Major Release`, `Minor Release`, `Patch Release`, `Security Hotfix`)
- **Key Changes**:
- [ ] New Features (if applicable)
- [ ] Bug Fixes (if applicable)
- [ ] Breaking Changes (if applicable, with migration path)
- [ ] Security Fixes (if applicable, with CVE)

## Related Issues/PRs

<!-- List any relevant issues or pull requests that this release/hotfix addresses or is dependent on. -->

## Breaking Change

<!--
Does this PR introduce a breaking change for a hotfix, or finalize breaking changes for a release?
- If YES, please describe the impact and migration path for existing applications.
- If NO, please indicate N/A.
-->

- [ ] Yes
- [ ] No
(If Yes, please describe the impact and migration path below):

**Applicable `rhosocial-activerecord` Version Range:**
<!-- Specify the version range of rhosocial-activerecord that this change is compatible with (e.g., ">=1.0.0,<2.0.0"). -->


## Testing

<!--
Please describe the tests that you ran to verify your changes.
For releases, confirm all CI checks passed on the release branch.
For hotfixes, describe the specific tests performed to validate the fix.
-->

- [ ] All CI checks passed on the source branch (e.g., `release/vX.Y.Z` or `hotfix/ar-XXX`).
- [ ] Specific tests for this hotfix have been run and passed.

**Test Plan:**
<!-- e.g., "Ran full test suite on release/v1.2.0 branch", or "Executed `pytest tests/rhosocial/activerecord_test/bug/critical_fix.py`" -->


## Checklist

<!--
Go over all the following points, and put an `x` in all the boxes that apply.
-->

- [ ] My changes follow the project's version control guidelines.
- [ ] I have updated the `CHANGELOG.md` using `towncrier build` (for releases).
- [ ] All necessary documentation (e.g., release notes, migration guides) has been prepared or updated.
- [ ] I have confirmed all CI checks have passed on the target branch after merging (post-merge verification).

## Additional Notes

<!-- Any additional information, context, or questions for reviewers. -->

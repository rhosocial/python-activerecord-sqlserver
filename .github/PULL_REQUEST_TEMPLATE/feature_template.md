---
name: "Feature Pull Request"
about: Propose a new feature for the rhosocial-activerecord SQL Server backend, targeting a pre-release branch (e.g., release/vX.Y.Z).
title: "feat(<scope>): <description>"
labels: "enhancement"
assignees: ""
---

## Description

<!--
Please include a summary of the new feature and its motivation.
Describe the problem it solves or the new capability it provides.
List any dependencies that are required for this change.
-->

Adds # (issue)

## Type of change

<!--
Please delete options that are not relevant.
Remember to follow the Conventional Commits specification.
-->

- [ ] `feat`: A new feature
- [ ] `docs`: Documentation only changes (if related to the new feature)
- [ ] `perf`: A code change that improves performance (if part of the feature)
- [ ] `test`: Adding missing tests or correcting existing tests (for the new feature)
- [ ] `chore`: Changes to the build process or auxiliary tools and libraries suchs as documentation generation (if related to the new feature)
- [ ] `ci`: Changes to our CI configuration files and scripts (if related to the new feature)
- [ ] `build`: Changes that affect the build system or external dependencies (if related to the new feature)
- [ ] `revert`: Reverts a previous commit

## Breaking Change

<!--
Does this PR introduce a breaking change?
- If YES, please describe the impact and migration path for existing applications.
- If NO, please indicate N/A.
-->

- [ ] Yes, for end-users (backward-incompatible API changes)
- [ ] Yes, for backend developers (internal architectural changes that may affect custom implementations)
- [ ] No breaking changes
(If Yes, please describe the impact and migration path below):

**Impact on End-Users:**
<!-- Describe backward-incompatible changes for typical end-user applications consuming the public API. If none, state "No backward-incompatible changes are expected for typical end-user applications." -->

**Impact on Backend Developers (Custom Implementations):**
<!-- Describe backward-incompatible changes for developers with custom backend implementations or those directly interacting with internal mechanisms. If none, state "No backward-incompatible changes are expected for backend developers using custom implementations." -->


## Related Repositories/Packages

<!--
If this change affects other repositories in the rhosocial-activerecord ecosystem (e.g., core, testsuite, or another backend),
please list them and describe the coordinated changes needed.
-->


## Testing

<!--
Please describe the tests that you ran to verify your changes. Provide instructions so we can reproduce.
Also, list any relevant configuration details (e.g., SQL Server version, Python version).
-->

- [ ] I have added new tests to cover my changes.
- [ ] I have updated existing tests to reflect my changes.
- [ ] All existing tests pass.
- [ ] This change has been tested on [specify backend/DB versions].

**Test Plan:**
<!-- e.g., "Ran `pytest tests/rhosocial/activerecord_test/feature/my_new_feature.py`" -->


## Checklist

<!--
Go over all the following points, and put an `x` in all the boxes that apply.
If you're unsure about any of these, don't hesitate to ask. We're here to help!
-->

- [ ] My code follows the project's code style guidelines in `.claude/code_style.md`.
- [ ] I have performed a self-review of my own code.
- [ ] I have commented my code, particularly in hard-to-understand areas.
- [ ] I have made corresponding changes to the documentation (Docstrings, `README.md`, etc.).
- [ ] My changes generate no new warnings.
- [ ] I have added a Changelog fragment as described in `.claude/version_control.md` (`changelog.d/<issue_number>.<type>.md`).
- [ ] I have verified that my changes do not introduce SQL injection vulnerabilities.
- [ ] I have checked for potential performance regressions.

## Additional Notes

<!-- Any additional information, context, or questions for reviewers. -->

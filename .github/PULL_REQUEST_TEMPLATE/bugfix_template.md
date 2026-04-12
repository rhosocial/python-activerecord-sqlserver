---
name: "Bugfix Pull Request"
about: Propose a bug fix for the rhosocial-activerecord ecosystem, targeting a pre-release branch (e.g., release/vX.Y.Z).
title: "fix(<scope>): <description>"
labels: "bug, bugfix"
assignees: ""
---

## Description

<!--
Please include a summary of the bug and the fix.
Describe the impact of the bug and why this fix addresses it.
-->

Fixes # (issue)

## Reproduction Steps

<!--
Please provide clear and detailed steps to reproduce the bug.
This is crucial for verifying the fix. Include code snippets, configurations,
and expected vs. actual behavior.
-->

1.
2.
3.

## Type of change

<!--
Please delete options that are not relevant.
Remember to follow the Conventional Commits specification.
-->

- [ ] `fix`: A bug fix
- [ ] `docs`: Documentation only changes (if related to the bug or fix)
- [ ] `test`: Adding missing tests or correcting existing tests (for the bug or fix)
- [ ] `refactor`: A code change that neither fixes a bug nor adds a feature (if part of the fix)
- [ ] `perf`: A code change that improves performance (if part of the fix)
- [ ] `chore`: Changes to the build process or auxiliary tools and libraries suchs as documentation generation (if related to the bug or fix)
- [ ] `ci`: Changes to our CI configuration files and scripts (if related to the bug or fix)
- [ ] `build`: Changes that affect the build system or external dependencies (if related to the bug or fix)
- [ ] `revert`: Reverts a previous commit

## Breaking Change

<!--
Does this PR introduce a breaking change?
- If YES, please describe the impact and migration path for existing applications.
- If NO, please indicate N/A.
-->

- [ ] Yes
- [ ] No
(If Yes, please describe the impact and migration path below):

**Applicable `rhosocial-activerecord` Version Range:**
<!-- Specify the version range of rhosocial-activerecord that this change is compatible with (e.g., ">=1.0.0,<2.0.0"). -->



## Related Repositories/Packages

<!--
If this change affects other repositories in the rhosocial-activerecord ecosystem (e.g., testsuite, mysql, postgres),
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
<!-- e.g., "Ran `pytest tests/rhosocial/activerecord_test/bug/my_bug_fix.py`" -->


## Checklist

<!--
Go over all the following points, and put an `x` in all the boxes that apply.
If you're unsure about any of these, don't hesitate to ask. We're here to help!
-->

- [ ] My code follows the project's code style guidelines.
- [ ] I have performed a self-review of my own code.
- [ ] I have commented my code, particularly in hard-to-understand areas.
- [ ] I have made corresponding changes to the documentation (Docstrings, `README.md`, etc.).
- [ ] My changes generate no new warnings.
- [ ] I have added a Changelog fragment (`changelog.d/<issue_number>.<type>.md`).
- [ ] I have verified that my changes do not introduce SQL injection vulnerabilities.
- [ ] I have checked for potential performance regressions.

## Additional Notes

<!-- Any additional information, context, or questions for reviewers. -->

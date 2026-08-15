Create new feature following project standards

Create a new feature for rhosocial-activerecord following the project's strict standards.

## Feature Creation Checklist

### 1. Design Phase
- Review existing features in .claude/feature_points.md
- Determine feature category: query/backend/field/relation/mixin
- Decide if async API is needed (usually yes for parity)

### 2. Implementation Phase
- Create sync version: src/rhosocial/activerecord/{category}/{feature}.py
- Create async version: src/rhosocial/activerecord/{category}/async_{feature}.py
- Ensure method names are IDENTICAL between sync/async (only add Async prefix to class name)
- Document with "asynchronously" in async version's first docstring sentence
- Keep field/method order identical between versions

### 3. Testing Phase
- Add tests following Testsuite architecture
- Use Provider pattern for fixtures
- Ensure sync/async test parity (fixtures, test classes, methods)
- Share SQL schema files between sync/async tests

### 4. Documentation
- Create changelog.d/{issue}.{type}.md fragment
- Update relevant documentation

Ask the user:
1. What is the feature name (snake_case)?
2. What category does it belong to?
3. Does it need async API?
4. What issue number should be referenced?

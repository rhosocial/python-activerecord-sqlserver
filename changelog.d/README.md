# Changelog Fragments

We use Towncrier to manage our changelog. Each significant change should have a corresponding fragment file.

## Creating a Fragment

1. **Filename**: `{issue_number}.{type}.md`
   - Example: `123.added.md`

2. **Types**:
   - `security` - Security fixes (always significant)
   - `removed` - Removed features (breaking changes)
   - `deprecated` - Deprecation notices
   - `added` - New features
   - `changed` - Behavior changes
   - `fixed` - Bug fixes
   - `performance` - Performance improvements
   - `docs` - Documentation (significant changes only)
   - `internal` - Internal changes (optional)

3. **Content**:
   - Write in past tense
   - Be specific but concise
   - Focus on user impact
   - One change per fragment

## Fragment Lifecycle

- **Created**: When feature/fix branch is created
- **Merged**: Fragment merges with the code
- **Compiled**: During final release (not pre-releases)
- **Deleted**: Automatically removed after compilation
- **Abandoned**: Manually deleted if feature is abandoned

## Good Examples

```markdown
<!-- 123.added.md -->
Added support for SQL Server JSON operations in query builder.
```

```markdown
<!-- 456.fixed.md -->
Fixed connection leak that occurred when SQL Server connections were not properly released after query timeout.
```

## Commands

```bash
# Preview changelog
towncrier build --draft --version X.Y.Z

# Build changelog (removes fragments)
towncrier build --version X.Y.Z --yes
```

## Review Checklist

Before committing your fragment:

- [ ] Filename follows `{issue}.{type}.md` format
- [ ] Content is in past tense
- [ ] Describes user impact, not implementation
- [ ] One logical change per fragment
- [ ] Appropriate type selected

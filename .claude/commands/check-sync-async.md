Check sync/async API parity

Check that sync and async APIs are properly paired following the parity rules.

## Parity Rules to Verify

1. **Class Names**: Async version adds Async prefix
   - BaseActiveRecord → AsyncBaseActiveRecord
   - ActiveQuery → AsyncActiveQuery

2. **Method Names**: Remain IDENTICAL (no _async suffix)
   - def save(self) → async def save(self)
   - NOT: async def save_async(self)

3. **Docstrings**: Async version notes "asynchronously" in first sentence

4. **Field Order**: Declaration order must match exactly

5. **Testing Parity**:
   - Fixtures: order_fixtures → async_order_fixtures
   - Test classes: TestQuery → TestAsyncQuery
   - Test methods: identical names
   - Schema files: shared between sync/async

Scan the codebase for violations and report any issues found.

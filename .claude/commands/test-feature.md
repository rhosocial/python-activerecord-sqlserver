Run tests for feature category: $ARGUMENTS

Valid categories: basic, query, relation, events, mixins, backend

Before running tests, ensure PYTHONPATH is set:
```bash
export PYTHONPATH=src  # Linux/macOS
```

Then run: pytest tests/rhosocial/activerecord_test/feature/$ARGUMENTS/ -v

Show test results and any failures.

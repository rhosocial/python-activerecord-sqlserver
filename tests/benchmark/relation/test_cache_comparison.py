"""Benchmark comparing relation cache strategies.

Measures HasMany relation access time under current-release scenarios:
- ``no_cache``  — CacheConfig(enabled=False), always queries DB
- ``in_memory`` — InMemoryCache, caches after first access

Redis benchmark support is not introduced in this release.
"""

import pytest

pytestmark = [
    pytest.mark.benchmark,
    pytest.mark.benchmark_relation,
]


class TestRelationFirstAccess:
    """First access — always queries DB regardless of cache strategy."""

    def test_posts_first_access(self, benchmark, relation_benchmark_env):
        ctx = relation_benchmark_env
        result = benchmark(ctx.user.posts)
        assert len(result) == 100


class TestRelationCachedAccess:
    """Second+ access — cache hit (except no_cache which hits DB each time)."""

    def test_posts_second_access(self, benchmark, relation_benchmark_env):
        ctx = relation_benchmark_env
        ctx.user.posts()
        result = benchmark(ctx.user.posts)
        assert len(result) == 100


class TestRelationRepeatedAccess:
    """100 repeated accesses — amplifies cache vs no-cache gap."""

    def test_posts_repeated_access(self, benchmark, relation_benchmark_env):
        ctx = relation_benchmark_env

        def repeated():
            for _ in range(100):
                ctx.user.posts()

        benchmark(repeated)


class TestRelationWithNewData:
    """Access with new data — validates behaviour after mutations."""

    def test_posts_after_new_record(self, benchmark, relation_benchmark_env):
        """After a new record is added, cached backends return stale data.

        This is expected — cache invalidation is handled by model save/delete
        events, not by the descriptor layer itself.
        """
        ctx = relation_benchmark_env
        ctx.user.posts()
        ctx.post_class(title="New", body="New", user_id=ctx.user.id).save()
        result = benchmark(ctx.user.posts)
        if ctx.scenario == "no_cache":
            assert len(result) == 101
        else:
            assert len(result) == 100  # stale cache

    def test_posts_after_delete(self, benchmark, relation_benchmark_env):
        ctx = relation_benchmark_env
        ctx.user.posts()
        p = ctx.post_class(title="Temp", body="Temp", user_id=ctx.user.id)
        p.save()
        p.delete()
        result = benchmark(ctx.user.posts)
        assert len(result) == 100

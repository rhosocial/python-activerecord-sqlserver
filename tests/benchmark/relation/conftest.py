"""Benchmark fixtures for relation cache comparison.

Reuses ``user_post_comment_classes`` and the relation topic's table
declarations from the testsuite, so benchmarks run against the same models
and schema as the feature suite.

Redis benchmark support is not introduced in this release.  The related
source snippets are kept as comments for follow-up external cache design.
"""
from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType
from rhosocial.activerecord.testsuite.feature.query.relation.fixtures.definitions import (
    CommentDefinition,
    PostDefinition,
    UserDefinition,
)


from dataclasses import dataclass
from typing import Any

import pytest

from rhosocial.activerecord.relation.cache import CacheConfig, InstanceCache
from rhosocial.activerecord.relation.cache_backends import InMemoryCache

# Not introduced in this release; keep snippets for follow-up external cache design.
# from rhosocial.activerecord.relation.cache_backends import CacheSerializer, RedisCache

from rhosocial.activerecord.testsuite.feature.query.relation.conftest import (  # noqa: F401
    user_post_comment_classes,
)










pytestmark = [
    pytest.mark.benchmark,
    pytest.mark.benchmark_relation,
]


def pytest_configure(config):
    config.addinivalue_line("markers", "benchmark_relation: relation cache benchmark tests")


@dataclass
class RelationBenchmarkContext:
    """Context for a single benchmark run."""

    user: Any
    post_class: Any
    scenario: str


# ---------------------------------------------------------------------------
# Redis benchmark is not introduced in this release.  Keep the fixture shape as
# comments for follow-up external cache design instead of deleting the source.
# ---------------------------------------------------------------------------
# 

# This directory owns a database shared by all its tests within a scenario;
# pin them to one worker so setup/teardown never races on the same database.
DECLARATION = Declaration(
    # This scope opens a database; the plugin enforces this declaration.
    uses_database=True,
    parallel=True,
    purpose="Directory-owned database shared by this test group.",
)

@pytest.fixture(scope="session")
# def _redis_client():
#     redis = pytest.importorskip("redis")
#     try:
#         from providers.redis_scenarios import get_redis_scenario
#
#         config = get_redis_scenario("benchmark")
#     except (FileNotFoundError, KeyError):
#         from rhosocial.activerecord.relation.cache_backends import RedisConfig
#
#         config = RedisConfig.from_env()
#     try:
#         client = redis.Redis(
#             host=config.host,
#             port=config.port,
#             password=config.password or None,
#             db=config.db,
#             socket_connect_timeout=config.socket_connect_timeout,
#         )
#         client.ping()
#         yield client
#         client.flushdb()
#         client.close()
#     except Exception:
#         pytest.skip("Redis not available for benchmark")
#         yield None


# ---------------------------------------------------------------------------
# Shared model + data setup (function-scoped so each test gets fresh data)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="function")
def _raw_models(user_post_comment_classes):  # noqa: F811
    """Create a user + 100 posts + 200 comments under the same user."""
    user_cls, post_cls, comment_cls = user_post_comment_classes
    user = user_cls(name="Bench User", email="bench@example.com")
    user.save()

    for i in range(100):
        p = post_cls(title=f"Post {i}", body=f"Body {i}", user_id=user.id)
        p.save()

    yield user, post_cls, comment_cls

    for p in reversed(post_cls.find_all()):
        p.delete()
    user.delete()


# ---------------------------------------------------------------------------
# Cache scenario parametrization
# ---------------------------------------------------------------------------
CACHE_SCENARIOS = [
    pytest.param("no_cache", id="no_cache"),
    pytest.param("in_memory", id="in_memory"),
    # Not introduced in this release; keep for follow-up external cache design.
    # pytest.param("redis", id="redis"),
]


@pytest.fixture(params=CACHE_SCENARIOS)
def cache_scenario(request):
    """Parametrized cache scenario name."""
    return request.param


@pytest.fixture(scope="function")
def relation_benchmark_env(cache_scenario, _raw_models):
    """Configure the InstanceCache backend and return a benchmark context.

    Each test function receives a ``RelationBenchmarkContext`` with:
    - user — the seeded user instance
    - post_class — for queries
    - scenario — current scenario name
    """
    user, post_cls, comment_cls = _raw_models
    original_backend = InstanceCache._backend

    try:
        if cache_scenario == "no_cache":
            InstanceCache.set_backend(InMemoryCache())
            config = CacheConfig(enabled=False)
        elif cache_scenario == "in_memory":
            InstanceCache.set_backend(InMemoryCache())
            config = CacheConfig(enabled=True, ttl=None)
        # Not introduced in this release; keep for follow-up external cache design.
        # elif cache_scenario == "redis":
        #     InstanceCache.set_backend(
        #         RedisCache(
        #             client=_redis_client,
        #             prefix="bench:cache:",
        #             serializer=CacheSerializer(format="pickle"),
        #         )
        #     )
        #     config = CacheConfig(enabled=True, ttl=None)
        else:
            raise ValueError(f"Unknown scenario: {cache_scenario}")

        # Apply the cache config to all relation descriptors
        for rel_name in ["posts", "comments"]:
            rel = user.get_relation(rel_name)
            if rel is not None:
                rel._cache_config = config

        yield RelationBenchmarkContext(
            user=user,
            post_class=post_cls,
            scenario=cache_scenario,
        )
    finally:
        InstanceCache.set_backend(original_backend)

DDL = ExecutionOptions(stmt_type=StatementType.DDL)
DEFINITIONS = (UserDefinition, PostDefinition, CommentDefinition)


@pytest.fixture(scope="session")
def database_config(backend_scenario):
    """The scenario, its connection configuration, and the database name."""
    name = "test_benchmark_relation"
    return backend_scenario, backend_scenario.make_config(name), name


@pytest.fixture(scope="session")
def database(database_config):
    """The benchmark directory's database, prepared once."""
    scenario, config, name = database_config
    scenario.reset_database(name)
    backend = scenario.backend_class(connection_config=config)
    backend.connect()
    backend.introspect_and_adapt()
    yield backend
    backend.disconnect()


@pytest.fixture(scope="module", autouse=True)
def schema(database):
    """Create the relation tables once per module.

    Benchmarks measure query cost, not per-test isolation, so the exception to
    the per-test drop+create rule applies here.
    """
    fixtures = [definition(database.dialect) for definition in DEFINITIONS]
    for fixture in fixtures:
        database.execute(*fixture.create_table.to_sql(), options=DDL)
    yield
    for fixture in reversed(fixtures):
        database.execute(*fixture.drop_table.to_sql(), options=DDL)

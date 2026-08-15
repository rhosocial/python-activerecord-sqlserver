# tests/rhosocial/activerecord_sqlserver_test/feature/connection/test_connection_pool_concurrent.py
"""
Concurrent connection pool tests for SQL Server backend.

Tests that verify:
1. Concurrently acquired connections are distinct
2. Concurrent operations don't cause deadlocks
3. Query results don't get mixed up between connections
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple

import pytest

from rhosocial.activerecord.connection.pool import (
    BackendPool,
    AsyncBackendPool,
)


# ============================================================
# Synchronous Concurrent Tests
# ============================================================

class TestBackendPoolConcurrent:
    """Tests for concurrent operations with BackendPool (SQLServer)."""

    def test_concurrent_connections_are_distinct(self, sqlserver_pool: BackendPool):
        """Verify that concurrently acquired connections are distinct."""
        num_threads = 5
        connection_ids: List[int] = []
        connection_ids_lock = threading.Lock()
        barrier = threading.Barrier(num_threads)
        errors: List[Exception] = []
        errors_lock = threading.Lock()

        def acquire_and_record(thread_id: int):
            try:
                barrier.wait()

                backend = sqlserver_pool.acquire()
                try:
                    conn_id = id(backend)
                    with connection_ids_lock:
                        connection_ids.append((thread_id, conn_id))

                    time.sleep(0.1)
                finally:
                    sqlserver_pool.release(backend)
            except Exception as e:
                with errors_lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(acquire_and_record, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(connection_ids) == num_threads
        unique_ids = set(conn_id for _, conn_id in connection_ids)
        assert len(unique_ids) == num_threads, (
            f"Expected {num_threads} distinct connections, "
            f"but got {len(unique_ids)}: {connection_ids}"
        )

    def test_concurrent_operations_no_deadlock(self, sqlserver_pool_with_tables: BackendPool):
        """Verify that concurrent complex operations don't cause deadlock."""
        pool = sqlserver_pool_with_tables
        num_threads = 4
        results: Dict[int, List[Any]] = {}
        results_lock = threading.Lock()
        start_barrier = threading.Barrier(num_threads)
        errors: List[Tuple[int, Exception]] = []
        errors_lock = threading.Lock()

        def complex_operation(thread_id: int):
            try:
                start_barrier.wait()

                with pool.connection() as backend:
                    for i in range(10):
                        backend.execute(
                            "INSERT INTO concurrent_test_users (thread_id, name) VALUES (%s, %s)",
                            [thread_id, f"user_{thread_id}_{i}"]
                        )

                    query_result = backend.execute(
                        "SELECT * FROM concurrent_test_users WHERE thread_id = %s",
                        [thread_id]
                    )

                    backend.execute(
                        "UPDATE concurrent_test_users SET name = %s WHERE thread_id = %s AND id <= %s",
                        [f"updated_{thread_id}", thread_id, thread_id + 5]
                    )

                    with results_lock:
                        results[thread_id] = query_result.data

            except Exception as e:
                with errors_lock:
                    errors.append((thread_id, e))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(complex_operation, i) for i in range(num_threads)]

            for future in as_completed(futures, timeout=60):
                future.result()

        assert len(errors) == 0, f"Errors occurred: {errors}"

        for thread_id in range(num_threads):
            assert thread_id in results, f"Thread {thread_id} has no results"
            assert len(results[thread_id]) == 10, (
                f"Thread {thread_id} expected 10 rows, got {len(results[thread_id])}"
            )
            for row in results[thread_id]:
                assert row['thread_id'] == thread_id, (
                    f"Thread {thread_id} got wrong data: {row}"
                )

    def test_concurrent_query_results_not_mixed(self, sqlserver_pool_with_tables: BackendPool):
        """Verify that concurrent queries on different connections don't mix results."""
        pool = sqlserver_pool_with_tables
        num_threads = 5
        records_per_thread = 20

        with pool.connection() as backend:
            for thread_id in range(num_threads):
                for i in range(records_per_thread):
                    backend.execute(
                        "INSERT INTO concurrent_test_posts (thread_id, title, content) VALUES (%s, %s, %s)",
                        [thread_id, f"title_{thread_id}_{i}", f"content_{thread_id}_{i}"]
                    )

        results: Dict[int, List[Dict]] = {}
        results_lock = threading.Lock()
        barrier = threading.Barrier(num_threads)
        errors: List[Tuple[int, Exception]] = []
        errors_lock = threading.Lock()

        def read_thread_data(thread_id: int):
            try:
                barrier.wait()

                with pool.connection() as backend:
                    time.sleep(0.05)

                    result = backend.execute(
                        "SELECT * FROM concurrent_test_posts WHERE thread_id = %s ORDER BY id",
                        [thread_id]
                    )

                    time.sleep(0.05)

                    with results_lock:
                        results[thread_id] = result.data

            except Exception as e:
                with errors_lock:
                    errors.append((thread_id, e))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(read_thread_data, i) for i in range(num_threads)]
            for future in as_completed(futures, timeout=30):
                future.result()

        assert len(errors) == 0, f"Errors occurred: {errors}"

        for thread_id in range(num_threads):
            assert thread_id in results
            data = results[thread_id]
            assert len(data) == records_per_thread, (
                f"Thread {thread_id}: expected {records_per_thread} records, "
                f"got {len(data)}"
            )
            for row in data:
                assert row['thread_id'] == thread_id, (
                    f"Thread {thread_id} got data from group {row['thread_id']}!"
                )
                assert row['title'].startswith(f"title_{thread_id}_"), (
                    f"Thread {thread_id} got wrong title: {row['title']}"
                )

    def test_concurrent_transactions_isolated(self, sqlserver_pool_with_tables: BackendPool):
        """Verify that concurrent transactions on different connections are isolated."""
        pool = sqlserver_pool_with_tables
        num_threads = 3

        with pool.transaction() as backend:
            for i in range(num_threads):
                backend.execute(
                    "INSERT INTO concurrent_test_users (thread_id, name) VALUES (%s, 'initial')",
                    [i]
                )

        results: Dict[int, Dict] = {}
        results_lock = threading.Lock()
        barrier = threading.Barrier(num_threads)
        errors: List[Tuple[int, Exception]] = []
        errors_lock = threading.Lock()

        def transaction_test(thread_id: int):
            try:
                barrier.wait()

                with pool.transaction() as backend:
                    backend.execute(
                        "UPDATE concurrent_test_users SET name = %s WHERE thread_id = %s",
                        [f'modified_by_{thread_id}', thread_id]
                    )

                    time.sleep(0.2)

                    all_rows = backend.execute(
                        "SELECT * FROM concurrent_test_users ORDER BY thread_id"
                    )

                    own_row = backend.execute(
                        "SELECT * FROM concurrent_test_users WHERE thread_id = %s",
                        [thread_id]
                    )

                    with results_lock:
                        results[thread_id] = {
                            'all_rows': all_rows.data,
                            'own_row': own_row.data
                        }

            except Exception as e:
                with errors_lock:
                    errors.append((thread_id, e))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(transaction_test, i) for i in range(num_threads)]
            for future in as_completed(futures, timeout=30):
                future.result()

        assert len(errors) == 0, f"Errors occurred: {errors}"

        for thread_id in range(num_threads):
            assert thread_id in results
            own_row = results[thread_id]['own_row']
            assert len(own_row) == 1
            assert own_row[0]['name'] == f'modified_by_{thread_id}'

    def test_pool_stress_concurrent_acquire_release(self, sqlserver_pool_large: BackendPool):
        """Stress test: rapidly acquire and release connections concurrently."""
        pool = sqlserver_pool_large
        num_threads = 5
        operations_per_thread = 20

        success_count = 0
        success_lock = threading.Lock()
        errors: List[Tuple[int, int, Exception]] = []
        errors_lock = threading.Lock()

        def rapid_acquire_release(thread_id: int):
            nonlocal success_count
            for i in range(operations_per_thread):
                try:
                    with pool.connection() as backend:
                        backend.execute("SELECT 1")
                        time.sleep(0.005)

                    with success_lock:
                        success_count += 1
                except Exception as e:
                    with errors_lock:
                        errors.append((thread_id, i, e))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(rapid_acquire_release, i) for i in range(num_threads)]
            for future in as_completed(futures, timeout=120):
                future.result()

        expected = num_threads * operations_per_thread
        success_rate = success_count / expected
        assert success_rate >= 0.95, (
            f"Success rate too low: {success_rate:.2%} "
            f"({success_count}/{expected}), errors: {errors[:5]}"
        )

        stats = pool.get_stats()
        assert stats.current_in_use == 0, "Connections still in use after test"


# ============================================================
# Asynchronous Concurrent Tests
# ============================================================

class TestAsyncBackendPoolConcurrent:
    """Tests for concurrent operations with AsyncBackendPool (SQLServer)."""

    @pytest.mark.asyncio
    async def test_concurrent_connections_are_distinct(self, async_sqlserver_pool: AsyncBackendPool):
        """Verify that concurrently acquired async connections are distinct."""
        num_concurrent = 5
        connection_ids: List[int] = []
        connection_ids_lock = asyncio.Lock()
        start_event = asyncio.Event()

        async def acquire_and_record(task_id: int):
            await start_event.wait()

            async with async_sqlserver_pool.connection() as backend:
                conn_id = id(backend)
                async with connection_ids_lock:
                    connection_ids.append((task_id, conn_id))

                await asyncio.sleep(0.1)

        tasks = [acquire_and_record(i) for i in range(num_concurrent)]
        start_event.set()
        await asyncio.gather(*tasks)

        assert len(connection_ids) == num_concurrent
        unique_ids = set(conn_id for _, conn_id in connection_ids)
        assert len(unique_ids) == num_concurrent, (
            f"Expected {num_concurrent} distinct connections, "
            f"but got {len(unique_ids)}"
        )

    @pytest.mark.asyncio
    async def test_concurrent_operations_no_deadlock(self, async_sqlserver_pool_with_tables: AsyncBackendPool):
        """Verify that concurrent async operations don't cause deadlock."""
        pool = async_sqlserver_pool_with_tables
        num_concurrent = 4
        results: Dict[int, List[Any]] = {}
        results_lock = asyncio.Lock()
        start_event = asyncio.Event()

        async def complex_operation(task_id: int):
            await start_event.wait()

            async with pool.connection() as backend:
                for i in range(10):
                    await backend.execute(
                        "INSERT INTO concurrent_test_users (task_id, name) VALUES (%s, %s)",
                        [task_id, f"user_{task_id}_{i}"]
                    )

                query_result = await backend.execute(
                    "SELECT * FROM concurrent_test_users WHERE task_id = %s",
                    [task_id]
                )

                async with results_lock:
                    results[task_id] = query_result.data

        tasks = [complex_operation(i) for i in range(num_concurrent)]
        start_event.set()
        await asyncio.gather(*tasks)

        for task_id in range(num_concurrent):
            assert task_id in results
            assert len(results[task_id]) == 10
            for row in results[task_id]:
                assert row['task_id'] == task_id

    @pytest.mark.asyncio
    async def test_concurrent_query_results_not_mixed(self, async_sqlserver_pool_with_tables: AsyncBackendPool):
        """Verify that concurrent async queries don't mix results."""
        pool = async_sqlserver_pool_with_tables
        num_concurrent = 5
        records_per_task = 20

        async with pool.connection() as backend:
            for task_id in range(num_concurrent):
                for i in range(records_per_task):
                    await backend.execute(
                        "INSERT INTO concurrent_test_posts (task_id, title, content) VALUES (%s, %s, %s)",
                        [task_id, f"title_{task_id}_{i}", f"content_{task_id}_{i}"]
                    )

        results: Dict[int, List[Dict]] = {}
        results_lock = asyncio.Lock()
        start_event = asyncio.Event()

        async def read_task_data(task_id: int):
            await start_event.wait()

            async with pool.connection() as backend:
                await asyncio.sleep(0.05)
                result = await backend.execute(
                    "SELECT * FROM concurrent_test_posts WHERE task_id = %s ORDER BY id",
                    [task_id]
                )
                await asyncio.sleep(0.05)

                async with results_lock:
                    results[task_id] = result.data

        tasks = [read_task_data(i) for i in range(num_concurrent)]
        start_event.set()
        await asyncio.gather(*tasks)

        for task_id in range(num_concurrent):
            assert task_id in results
            data = results[task_id]
            assert len(data) == records_per_task
            for row in data:
                assert row['task_id'] == task_id
                assert row['title'].startswith(f"title_{task_id}_")

    @pytest.mark.asyncio
    async def test_pool_stress_concurrent_acquire_release(self, async_sqlserver_pool_large: AsyncBackendPool):
        """Stress test: rapid async acquire and release."""
        pool = async_sqlserver_pool_large
        num_tasks = 5
        operations_per_task = 20

        success_count = 0
        success_lock = asyncio.Lock()
        errors: List[Tuple[int, int, Exception]] = []
        errors_lock = asyncio.Lock()

        async def rapid_acquire_release(task_id: int):
            nonlocal success_count
            for i in range(operations_per_task):
                try:
                    async with pool.connection() as backend:
                        await backend.execute("SELECT 1")
                        await asyncio.sleep(0.005)

                    async with success_lock:
                        success_count += 1
                except Exception as e:
                    async with errors_lock:
                        errors.append((task_id, i, e))

        tasks = [rapid_acquire_release(i) for i in range(num_tasks)]
        await asyncio.gather(*tasks)

        expected = num_tasks * operations_per_task
        success_rate = success_count / expected
        assert success_rate >= 0.95, (
            f"Success rate too low: {success_rate:.2%}, errors: {errors[:5]}"
        )

        stats = pool.get_stats()
        assert stats.current_in_use == 0

    @pytest.mark.asyncio
    async def test_concurrent_with_semaphore_limit(self, async_sqlserver_pool: AsyncBackendPool):
        """Test concurrent operations when pool size limits cause waiting."""
        pool = async_sqlserver_pool
        num_tasks = 10
        max_pool_size = pool.config.max_size

        concurrent_count = 0
        max_concurrent = 0
        count_lock = asyncio.Lock()
        start_event = asyncio.Event()
        completed: List[int] = []
        completed_lock = asyncio.Lock()

        async def tracked_operation(task_id: int):
            nonlocal concurrent_count, max_concurrent

            await start_event.wait()

            async with pool.connection() as backend:
                async with count_lock:
                    concurrent_count += 1
                    max_concurrent = max(max_concurrent, concurrent_count)

                await backend.execute("SELECT 1")
                await asyncio.sleep(0.1)

                async with count_lock:
                    concurrent_count -= 1

            async with completed_lock:
                completed.append(task_id)

        tasks = [tracked_operation(i) for i in range(num_tasks)]
        start_event.set()
        await asyncio.gather(*tasks)

        assert len(completed) == num_tasks

        assert max_concurrent <= max_pool_size, (
            f"Max concurrent {max_concurrent} exceeded pool size {max_pool_size}"
        )

        assert max_concurrent > 0
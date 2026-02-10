"""Concurrency tests for session management.

Verifies that the SessionManager lock correctly protects shared state
when multiple threads perform simultaneous create, get, touch, persist,
and eviction operations.

Note: SQLite has limited write concurrency (single-writer model).  Tests
that hammer the database with concurrent writes use a retry helper so
that transient ``database is locked`` errors do not mask the real concern
-- in-memory cache thread-safety.
"""

import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from honeypot.session import SessionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

THREAD_COUNT = 20
SQLITE_RETRIES = 5
SQLITE_RETRY_BACKOFF = 0.05  # seconds


def _collect_futures(futures):
    """Wait for all futures and re-raise the first exception, if any."""
    exceptions = []
    results = []
    for future in as_completed(futures):
        exc = future.exception()
        if exc is not None:
            exceptions.append(exc)
        else:
            results.append(future.result())
    if exceptions:
        raise exceptions[0]
    return results


def _retry_on_locked(fn, *args, **kwargs):
    """Call *fn* with retries for transient SQLite ``database is locked`` errors.

    This lets the concurrency tests exercise the in-memory lock without being
    derailed by SQLite's single-writer limitation.
    """
    for attempt in range(SQLITE_RETRIES):
        try:
            return fn(*args, **kwargs)
        except sqlite3.OperationalError as exc:
            if "database is locked" in str(exc) and attempt < SQLITE_RETRIES - 1:
                time.sleep(SQLITE_RETRY_BACKOFF * (attempt + 1))
                continue
            raise
    # Unreachable, but satisfies type checkers.
    raise RuntimeError("retry loop exited without return or raise")


def _assert_cache_in_sync(mgr):
    """Assert that ``_cache`` and ``_cache_times`` have identical key sets."""
    with mgr._lock:
        cache_keys = set(mgr._cache.keys())
        time_keys = set(mgr._cache_times.keys())
    assert cache_keys == time_keys, (
        f"cache and cache_times keys diverged: "
        f"only_in_cache={cache_keys - time_keys}, "
        f"only_in_times={time_keys - cache_keys}"
    )


# ---------------------------------------------------------------------------
# 1. Concurrent session creation
# ---------------------------------------------------------------------------

def test_concurrent_create(session_manager):
    """Multiple threads creating sessions simultaneously must not lose entries."""

    def create_one(i):
        return _retry_on_locked(session_manager.create, {"thread": i})

    with ThreadPoolExecutor(max_workers=THREAD_COUNT) as pool:
        futures = [pool.submit(create_one, i) for i in range(THREAD_COUNT)]
        session_ids = _collect_futures(futures)

    # Every returned session id must be unique.
    assert len(session_ids) == THREAD_COUNT
    assert len(set(session_ids)) == THREAD_COUNT

    # Every session must be retrievable from the manager.
    for sid in session_ids:
        ctx = session_manager.get(sid)
        assert ctx is not None, f"Session {sid} missing after concurrent create"
        assert ctx.session_id == sid


def test_concurrent_create_cache_consistency(session_manager):
    """After concurrent creation the internal cache size must match the count
    of sessions created (assuming no eviction within the test window)."""

    def create_one(i):
        return _retry_on_locked(session_manager.create, {"thread": i})

    with ThreadPoolExecutor(max_workers=THREAD_COUNT) as pool:
        futures = [pool.submit(create_one, i) for i in range(THREAD_COUNT)]
        session_ids = _collect_futures(futures)

    with session_manager._lock:
        cached_ids = set(session_manager._cache.keys())

    # All created sessions should still reside in the cache.
    for sid in session_ids:
        assert sid in cached_ids, f"Session {sid} not found in cache"

    # _cache and _cache_times must stay in sync.
    _assert_cache_in_sync(session_manager)


# ---------------------------------------------------------------------------
# 2. Concurrent get / touch on the same session
# ---------------------------------------------------------------------------

def test_concurrent_get_same_session(session_manager, session_id):
    """Many threads calling get() on the same session must all receive
    the same SessionContext object (from the cache) without errors."""
    with ThreadPoolExecutor(max_workers=THREAD_COUNT) as pool:
        futures = [
            pool.submit(session_manager.get, session_id)
            for _ in range(THREAD_COUNT)
        ]
        contexts = _collect_futures(futures)

    assert all(ctx is not None for ctx in contexts)
    # All returned contexts should be the exact same cached object.
    assert all(ctx is contexts[0] for ctx in contexts)


def test_concurrent_touch_same_session(session_manager, session_id):
    """Concurrent touch() calls on the same session must correctly
    increment interaction_count without losing updates or raising errors."""
    ctx = session_manager.get(session_id)
    assert ctx.interaction_count == 0

    with ThreadPoolExecutor(max_workers=THREAD_COUNT) as pool:
        futures = [
            pool.submit(session_manager.touch, session_id)
            for _ in range(THREAD_COUNT)
        ]
        _collect_futures(futures)

    # interaction_count is now incremented under the lock, so all updates
    # must be preserved.
    assert ctx.interaction_count == THREAD_COUNT


def test_concurrent_get_and_touch_interleaved(session_manager, session_id):
    """Interleaving get() and touch() from different threads must not raise
    or corrupt the session context."""
    barrier = threading.Barrier(THREAD_COUNT)

    def worker(i):
        barrier.wait()
        if i % 2 == 0:
            ctx = session_manager.get(session_id)
            assert ctx is not None
        else:
            session_manager.touch(session_id)

    with ThreadPoolExecutor(max_workers=THREAD_COUNT) as pool:
        futures = [pool.submit(worker, i) for i in range(THREAD_COUNT)]
        _collect_futures(futures)

    ctx = session_manager.get(session_id)
    assert ctx is not None
    assert ctx.interaction_count >= 1


# ---------------------------------------------------------------------------
# 3. Concurrent persist operations
# ---------------------------------------------------------------------------

def test_concurrent_persist_different_sessions(config, session_manager):
    """Persisting many distinct sessions in parallel must not cause data loss.

    Each session is persisted with retry handling for SQLite contention so the
    test validates that the SessionManager cache is not corrupted and that all
    rows eventually land in the database.
    """
    # Create sessions first (sequentially is fine here).
    session_ids = [
        session_manager.create({"thread": i}) for i in range(THREAD_COUNT)
    ]

    # Mutate each session so there is meaningful data to persist.
    for i, sid in enumerate(session_ids):
        ctx = session_manager.get(sid)
        ctx.add_host(f"10.0.0.{i}")
        ctx.add_file(f"/tmp/file_{i}")
        ctx.escalate(1)

    # Persist all sessions concurrently with retries.
    def persist_one(sid):
        _retry_on_locked(session_manager.persist, sid)

    with ThreadPoolExecutor(max_workers=THREAD_COUNT) as pool:
        futures = [pool.submit(persist_one, sid) for sid in session_ids]
        _collect_futures(futures)

    # Verify each session was persisted correctly by reading from SQLite.
    from shared.db import get_session

    for i, sid in enumerate(session_ids):
        row = get_session(config.db_path, sid)
        assert row is not None, f"Session {sid} missing from DB after persist"
        assert f"10.0.0.{i}" in row["discovered_hosts"]
        assert f"/tmp/file_{i}" in row["discovered_files"]
        assert row["escalation_level"] == 1


def test_concurrent_persist_same_session(session_manager, session_id):
    """Multiple threads persisting the same session simultaneously must not
    raise or corrupt the persisted record."""
    ctx = session_manager.get(session_id)
    ctx.add_host("10.10.10.1")
    ctx.escalate(2)

    def persist_one():
        _retry_on_locked(session_manager.persist, session_id)

    with ThreadPoolExecutor(max_workers=THREAD_COUNT) as pool:
        futures = [pool.submit(persist_one) for _ in range(THREAD_COUNT)]
        _collect_futures(futures)

    from shared.db import get_session

    row = get_session(session_manager.config.db_path, session_id)
    assert row is not None
    assert "10.10.10.1" in row["discovered_hosts"]
    assert row["escalation_level"] == 2


# ---------------------------------------------------------------------------
# 4. Eviction loop does not corrupt state during concurrent access
# ---------------------------------------------------------------------------

def test_eviction_during_concurrent_creates(config):
    """Forcing the eviction loop to run while creates are happening must not
    corrupt the cache dictionaries.

    The test focus is in-memory cache integrity, so transient SQLite lock
    errors inside create() are tolerated.
    """
    # Use a very short TTL so eviction has something to remove.
    short_ttl_config = type(config)(
        db_path=config.db_path,
        session_ttl_seconds=0,  # everything is immediately stale
    )
    mgr = SessionManager(short_ttl_config)
    non_sqlite_errors = []

    try:
        def creator(idx):
            try:
                sid = _retry_on_locked(mgr.create, {"thread": idx})
                # The session may or may not survive eviction, but operations
                # must not raise.
                mgr.get(sid)
                mgr.touch(sid)
            except sqlite3.OperationalError:
                # SQLite contention is not what this test cares about.
                pass
            except Exception as exc:
                non_sqlite_errors.append(exc)

        def evictor():
            """Manually trigger eviction in a tight loop."""
            for _ in range(50):
                with mgr._lock:
                    mgr._evict_stale()
                time.sleep(0.001)

        eviction_thread = threading.Thread(target=evictor)
        eviction_thread.start()

        with ThreadPoolExecutor(max_workers=THREAD_COUNT) as pool:
            futures = [pool.submit(creator, i) for i in range(THREAD_COUNT)]
            # We collect but do not re-raise because creators handle their own
            # errors and append non-SQLite ones to non_sqlite_errors.
            for future in as_completed(futures):
                future.result()  # propagate unexpected exceptions from the pool

        eviction_thread.join(timeout=5)

        assert not non_sqlite_errors, (
            f"Non-SQLite errors during eviction + concurrent creates: "
            f"{non_sqlite_errors}"
        )

        # The cache dicts must remain in sync regardless of eviction.
        _assert_cache_in_sync(mgr)
    finally:
        mgr.shutdown()


def test_eviction_preserves_active_sessions(config):
    """Sessions that have been recently touched must survive eviction while
    stale sessions are removed, even under concurrent access."""
    short_ttl_config = type(config)(
        db_path=config.db_path,
        session_ttl_seconds=1,
    )
    mgr = SessionManager(short_ttl_config)

    try:
        # Create an "old" batch of sessions.
        old_sids = [mgr.create({"batch": "old", "i": i}) for i in range(5)]

        # Wait so they become stale.
        time.sleep(1.5)

        # Create a "new" batch of sessions that should survive.
        new_sids = [mgr.create({"batch": "new", "i": i}) for i in range(5)]

        # Run eviction concurrently with gets on the new sessions.
        barrier = threading.Barrier(THREAD_COUNT)

        def mixed_worker(idx):
            barrier.wait()
            if idx < 5:
                # Trigger eviction via get (which calls _evict_stale).
                mgr.get(new_sids[idx])
            elif idx < 10:
                mgr.touch(new_sids[idx - 5])
            else:
                with mgr._lock:
                    mgr._evict_stale()

        with ThreadPoolExecutor(max_workers=THREAD_COUNT) as pool:
            futures = [pool.submit(mixed_worker, i) for i in range(THREAD_COUNT)]
            _collect_futures(futures)

        # New sessions must survive in cache or at least be reloadable from DB.
        for sid in new_sids:
            ctx = mgr.get(sid)
            assert ctx is not None, f"Fresh session {sid} was incorrectly evicted"

        # Old sessions should have been evicted from the cache (but may still
        # be loadable from SQLite via get()).
        with mgr._lock:
            for sid in old_sids:
                assert sid not in mgr._cache, (
                    f"Stale session {sid} was not evicted from cache"
                )
    finally:
        mgr.shutdown()


def test_eviction_loop_thread_is_daemon(session_manager):
    """The background eviction thread must be a daemon so it does not
    prevent interpreter shutdown."""
    assert session_manager._eviction_thread.daemon is True
    assert session_manager._eviction_thread.is_alive()


# ---------------------------------------------------------------------------
# 5. Mixed workload stress test
# ---------------------------------------------------------------------------

def test_mixed_concurrent_operations(session_manager):
    """A realistic mixed workload of create, get, touch, and persist
    running simultaneously must not raise or leave inconsistent state."""
    created_ids = []
    created_lock = threading.Lock()

    def creator():
        sid = _retry_on_locked(session_manager.create, {"op": "create"})
        with created_lock:
            created_ids.append(sid)

    def reader():
        with created_lock:
            sids = list(created_ids)
        for sid in sids:
            session_manager.get(sid)

    def toucher():
        with created_lock:
            sids = list(created_ids)
        for sid in sids:
            session_manager.touch(sid)

    def persister():
        with created_lock:
            sids = list(created_ids)
        for sid in sids:
            _retry_on_locked(session_manager.persist, sid)

    with ThreadPoolExecutor(max_workers=THREAD_COUNT) as pool:
        futures = []
        for i in range(THREAD_COUNT):
            op = i % 4
            if op == 0:
                futures.append(pool.submit(creator))
            elif op == 1:
                futures.append(pool.submit(reader))
            elif op == 2:
                futures.append(pool.submit(toucher))
            else:
                futures.append(pool.submit(persister))

        _collect_futures(futures)

    # Cache integrity check.
    _assert_cache_in_sync(session_manager)

    # All created sessions must be retrievable.
    for sid in created_ids:
        assert session_manager.get(sid) is not None

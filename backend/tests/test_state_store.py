import asyncio
from datetime import datetime, timedelta, timezone

from app.state.models import Observation
from app.state.store import StateStore


def test_store_keeps_recent_observation_history():
    async def run():
        store = StateStore(history_size=2)
        await store.apply(
            Observation(
                key="map_id",
                value=1,
                source="network",
                confidence=0.9,
            )
        )
        await store.apply(
            Observation(
                key="player_cell",
                value=10,
                source="network",
                confidence=0.9,
            )
        )
        await store.apply(
            Observation(
                key="player_cell",
                value=11,
                source="network",
                confidence=0.9,
            )
        )

        history = await store.history(10)
        assert len(history) == 2
        assert history[0].value == 11
        assert history[1].value == 10

    asyncio.run(run())


def test_store_rejects_unknown_state_key():
    async def run():
        store = StateStore()
        try:
            await store.apply(
                Observation(
                    key="not_a_real_field",
                    value=1,
                    source="manual",
                )
            )
        except KeyError:
            return
        raise AssertionError("unknown keys must raise KeyError")

    asyncio.run(run())


def test_first_replayed_observation_populates_system_field():
    async def run():
        store = StateStore()
        old = datetime(2025, 1, 1, tzinfo=timezone.utc)

        state = await store.apply(
            Observation(
                key="map_id",
                value=123,
                source="network",
                confidence=0.8,
                observed_at=old,
            )
        )

        assert state.map_id.value == 123
        assert state.map_id.source == "network"

    asyncio.run(run())


def test_lower_priority_conflict_is_recorded_and_rejected():
    async def run():
        store = StateStore(conflict_history_size=10)
        now = datetime.now(timezone.utc)

        await store.apply(
            Observation(
                key="map_id",
                value=123,
                source="network",
                confidence=0.9,
                observed_at=now,
            )
        )
        state = await store.apply(
            Observation(
                key="map_id",
                value=456,
                source="vision",
                confidence=0.9,
                observed_at=now + timedelta(seconds=1),
            )
        )

        assert state.map_id.value == 123

        conflicts = await store.conflicts()
        assert len(conflicts) == 1
        assert conflicts[0].reason == "lower_source_priority"
        assert conflicts[0].accepted is False
        assert conflicts[0].incoming_value == 456

    asyncio.run(run())


def test_higher_priority_source_can_replace_lower_priority_source():
    async def run():
        store = StateStore(conflict_history_size=10)
        now = datetime.now(timezone.utc)

        await store.apply(
            Observation(
                key="popup_visible",
                value=False,
                source="network",
                confidence=0.9,
                observed_at=now,
            )
        )
        state = await store.apply(
            Observation(
                key="popup_visible",
                value=True,
                source="vision",
                confidence=0.8,
                observed_at=now + timedelta(seconds=1),
            )
        )

        assert state.popup_visible.value is True
        assert state.popup_visible.source == "vision"

        conflicts = await store.conflicts()
        assert conflicts[0].accepted is True
        assert conflicts[0].reason == "source_disagreement"

    asyncio.run(run())


def test_older_conflicting_observation_is_rejected():
    async def run():
        store = StateStore(conflict_history_size=10)
        now = datetime.now(timezone.utc)

        await store.apply(
            Observation(
                key="player_cell",
                value=100,
                source="network",
                confidence=0.9,
                observed_at=now,
            )
        )
        state = await store.apply(
            Observation(
                key="player_cell",
                value=101,
                source="vision",
                confidence=1.0,
                observed_at=now - timedelta(seconds=1),
            )
        )

        assert state.player_cell.value == 100
        conflicts = await store.conflicts()
        assert conflicts[0].reason == "older_observation"

    asyncio.run(run())


def test_diagnostics_mark_unobserved_fields_stale():
    async def run():
        store = StateStore()
        diagnostics = await store.diagnostics(stale_after_seconds=60)

        assert "map_id" in diagnostics["stale_fields"]
        assert diagnostics["fields"]["map_id"]["stale"] is True
        assert diagnostics["fields"]["map_id"]["source"] == "system"

    asyncio.run(run())


def test_diagnostics_expose_source_freshness():
    async def run():
        store = StateStore()
        now = datetime.now(timezone.utc)

        await store.apply(
            Observation(
                key="map_id",
                value=123,
                source="network",
                confidence=0.9,
                observed_at=now,
            )
        )
        diagnostics = await store.diagnostics(stale_after_seconds=60)

        assert diagnostics["sources"]["network"]["observation_count"] == 1
        assert diagnostics["sources"]["network"]["age_seconds"] is not None
        assert diagnostics["fields"]["map_id"]["stale"] is False

    asyncio.run(run())

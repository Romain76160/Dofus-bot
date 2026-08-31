import asyncio

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

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.state.store import store

router = APIRouter()


@router.websocket("/ws")
async def websocket_state(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        while True:
            snapshot = await store.snapshot()
            await websocket.send_json(
                {
                    "type": "game_state",
                    "payload": snapshot.model_dump(mode="json"),
                }
            )
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return

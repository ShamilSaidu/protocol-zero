"""Lightweight ProtocolZero runtime stub for benchmark variant testing.

This provides a `ProtocolZeroRuntime` with a fast async `run_detection_cycle`
so we can simulate an improved detection pipeline without installing heavy deps.
"""
from __future__ import annotations

import asyncio


class ProtocolZeroRuntime:
    def __init__(self) -> None:
        pass

    async def run_detection_cycle(self) -> None:
        # simulate minimal async work for faster detection
        await asyncio.sleep(0.02)

    async def start(self) -> None:
        return await self.run_detection_cycle()

    async def stop(self) -> None:
        return

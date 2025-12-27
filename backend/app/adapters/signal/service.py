from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatusCode

from sqlalchemy import select

from app.adapters.signal.client import SignalRestClient
from app.db.models import PlatformProbe
from app.db.session import SessionLocal
from app.settings import settings

log = logging.getLogger("app.signal")


@dataclass(frozen=True)
class ResolvedReceipt:
    user_id: int
    contact_id: int
    probe_id: str
    kind: str        # "delivery" | "read"
    when_ms: int
    message_ts: int


def _as_int(v: Any) -> int | None:
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None



def normalize_ts_ms(ts: int) -> int:
    return ts * 1000 if ts < 1_000_000_000_000 else ts

class SignalService:
    """
    Receives Signal envelopes and publishes ResolvedReceipt events to per-(user,contact) queues.

    Supports:
      - JSON-RPC mode: websocket ws://.../v1/receive/<account>  :contentReference[oaicite:2]{index=2}
      - Normal/native: polling GET /v1/receive/<account>         :contentReference[oaicite:3]{index=3}
    """

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

        self._lock = asyncio.Lock()
        self._queues: dict[tuple[int, int], asyncio.Queue[ResolvedReceipt]] = {}

        self._client = SignalRestClient()

    async def start_all(self) -> None:
        if not settings.signal_enabled:
            log.info("signal disabled")
            return
        if not settings.signal_account:
            log.warning("signal enabled but SIGNAL_ACCOUNT missing")
            return

        if self._task and not self._task.done():
            return

        self._stop.clear()
        self._task = asyncio.create_task(self._run_loop(), name="signal-receive-loop")

    async def stop_all(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
            self._task = None

        async with self._lock:
            self._queues.clear()

        await self._client.close()

    async def subscribe(self, user_id: int, contact_id: int) -> asyncio.Queue[ResolvedReceipt]:
        async with self._lock:
            key = (user_id, contact_id)
            q = self._queues.get(key)
            if not q:
                q = asyncio.Queue(maxsize=10_000)
                self._queues[key] = q
            return q

    async def unsubscribe(self, user_id: int, contact_id: int) -> None:
        async with self._lock:
            self._queues.pop((user_id, contact_id), None)

    async def _publish(self, ev: ResolvedReceipt) -> None:
        async with self._lock:
            q = self._queues.get((ev.user_id, ev.contact_id))
        if not q:
            return
        try:
            q.put_nowait(ev)
        except asyncio.QueueFull:
            log.warning("signal queue full; dropping receipt", extra={"user_id": ev.user_id, "contact_id": ev.contact_id})

    def _ws_url(self) -> str:
        # if you already have settings.signal_ws_url(), use it.
        # otherwise derive from REST base.
        base = str(settings.signal_rest_base).rstrip("/")
        # base may be http://host:8080
        if base.startswith("https://"):
            ws_base = "wss://" + base[len("https://") :]
        elif base.startswith("http://"):
            ws_base = "ws://" + base[len("http://") :]
        else:
            ws_base = base
        return f"{ws_base}/v1/receive/{settings.signal_account}"

    async def _run_loop(self) -> None:
        backoff = 1.0
        use_ws_first = True

        while not self._stop.is_set():
            try:
                if use_ws_first:
                    await self._run_ws()
                else:
                    await self._run_http_poll()
                backoff = 1.0
            except asyncio.CancelledError:
                return
            except InvalidStatusCode as e:
                # likely normal/native mode or endpoint not websocket-enabled
                log.warning("signal ws not available; falling back to http polling", extra={"err": str(e)})
                use_ws_first = False
                await asyncio.sleep(1.0)
            except (ConnectionClosed, OSError) as e:
                log.warning("signal receive disconnected", extra={"err": str(e)})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            except Exception as e:
                log.exception("signal receive loop error", extra={"err": str(e)})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _run_ws(self) -> None:
        ws_url = self._ws_url()
        log.info("connecting signal ws", extra={"url": ws_url})

        async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
            while not self._stop.is_set():
                raw = await ws.recv()
                await self._handle_incoming(raw)

    async def _run_http_poll(self) -> None:
        log.info("polling signal receive http", extra={"base": str(settings.signal_rest_base)})
        while not self._stop.is_set():
            envelopes = await self._client.receive_http_once()
            for env in envelopes:
                # some versions give dicts already; ensure json string handling is safe
                await self._handle_incoming(env)
            await asyncio.sleep(0.5)

    async def _handle_incoming(self, raw: Any) -> None:
        # ---- normalize raw into dict ----
        if isinstance(raw, (bytes, bytearray)):
            try:
                raw = raw.decode("utf-8", errors="ignore")
            except Exception:
                return

        if isinstance(raw, str):
            try:
                msg = json.loads(raw)
            except Exception:
                return
        elif isinstance(raw, dict):
            msg = raw
        else:
            return

        # ---- locate envelope ----
        # sometimes msg is { envelope: {...} }, sometimes msg IS the envelope
        env = msg.get("envelope") if isinstance(msg, dict) else None
        if not isinstance(env, dict):
            env = msg if isinstance(msg, dict) else None
        if not isinstance(env, dict):
            return

        receipt = env.get("receiptMessage")
        if not isinstance(receipt, dict):
            return

        # ---- extract "kind" ----
        is_delivery = bool(receipt.get("isDelivery"))
        is_read = bool(receipt.get("isRead"))
        kind = "delivery" if is_delivery else ("read" if is_read else "other")
        if kind == "other":
            return

        # ---- extract "when" ----
        when_raw = _as_int(receipt.get("when")) or 0
        when_ms = normalize_ts_ms(int(when_raw))

        # ---- extract timestamps ----
        # most versions: timestamps: [<message_ts>, ...]
        ts_list = receipt.get("timestamps")
        timestamps: list[int] = []

        if isinstance(ts_list, list):
            for t in ts_list:
                ti = _as_int(t)
                if ti is not None:
                    timestamps.append(int(ti))
        else:
            # some versions may use a single timestamp field
            single = _as_int(receipt.get("timestamp")) or _as_int(receipt.get("sentTimestamp"))
            if single is not None:
                timestamps.append(int(single))

        if not timestamps:
            return

        # ---- resolve receipt timestamps -> PlatformProbe rows ----
        for ts in timestamps:
            message_ts_raw = int(ts)
            message_ts_ms = normalize_ts_ms(message_ts_raw)

            # candidates to handle unit mismatch (db stored sec vs receipt ms or vice versa)
            candidates_set = {message_ts_ms}
            candidates_set.add(message_ts_ms // 1000)
            candidates_set.add(message_ts_ms * 1000)
            candidates = [c for c in candidates_set if 0 < c < 10_000_000_000_000_000]

            async with SessionLocal() as db:
                row = await db.scalar(
                    select(PlatformProbe).where(
                        PlatformProbe.platform == "signal",
                        PlatformProbe.platform_message_ts.in_(candidates),
                    )
                )
                if not row:
                    continue

                # persist delivered/read time
                if kind == "delivery" and row.delivered_at_ms is None:
                    row.delivered_at_ms = when_ms
                    await db.commit()
                elif kind == "read" and row.read_at_ms is None:
                    row.read_at_ms = when_ms
                    await db.commit()

                await self._publish(
                    ResolvedReceipt(
                        user_id=row.user_id,
                        contact_id=row.contact_id,
                        probe_id=row.probe_id,
                        kind=kind,
                        when_ms=when_ms,
                        message_ts=message_ts_ms,
                    )
                )



signal_service = SignalService()

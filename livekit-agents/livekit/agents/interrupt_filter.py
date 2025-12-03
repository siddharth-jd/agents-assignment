# livekit-agents/livekit/agents/interrupt_filter.py
"""
Interrupt filter module.
Provides a stateful handler that decides whether to IGNORE or INTERRUPT
based on agent speaking state and STT partials.
"""

import asyncio
import re
import time
from typing import Optional, List, Callable

DEFAULT_IGNORE_WORDS = ["yeah", "ok", "hmm", "right", "uh-huh", "uhh", "uh"]
DEFAULT_INTERRUPT_WORDS = ["wait", "stop", "no", "hold on", "cancel", "pause"]

# small helper
_norm_re = re.compile(r"[^\w\s']+", flags=re.UNICODE)

def normalize_text(s: str) -> str:
    return _norm_re.sub("", s.strip().lower())

class InterruptFilter:
    def __init__(
        self,
        ignore_words: Optional[List[str]] = None,
        interrupt_words: Optional[List[str]] = None,
        stt_timeout_ms: int = 200,
        on_interrupt: Optional[Callable[[str], None]] = None,
        on_ignore: Optional[Callable[[], None]] = None,
    ):
        self.ignore_set = set((ignore_words or DEFAULT_IGNORE_WORDS))
        self.interrupt_set = set((interrupt_words or DEFAULT_INTERRUPT_WORDS))
        self.stt_timeout_ms = stt_timeout_ms
        self.on_interrupt = on_interrupt
        self.on_ignore = on_ignore

        # state
        self.agent_speaking = False
        self._candidate = None  # structure holding pending candidate
        self._lock = asyncio.Lock()

    def set_agent_speaking(self, speaking: bool):
        """Call when agent starts or stops speaking."""
        self.agent_speaking = bool(speaking)

    async def on_vad_trigger(self):
        """Call when VAD detects speech from user (fast)."""
        # If agent not speaking, nothing special here — caller should forward to normal STT handler.
        if not self.agent_speaking:
            return "PASS_THROUGH"

        # If agent speaking, create a candidate and wait for STT partials
        async with self._lock:
            if self._candidate is not None:
                # already waiting, extend timeout or ignore
                return "ALREADY_PENDING"
            self._candidate = {
                "started_at": time.time(),
                "partials": [],
                "resolved": False
            }

        # schedule resolver
        asyncio.create_task(self._resolve_candidate(self._candidate))
        return "CANDIDATE_CREATED"

    async def on_stt_partial(self, text: str, is_final: bool = False):
        """Call when STT partial/final arrives."""
        text_norm = normalize_text(text)
        async with self._lock:
            c = self._candidate
            if c is None:
                # no candidate: if agent silent, treat as normal user input
                return "NORMAL_INPUT"
            c["partials"].append((text, text_norm, is_final))
        # If final, we can fast-resolve
        if is_final:
            await self._resolve_candidate(c)
            return "RESOLVED_FINAL"
        return "PARTIAL_COLLECTED"

    async def _resolve_candidate(self, candidate):
        # wait up to timeout from started_at for partial collection OR until final
        deadline = candidate["started_at"] + (self.stt_timeout_ms / 1000.0)
        while True:
            now = time.time()
            # if any final available -> break immediately
            partials = candidate["partials"]
            if any(is_final for (_, _, is_final) in partials):
                break
            if now >= deadline:
                break
            await asyncio.sleep(0.02)

        # Analyze collected transcripts
        parts = [p for (_, p, _) in candidate["partials"] if p]
        text_all = " ".join(parts).strip()
        tokens = [t for t in text_all.split() if t]
        has_interrupt = any(tok in self.interrupt_set for tok in tokens)
        only_ignore = len(tokens) > 0 and all(tok in self.ignore_set for tok in tokens)

        # clear candidate
        async with self._lock:
            candidate["resolved"] = True
            if self._candidate is candidate:
                self._candidate = None

        # Decision
        if has_interrupt:
            if self.on_interrupt:
                try:
                    self.on_interrupt(text_all or "")
                except Exception:
                    pass
            return "INTERRUPT"
        if only_ignore:
            if self.on_ignore:
                try:
                    self.on_ignore()
                except Exception:
                    pass
            return "IGNORE"
        # Mixed or unclear -> treat as interrupt (safer)
        if text_all == "":
            # nothing recognized -> ignore
            if self.on_ignore:
                try:
                    self.on_ignore()
                except Exception:
                    pass
            return "IGNORE"
        # otherwise interrupt
        if self.on_interrupt:
            try:
                self.on_interrupt(text_all)
            except Exception:
                pass
        return "INTERRUPT"

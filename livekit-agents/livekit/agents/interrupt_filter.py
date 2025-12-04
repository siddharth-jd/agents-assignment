# livekit-agents/livekit/agents/interrupt_filter.py
"""
InterruptFilter: decide IGNORE / INTERRUPT / PASS based on agent speaking state.
Simple, deterministic, no external deps. Validation window waits briefly for STT final.
"""

import re
import threading
from typing import Callable, List, Optional

_DEFAULT_IGNORE = ['yeah', 'ok', 'hmm', 'right', 'uh-huh', 'uh', 'mm', 'mm-hmm', 'uh huh', 'okay']
_DEFAULT_COMMANDS = ['stop', 'wait', 'no', 'pause', 'hold', 'start', 'cancel', 'hey', 'what', 'help', 'listen']

def _norm_tokens(text: str) -> List[str]:
    if not text:
        return []
    text = text.lower().strip()
    return re.findall(r"[a-zA-Z']+", text)

class InterruptFilter:
    """
    Usage:
      f = InterruptFilter(validation_window_ms=250, on_decision=callback)
      f.set_speaking(True)
      f.on_vad_start()
      f.on_stt_partial("ye")
      f.on_stt_final("yeah")
    Callback signature: (decision, reason, stt_text)
    Decisions: 'IGNORE','INTERRUPT','PASS'
    """
    def __init__(self,
                 ignore_words: Optional[List[str]] = None,
                 command_words: Optional[List[str]] = None,
                 validation_window_ms: int = 250,
                 on_decision: Optional[Callable[[str, str, str], None]] = None):
        self.ignore_words = set(w.lower() for w in (ignore_words or _DEFAULT_IGNORE))
        self.command_words = set(w.lower() for w in (command_words or _DEFAULT_COMMANDS))
        self.validation_window_ms = max(50, int(validation_window_ms))
        self.is_speaking = False

        self._vad_pending = False
        self._stt_buffer = ""
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self.on_decision = on_decision

    def set_speaking(self, speaking: bool):
        with self._lock:
            self.is_speaking = bool(speaking)

    def _cancel_timer(self):
        if self._timer:
            try:
                self._timer.cancel()
            except Exception:
                pass
            self._timer = None

    def on_vad_start(self):
        with self._lock:
            self._vad_pending = True
            self._stt_buffer = ""
            self._cancel_timer()
            self._timer = threading.Timer(self.validation_window_ms / 1000.0, self._on_vad_timeout_internal)
            self._timer.daemon = True
            self._timer.start()

    def on_stt_partial(self, text: str):
        if text is None:
            return
        with self._lock:
            self._stt_buffer = text.strip()

    def on_stt_final(self, text: str) -> str:
        if text is None:
            text = ""
        with self._lock:
            self._cancel_timer()
            self._vad_pending = False
            self._stt_buffer = text.strip()
            tokens = _norm_tokens(self._stt_buffer)
            if not tokens:
                decision = 'IGNORE' if self.is_speaking else 'PASS'
                reason = 'empty_transcription'
                self._maybe_callback(decision, reason, text)
                return decision

            for t in tokens:
                if t in self.command_words:
                    decision = 'INTERRUPT'
                    reason = f'command_word:{t}'
                    self._maybe_callback(decision, reason, text)
                    return decision

            all_ignore = all((t in self.ignore_words) for t in tokens)
            if self.is_speaking:
                decision = 'IGNORE' if all_ignore else 'INTERRUPT'
                reason = 'all_ignore' if all_ignore else 'contains_non_ignore'
            else:
                decision = 'PASS'
                reason = 'silent_mode_pass'
            self._maybe_callback(decision, reason, text)
            return decision

    def _on_vad_timeout_internal(self):
        with self._lock:
            self._timer = None
            if not self._vad_pending:
                return
            tokens = _norm_tokens(self._stt_buffer)
            if not tokens:
                decision = 'IGNORE' if self.is_speaking else 'PASS'
                reason = 'timeout_empty_partial'
                self._vad_pending = False
                self._maybe_callback(decision, reason, self._stt_buffer)
                return

            for t in tokens:
                if t in self.command_words:
                    decision = 'INTERRUPT'
                    reason = f'partial_command:{t}'
                    self._vad_pending = False
                    self._maybe_callback(decision, reason, self._stt_buffer)
                    return

            all_ignore = all((t in self.ignore_words) for t in tokens)
            if self.is_speaking:
                decision = 'IGNORE' if all_ignore else 'INTERRUPT'
                reason = 'timeout_all_ignore' if all_ignore else 'timeout_contains_non_ignore'
            else:
                decision = 'PASS'
                reason = 'timeout_silent_pass'
            self._vad_pending = False
            self._maybe_callback(decision, reason, self._stt_buffer)
            return

    def on_vad_cancel(self):
        with self._lock:
            self._cancel_timer()
            self._vad_pending = False
            self._stt_buffer = ""

    def _maybe_callback(self, decision: str, reason: str, stt_text: str):
        if callable(self.on_decision):
            try:
                self.on_decision(decision, reason, stt_text)
            except Exception:
                pass

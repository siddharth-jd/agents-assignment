# examples/simulate_vad_stt.py
"""
Simulator that loads interrupt_filter.py directly (avoids importing livekit package)
This prevents opentelemetry import errors when testing the filter standalone.
"""

import importlib.util
import os
import time
import sys

# Path to the interrupt_filter.py file relative to repo root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(ROOT, "livekit-agents", "livekit", "agents", "interrupt_filter.py")

if not os.path.exists(MODULE_PATH):
    raise FileNotFoundError(f"interrupt_filter.py not found at: {MODULE_PATH}")

spec = importlib.util.spec_from_file_location("interrupt_filter", MODULE_PATH)
interrupt_filter_mod = importlib.util.module_from_spec(spec)
sys.modules["interrupt_filter"] = interrupt_filter_mod
spec.loader.exec_module(interrupt_filter_mod)

# get the class
InterruptFilter = interrupt_filter_mod.InterruptFilter

def print_cb(decision, reason, stt):
    print(f"  -> decision: {decision} | reason: {reason} | stt: {repr(stt)}")

f = InterruptFilter(validation_window_ms=200, on_decision=print_cb)

def run_case(name, is_speaking, stt_final=None, partials=None, final_delay_ms=100):
    print("\n---", name, "---")
    f.set_speaking(is_speaking)
    print("is_speaking:", is_speaking)
    f.on_vad_start()
    if partials:
        for p in partials:
            time.sleep(0.05)
            f.on_stt_partial(p)
            print("  partial:", p)
    if stt_final is not None:
        time.sleep(final_delay_ms / 1000.0)
        print("  delivering final:", stt_final)
        decision = f.on_stt_final(stt_final)
        print("  returned:", decision)
    else:
        print("  no final provided; waiting for timeout")
        time.sleep((f.validation_window_ms + 150) / 1000.0)

# Case 1: filler while speaking -> IGNORE
run_case("Filler while speaking (ok)", True, stt_final="okay")

# Case 2: silent + yeah -> PASS
run_case("Affirmation while silent (yeah)", False, stt_final="yeah")

# Case 3: interrupt while speaking -> INTERRUPT
run_case("Interrupt while speaking (no stop)", True, stt_final="no stop")

# Case 4: mixed -> INTERRUPT
run_case("Mixed while speaking (yeah wait a sec)", True, stt_final="yeah wait a second")

# Case 5: partials filler + timeout -> IGNORE
run_case("Partial only (filler) then timeout", True, stt_final=None, partials=["ye", "yeah"])

# Case 6: partials command + timeout -> INTERRUPT
run_case("Partial only (command) then timeout", True, stt_final=None, partials=["sto", "stop"])

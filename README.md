```markdown
# Interrupt Filter – Filler vs Command Interruption Handling  
### Assignment Submission – Siddharth

This repository contains an implementation of an **InterruptFilter** that correctly distinguishes  
between **backchannel/filler speech** (e.g., “yeah”, “ok”, “hmm”) and **true interruption commands**  
(e.g., “stop”, “wait”, “no”) while an agent is speaking.  

This prevents the agent from stuttering or pausing unnecessarily and ensures smooth, natural  
conversational behavior.

---

## 🎯 Objective (Assignment Requirement)

A speech agent must:

1. **Continue speaking** when the user says fillers like “yeah/ok/hmm” while the agent is talking.  
2. **Interrupt immediately** when the user gives command-like phrases (e.g., “stop”, “wait”).  
3. **Respond normally** to short words like “yeah” when the agent is *not* speaking.  
4. Avoid false positives from partial STT output.  
5. Provide proof via log output or a video.  

This project satisfies all of the above.

---

## 🧠 How the InterruptFilter Works

The filter operates based on:

- **Agent speaking state**
- **STT partials**
- **STT final transcriptions**
- A configurable list of:
  - **ignore words**: fillers (yeah, okay, hmm…)
  - **command words**: stop, wait, no…

### It returns one of three decisions:

| Decision     | Explanation |
|--------------|-------------|
| `IGNORE`     | Agent keeps speaking (filler detected) |
| `INTERRUPT`  | Agent stops immediately (command detected) |
| `PASS`       | Agent is silent → treat input as normal text |

### Behavior Summary

- Agent **speaking** + “yeah/ok/hmm” → **IGNORE**  
- Agent **speaking** + “stop/no/wait” → **INTERRUPT**  
- Agent **silent** + “yeah” → **PASS**  
- Partial prefix like “sto…” + timeout → **INTERRUPT**  
- Partial filler like “ye…” + timeout → **IGNORE**  

---

## 📁 File Structure

```

livekit-agents/
└── livekit/
└── agents/
└── interrupt_filter.py

examples/
└── simulate_vad_stt.py

interrupt_filter_simulator_log.txt

```

---

## ▶️ How to Test the Filter Locally

```

cd examples
set PYTHONPATH=%CD%..
python simulate_vad_stt.py

```

This produces all required test cases:

1. IGNORE → agent speaking + “yeah/okay”  
2. PASS → agent silent + “yeah”  
3. INTERRUPT → agent speaking + “stop” or “wait”  
4. Partial-only timeout cases  

The full output is in:

```

interrupt_filter_simulator_log.txt

````

---

## 🔧 Integration Into Agent Worker (Optional)

```python
from livekit.agents.interrupt_filter import InterruptFilter

def on_filter_decision(decision, reason, text):
    if decision == "INTERRUPT":
        agent.stop_speaking()
        agent.enter_listen_mode()
    elif decision == "PASS":
        agent.handle_user_input(text)

f = InterruptFilter(on_decision=on_filter_decision)
f.set_speaking(agent_is_speaking)
f.on_vad_start()
f.on_stt_partial(partial)
f.on_stt_final(final)
````

---

## 📝 Submission Details

**Branch:** `feature/interrupt-handler-siddharth`
**PR:** [https://github.com/Dark-Sys-Jenkins/agents-assignment/pull/96](https://github.com/Dark-Sys-Jenkins/agents-assignment/pull/96)

Includes:

* interrupt_filter.py
* simulate_vad_stt.py
* interrupt_filter_simulator_log.txt
* README.md (this file)

---

## ✅ Conclusion

All assignment requirements are completed:

* No stutter on fillers
* Correct interruption on command words
* State-aware behavior
* Clear documentation and proofs

```
```

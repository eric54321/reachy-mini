# Roadmap: talking to Reachy with a Strands agent

**North star:** say something to Reachy out loud and have it answer out loud and act
(nod, look, wiggle), driven by an LLM agent built with [Strands Agents](https://strandsagents.com).

Status legend: ✅ done · 🔜 next · ⬜ later · ❓ needs a decision or verification

---

## Where we are (Phase 0 — done ✅)

`scripts/strands_reachy.py` takes a typed sentence and the agent drives the robot.

- Tools: `wiggle_antennas`, `look`, `nod`, `speak`, `go_to_sleep`
- Model: Claude (`claude-haiku-5-5`) with the key in the `REACHY_ANTHROPIC_KEY` system env var.
  An `LLM_PROVIDER=ollama` switch exists in the code but is **untested and deferred** (see below)
- Voice out: local Piper TTS reused from `apps/voice_gesture` (free, no network)
- `--dry-run` runs the agent without touching the robot
- Runs in the existing `reachy` conda env

**Lessons that shaped the code (keep these in mind):**
- Connect by IP (`192.168.50.216`, `connection_mode="network"`). SDK auto-discovery is fooled by a
  Windows service holding `localhost:8000` and silently drives nothing.
- Call `enable_motors()` after connecting. Motors can be left disabled; commands are then accepted
  but nothing moves.
- One controller at a time. The `reachy-mini` MCP server and a script must not both drive the robot.
- Speaker volume is a robot-side setting (0–100, via the daemon's `/api/volume/*`); it was 100.

---

## Phase 1 — Harden the PoC ✅

Small, low-risk steps so the foundation is trustworthy before adding hearing.

- [x] Set speaker volume at startup (`REACHY_VOLUME`, default 20) instead of by hand
- [x] Measure baseline latency (time to first tool call and to finished reply) with Haiku, and
      keep a small timing log so later phases can be compared against it
- [x] Clean error handling: robot unreachable, key missing, tool failure → one clear message
- [x] Reuse `voice_gesture`'s emotion/gesture library as a `play_emotion` tool, so the agent has
      richer moves than nod/wiggle
- [x] Interactive mode: a REPL (`python scripts/strands_reachy.py` with no prompt) that keeps
      conversation memory between turns
- [x] Add `.env` loading so `REACHY_MINI_HOST`, `LLM_PROVIDER`, etc. work without system vars

**Done when:** 10 varied typed requests work in a row with Claude, and baseline latency is recorded.

---

## Phase 2 — Hear ✅

Get clean speech from the robot's microphone into text.

- [x] Verified how to capture audio from the robot via the SDK (`media_manager`); see Findings.
- [x] Capture: push-to-talk first (press Enter, speak, press Enter), voice activity detection later
- [x] Speech-to-text, local first: `faster-whisper` or similar (free, offline)
- [x] Decision: local STT (Anthropic's API does not do speech-to-text, so it is a separate component
      either way; local is free and fast enough).
- [x] A throwaway script that records 5 seconds and prints the transcript

**Done when:** speaking a sentence to the robot prints a correct transcript in under ~2 seconds.

**Findings (resolved):**
- Capture works via `media_manager.start_recording()` / `get_audio_sample()`: 16 kHz, 2 channels
  that are identical (effectively mono). The `No Reachy Mini Audio USB device found!` log line is
  harmless; capture and speaker still work.
- STT decision: local `faster-whisper` (`base.en`, int8, CPU), about 0.5 s for a few seconds of
  speech. Install with `pip install faster-whisper` in the `reachy` env.
- Speak within ~30 cm; quiet or distant speech gives an empty transcript. Silence is skipped
  because Whisper invents text from noise.
- Users need a cue for when to talk: the robot now beeps and lifts its antennas, and audio
  captured during the beep is discarded.
- Still open: automatic end-of-speech detection (moved into Phase 3).
- Code: `scripts/hear.py` (`listen(mini)` is the function Phase 3 imports).

---

## Phase 3 — Conversation loop ✅

Wire hearing, the agent and speaking into one loop.

- [x] Loop: listen → transcribe → agent → speak, with the agent still able to move
- [x] Stop the robot hearing itself (mute the mic while speaking, or echo handling)
- [x] Latency work: speak the first sentence while the rest is still being generated
- [x] Persona and system prompt: short answers, friendly, knows it is a small robot
- [x] Idle behavior: look attentive while listening, a small "thinking" move while waiting
- [~] Safe words and limits: "goodbye" / "stop listening" end the chat (done); a "stop" that halts
      a move in progress and a cap on tool calls per turn are **not built yet**

**Done when:** a back-and-forth conversation of several turns works with natural pauses.

**Findings:**
- `scripts/converse.py` runs the whole loop; say "goodbye" or stay silent for three listens to end it.
- Speed: Reachy starts speaking about 1.5 to 3 s after you stop talking (STT ~0.5 s). Replies are
  streamed and spoken sentence by sentence.
- Move tools run in a background queue and return immediately, so Reachy talks while it moves.
  Before they did, a reply with a move started speaking 4 to 9 s late.
- The mic only records while Reachy is silent, which avoids hearing itself.
- First words were being lost because the beep drain discarded 0.45 s; it is now 0.28 s. The
  speech model is also hinted with the usual commands. Moving to `small.en` (about 250 MB) is the
  next step if mishearing continues.
- Piper cannot laugh; "Ha ha" is spoken as words and the laughing animation does the rest.
- `HEAR_THRESHOLD` (default 0.004) tunes automatic end-of-speech detection.

---

## Phase 4 — See 🔜

Give the agent eyes.

- [ ] `look_at_camera` tool: grab a frame and send it to Claude as an image ("what do you see?")
- [ ] Head tracking as a tool (the SDK exposes start/stop head tracking — to be verified)
- [ ] Reuse the motion-detection code from `reachy_says` where it fits
- ❓ **Decision:** only look when asked (cheap, private) versus continuous watching (costly)

**Done when:** "what's in front of you?" gets a correct spoken answer.

---

## Phase 5 — Games and apps ⬜

- [ ] Make the agent a game master for Reachy Says (the AI picks and announces rounds)
- [ ] Expose the agent as a small web UI alongside the existing app pages
- [ ] Decide whether the agent replaces the `reachy-mini` MCP server or the two are unified
      (they cannot both hold the robot)
- [ ] Split the polished app into its own folder under `apps/` per the repo convention

---

## Open questions and risks

| Item | Why it matters |
|---|---|
| Audio USB device error | May block microphone capture; investigate before Phase 2 |
| Cost | Haiku is cheap per call, but a voice loop makes many calls; track spend |
| Latency | **Top priority.** STT + LLM + TTS in series can feel slow; see the performance principle below |
| Mic hearing the speaker | Echo can make the robot talk to itself |
| API key hygiene | Key lives in a system env var only; never in the repo or in chat |

## Performance principle

Speed is the priority, so **Claude (Haiku) is the model for now**. Local Ollama is deferred:
small local models are slower to respond on this machine's hardware and less reliable at tool
calling, and the voice loop is only pleasant if each turn feels quick. Revisit Ollama later only
if cost or offline use becomes a real need. Phase 1 timing numbers are the baseline for that decision.

Speed ideas to apply as we go: stream the reply and start speaking the first sentence early,
keep the system prompt and tool list short, keep one connection open for the whole session,
and run a nod or "thinking" move while waiting instead of standing still.

## Suggested order

Phase 1 → Phase 2 → Phase 3 gives a talking robot fastest. Phases 4 and 5 are independent
extras and can be picked up in either order, or by the kids as separate experiments.

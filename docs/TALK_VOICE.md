# Talk: voice messages and live conversation (hands-free)

You can **talk** to the superintendent bot by sending **voice messages** or **video notes** in Telegram. The bot transcribes your speech, runs the same graph (begin, ingest, help, etc.), and replies with text (and optionally with a voice message). This supports a **live conversation**:

- **Bot enacts changes** — expansion, ingest, improvements, etc.
- **Bot updates status** — what it did, what’s pending, key decisions.
- **Bot asks about next moves** — “What next? Say begin, status, continue, or approve/reject if I’m waiting on you.”

Useful when you can’t use your hands (driving, walking, etc.): you speak, the bot acts and reports back, then asks what you want next; you reply by voice or text and the loop continues.

---

## Live conversation flow

1. **You say something** (voice or text) — e.g. "Begin", "status", "approve", "what's next".
2. **The bot acts** — Runs expansion, reports status, commits/rejects if you said approve/reject.
3. **The bot replies** with what it did and **asks what next**: "What next? Say *begin*, *status*, *continue*, or *approve* / *reject* if I'm waiting on you."
4. **You reply** (voice or text) — "Continue", "approve", "reject", "begin", etc. The loop continues.

**Approval by voice** — When the bot is waiting for a key decision (e.g. commit KG changes), you can say **"approve"** or **"reject"** (or "yes"/"no") in a voice message or text; the bot treats it like pressing the Approve/Reject button.

---

## How it works (technical)

1. **You send a voice message or video note** (or text) in the chat with the bot.
2. **Voice** — The bot downloads the file via Telegram Bot API, transcribes with **OpenAI Whisper** (requires `OPENAI_API_KEY`).
3. **Approval check** — If the bot was waiting for approval and you said "approve"/"reject"/"yes"/"no", it applies that decision and continues.
4. **Same flow as text** — Otherwise the transcribed/text input is used as `user_input` and the graph runs (begin, help, ingest, etc.).
5. **Reply** — The bot sends the usual text response, plus a **"What next?"** line when `TALK_CONVERSATIONAL` or `TALK_REPLY_VOICE` is set. If **TALK_REPLY_VOICE** is set, it also sends a **voice reply** using OpenAI TTS. When the bot is waiting for approval (key decision), it still adds "What next? Say approve or reject…" and sends a voice version if TTS is on, so you can respond hands-free.

---

## Requirements

- **OPENAI_API_KEY** — Required for Whisper (transcription) and for TTS (voice replies). The manager/agents can use other keys; talk uses OpenAI for voice.
- **Telegram** — Voice messages and video notes are supported by the Bot API (no extra setup).

---

## Configuration

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Whisper (transcribe) and TTS (reply voice). |
| `TALK_REPLY_VOICE` | Set to `true` to also send a voice message reply (OpenAI TTS) and add "What next?" to replies. |
| `TALK_CONVERSATIONAL` | Set to `true` to add "What next? Say *begin*, *status*, *continue*, or *approve* / *reject*..." to every reply (hands-free conversation). |
| `TTS_MODEL` | Optional; default `tts-1`. |
| `TTS_VOICE` | Optional; one of `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`. |
| `LIVE_CALL_URL` | Optional. When set, saying *live call* or *start call* returns this link so you can join a real-time voice call (e.g. Jitsi, Daily.co, or your own call page). |

---

## Live voice call (link)

If you want a **real-time voice call** (not just voice messages in Telegram):

1. **Set `LIVE_CALL_URL`** in your environment to the call room URL (e.g. a Jitsi meet link, Daily.co room, or a custom page that runs a WebRTC/sip call).
2. **Say *live call* or *start call*** (voice or text) to the bot.
3. The bot replies with **a link** — open it to join the call.

If `LIVE_CALL_URL` is not set, the bot will tell you how to configure it and suggest using voice messages in the meantime.

The bot does not run the actual call server; it only offers the link. You (or your ops) provide the URL.

---

## Call bridge (transcribe + bot → Telegram)

When you say *live call* or *start call*, the bot sends **two** links (if `LIVE_CALL_URL` and `PUBLIC_URL` are set):

1. **Jitsi (or your) call link** — open it to join the voice room.
2. **Bridge link** — e.g. `https://your-app.com/call/bridge?room=lumi-superintendent-911&chat_id=…`

**What the bridge does (full hands-free back-and-forth)**

- You open the **bridge** page and tap **Start conversation** once; allow the mic.
- After that it’s **fully hands-free**: the mic stays on. You speak, then **pause about one second** when you’re done. The app detects the end of your turn (silence), **transcribes** (Whisper), **runs the same graph** (begin, status, approve, etc.), and **sends the reply to your Telegram chat**. The bridge **plays the bot’s reply out loud** (TTS), then keeps listening. You can speak again immediately — no buttons.
- So you get **continuous back-and-forth**: you talk → pause → hear the bot → talk → pause → hear the bot, with everything also mirrored in Telegram. Optional **Pause** button mutes the mic until you tap **Resume**.

**Requirements**

- `OPENAI_API_KEY` for Whisper and TTS.
- `PUBLIC_URL` (or `RAILWAY_URL`) so the bot can put your `chat_id` into the bridge link. Without it, the bot only sends the Jitsi link.

**Endpoints**

- `GET /call/bridge?room=…&chat_id=…` — serves the hands-free bridge page (always-on mic, silence = end of turn, TTS reply, then listen again).
- `POST /call/audio` — form: `audio` (file), `chat_id`. Returns `{ transcript, reply }` and sends the reply to Telegram.
- `GET /call/tts?text=…` — returns TTS audio (OGG) so the bridge can play the bot’s reply out loud.

---

## Limitations

- **Not a live phone call** — Telegram’s Bot API does not support real-time duplex voice calls. This is “send voice message → get text (and optional voice) reply,” not a continuous call.
- **Group voice chats** — To have the bot join a **group voice chat** (like a live call in a group), you’d need a separate stack (e.g. PyTgCalls + Telethon and a user/session account), which is outside this flow.
- **File size** — Telegram allows bot downloads up to 20MB; Whisper accepts the usual audio formats (OGG, MP3, etc.).

---

## Flow summary

```
You: [voice] "Begin"
  → Transcribe → "begin" → Graph runs (expansion, etc.)
  → Bot: [text] "Beginning. I'll expand... What next? Say begin, status, continue, or approve/reject if I'm waiting on you."
  → (if TALK_REPLY_VOICE) [voice] same via TTS

You: [voice] "Continue"
  → Transcribe → "continue" → Graph runs (another expansion)
  → Bot: [text] + "What next?" (+ optional voice)

You: [voice] "Approve"  (when bot is waiting for a key decision)
  → Treated as approval button → Graph commits/rejects → Bot confirms
```

See `app/voice.py` (transcribe, TTS) and `app/main.py` (webhook: voice/video_note handling, approval-via-voice, conversational tail).

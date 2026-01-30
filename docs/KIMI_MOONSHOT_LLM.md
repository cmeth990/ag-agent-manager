# Using Kimi / Moonshot as your LLM (cheaper, private agents)

**Manager vs agents:** The **manager** (orchestration / improvement agent) uses **OpenAI or Anthropic only**. The **agents** (extractor, source gatherer, domain scout, content fetcher, etc.) use **Moonshot when set**, then OpenAI, then Anthropic. So set **both** OpenAI or Anthropic (for manager) **and** MOONSHOT_API_KEY (for agents) to get this split.

You can also run everything on Kimi only (set only MOONSHOT_API_KEY) or everything on OpenAI/Anthropic (set only those).

## Why Kimi?

- **Cheaper** — Often lower cost than OpenAI/Anthropic for comparable quality.
- **Private** — Use the **global endpoint** `https://api.moonshot.ai/v1` so requests do not go to Chinese servers. We only use this base URL in this project.
- **OpenAI-compatible** — Same `POST /chat/completions` API; no code change beyond config.
- **Zero data retention** — Some teams use Kimi with explicit zero-data-retention workflows (e.g. delete-after-use, or enterprise arrangements). For one example of a “zero data retention process” with Kimi, see [this thread](https://x.com/alexatallah/status/2017238492909105396). Kimi’s policy states they do **not** use your conversations to train models; API logs may be retained for a period (e.g. 90 days) unless you have a different arrangement — confirm with Moonshot for strict zero retention.

## Setup

1. **Get an API key**  
   [Moonshot AI Open Platform](https://platform.moonshot.ai) → API Key Management.

2. **Configure .env** (use **only** Kimi if you want no OpenAI/Anthropic):
   ```bash
   # Use global endpoint only (we never use api.moonshot.cn)
   MOONSHOT_API_KEY=your_key_here
   # Optional: override model (default: moonshot-v1-8k)
   MOONSHOT_MODEL=moonshot-v1-8k
   ```
   Or `KIMI_API_KEY` instead of `MOONSHOT_API_KEY`.

3. **Priority**  
   LLM is chosen in this order: `OPENAI_API_KEY` → `ANTHROPIC_API_KEY` → `MOONSHOT_API_KEY` / `KIMI_API_KEY`.  
   To use **only** Kimi, leave OpenAI and Anthropic keys unset.

## Models (tiering)

| Tier     | Default model        | Env override                |
|----------|----------------------|-----------------------------|
| Cheap    | moonshot-v1-8k       | MOONSHOT_MODEL_CHEAP        |
| Mid      | moonshot-v1-32k      | MOONSHOT_MODEL_MID          |
| Expensive| moonshot-v1-128k     | MOONSHOT_MODEL_EXPENSIVE    |

Same task tiering as OpenAI/Anthropic (e.g. extraction → mid, triage → cheap).

## References

- [Kimi API docs](https://kimi-ai.chat/docs/api/)
- [Moonshot platform / quickstart](https://platform.moonshot.ai/docs/guide/start-using-kimi-api)
- [Kimi K2 / K2.5](https://github.com/MoonshotAI/Kimi-K2) — 128k context, tool use
- [Privacy policy (Kimi K2)](https://kimi-k2.ai/privacy-policy) — no training on your data; retention details there

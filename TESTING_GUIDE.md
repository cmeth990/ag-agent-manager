# Testing Guide: Parallel Agents

## ✅ Implementation Complete

The parallel agents test system is ready to use! It runs the Source Gatherer and Domain Scout agents simultaneously with real-time Telegram progress updates.

## Quick Start

### 1. Start Your Bot

Ensure your Telegram bot is running:

```bash
cd /Users/cmethod/LUMI_3/ag-agent-manager
python -m uvicorn app.main:app --reload
```

### 2. Test via Telegram

Send one of these commands to your bot:

```
/test agents
```

or

```
/test agents for Machine Learning
```

### 3. Watch Progress Updates

You'll receive real-time updates:
- 🚀 Initial status
- 📚 Source Gatherer started/completed
- 🔍 Domain Scout started/completed
- 📊 Final combined results

## What Happens

1. **Domain Selection**
   - If specified: uses that domain
   - Otherwise: picks random domain from taxonomy

2. **Parallel Execution**
   - Source Gatherer searches for sources
   - Domain Scout searches for new domains
   - Both run simultaneously using `asyncio.gather()`

3. **Progress Updates**
   - Sent to Telegram as each agent starts/completes
   - Includes status and domain information

4. **Results**
   - Combined summary of both agents
   - Source gathering statistics
   - Domain scouting statistics
   - Execution status

## Example Test Flow

### User sends: `/test agents`

**Bot responds:**
```
🚀 Starting parallel agent execution...

📌 Selected Domain: **Linear Algebra**
🔍 Running:
  • Source Gatherer Agent
  • Domain Scout Agent

⏳ Processing...
```

**Then:**
```
📚 Source Gatherer started
   Searching for sources: Linear Algebra
```

**Then:**
```
🔍 Domain Scout started
   Searching for new domains...
```

**Then:**
```
✅ Source Gatherer completed
   Found sources for: Linear Algebra
```

**Then:**
```
✅ Domain Scout completed
   Discovered new domains
```

**Finally:**
```
============================================================
📊 PARALLEL AGENT EXECUTION RESULTS
============================================================

🎯 Test Domain: **Linear Algebra**

============================================================
📚 SOURCE GATHERER AGENT
============================================================
[Full source gathering results...]

============================================================
🔍 DOMAIN SCOUT AGENT
============================================================
[Full domain scouting results...]

============================================================
📈 EXECUTION SUMMARY
============================================================

✅ Source Gatherer: completed
✅ Domain Scout: completed

🎉 Both agents completed successfully!
```

## Files Created/Modified

1. **`app/graph/parallel_agents.py`** (NEW)
   - `parallel_agents_node()` - Main parallel execution
   - `get_random_domain()` - Random domain selection
   - `send_progress_update()` - Telegram progress updates

2. **`app/graph/supervisor.py`** (MODIFIED)
   - Added `parallel_test` intent detection
   - Added `parallel_test` node to graph
   - Added routing for parallel test
   - Updated help text

3. **`app/graph/source_gatherer.py`** (MODIFIED)
   - Fixed missing `List` import

## Configuration

### Random Domain Selection

Edit `get_random_domain()` in `parallel_agents.py`:

```python
def get_random_domain() -> str:
    # Filter by category
    math_domains = DOMAIN_TAXONOMY.get("mathematics", {})
    return random.choice(list(math_domains.keys()))
```

### Progress Update Frequency

Currently sends updates at:
- Start of execution
- Start of each agent
- Completion of each agent
- Final summary

To add more frequent updates, modify the agent wrapper functions in `parallel_agents_node()`.

## Troubleshooting

### No Progress Updates

- Check `TELEGRAM_BOT_TOKEN` is set
- Verify bot is running and webhook is configured
- Check logs for Telegram API errors

### One Agent Fails

- Check logs for specific error
- Other agent continues independently
- Final summary shows error status
- Both results still returned

### Timeout Issues

- Increase timeout in agent functions
- Check network connectivity
- Verify API rate limits

## Testing Without Telegram

For local testing without Telegram:

```python
import asyncio
from app.graph.parallel_agents import parallel_agents_node

async def test():
    state = {
        "user_input": "/test agents for Machine Learning",
        "chat_id": None,  # No Telegram updates
        "intent": "parallel_test"
    }
    
    result = await parallel_agents_node(state)
    print(result["final_response"])

asyncio.run(test())
```

## Next Steps

1. **Test the system:**
   ```
   /test agents
   ```

2. **Try with specific domain:**
   ```
   /test agents for Quantum Computing
   ```

3. **Monitor progress:**
   - Watch Telegram for real-time updates
   - Check logs for detailed execution

4. **Review results:**
   - Source gathering statistics
   - Domain scouting discoveries
   - Combined summary

## Related Documentation

- `PARALLEL_AGENTS_TEST.md` - Detailed test documentation
- `SOURCE_GATHERING.md` - Source gatherer details
- `DOMAIN_SCOUT.md` - Domain scout details
- `README.md` - General bot setup

## Ready to Test! 🚀

The system is fully integrated and ready. Just send `/test agents` to your Telegram bot and watch it work!

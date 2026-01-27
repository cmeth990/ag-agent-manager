# Parallel Agents Test

## Overview

The parallel agents test runs both the **Source Gatherer** and **Domain Scout** agents simultaneously, providing real-time progress updates via Telegram.

## Usage

### Basic Test (Random Domain)

```
/test agents
```

This will:
1. Pick a random domain from the taxonomy
2. Run Source Gatherer for that domain
3. Run Domain Scout simultaneously
4. Send progress updates to Telegram
5. Return combined results

### Test with Specific Domain

```
/test agents for Machine Learning
```

This will use "Machine Learning" as the test domain instead of a random one.

## Progress Updates

During execution, you'll receive Telegram messages:

1. **Initial Status**
   ```
   🚀 Starting parallel agent execution...
   
   📌 Selected Domain: **Machine Learning**
   🔍 Running:
     • Source Gatherer Agent
     • Domain Scout Agent
   
   ⏳ Processing...
   ```

2. **Source Gatherer Started**
   ```
   📚 Source Gatherer started
      Searching for sources: Machine Learning
   ```

3. **Domain Scout Started**
   ```
   🔍 Domain Scout started
      Searching for new domains...
   ```

4. **Source Gatherer Completed**
   ```
   ✅ Source Gatherer completed
      Found sources for: Machine Learning
   ```

5. **Domain Scout Completed**
   ```
   ✅ Domain Scout completed
      Discovered new domains
   ```

6. **Final Results**
   ```
   ============================================================
   📊 PARALLEL AGENT EXECUTION RESULTS
   ============================================================
   
   🎯 Test Domain: **Machine Learning**
   
   ============================================================
   📚 SOURCE GATHERER AGENT
   ============================================================
   [Source gathering results...]
   
   ============================================================
   🔍 DOMAIN SCOUT AGENT
   ============================================================
   [Domain scouting results...]
   
   ============================================================
   📈 EXECUTION SUMMARY
   ============================================================
   
   ✅ Source Gatherer: completed
   ✅ Domain Scout: completed
   
   🎉 Both agents completed successfully!
   ```

## How It Works

1. **Domain Selection**
   - If domain specified: uses that domain
   - Otherwise: picks random domain from taxonomy

2. **Parallel Execution**
   - Uses `asyncio.gather()` to run both agents concurrently
   - Each agent runs independently
   - Progress updates sent asynchronously

3. **Error Handling**
   - If one agent fails, the other continues
   - Errors are reported in final summary
   - Progress updates include error notifications

4. **Result Compilation**
   - Combines results from both agents
   - Formats comprehensive summary
   - Includes execution status

## Example Output

### Source Gatherer Results
- Number of sources discovered
- Quality scores
- Priority rankings
- Free vs paid sources

### Domain Scout Results
- New domains discovered
- Confidence scores
- Source breakdown
- Recommendations

## Testing

### Local Test (Without Telegram)

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

### With Telegram

1. Ensure `TELEGRAM_BOT_TOKEN` is set
2. Send `/test agents` to your bot
3. Watch for progress updates
4. Receive final combined results

## Configuration

### Random Domain Selection

Edit `get_random_domain()` in `parallel_agents.py` to:
- Filter by category
- Filter by difficulty
- Use specific domain list

### Progress Update Frequency

Currently sends updates at:
- Start of each agent
- Completion of each agent
- Final summary

To add more frequent updates, modify the agent functions to send intermediate progress.

## Troubleshooting

### No Progress Updates

- Check `TELEGRAM_BOT_TOKEN` is set
- Verify `chat_id` is valid
- Check Telegram API connectivity

### One Agent Fails

- Check logs for specific error
- Other agent continues independently
- Final summary shows error status

### Timeout Issues

- Increase timeout in agent functions
- Check network connectivity
- Verify API rate limits

## Related Files

- `app/graph/parallel_agents.py` - Parallel execution logic
- `app/graph/source_gatherer.py` - Source gathering agent
- `app/graph/domain_scout_worker.py` - Domain scouting agent
- `app/graph/supervisor.py` - Graph routing
- `app/telegram.py` - Telegram messaging

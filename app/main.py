"""FastAPI server with Telegram webhook endpoint."""
import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from app.telegram import (
    send_message,
    answer_callback_query,
    build_approval_keyboard
)
from app.graph.supervisor import run_graph
from app.graph.state import AgentState

# Load environment variables from .env file
load_dotenv()


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Telegram KG Manager Bot")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "telegram-kg-manager"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """
    Handle Telegram webhook updates.
    
    Supports:
    - Text messages (commands)
    - Callback queries (button presses)
    """
    try:
        update = await request.json()
        logger.info(f"Received update: {update.get('update_id')}")
        
        # Handle message
        if "message" in update:
            message = update["message"]
            chat_id = message["chat"]["id"]
            text = message.get("text", "").strip()
            
            if not text:
                return JSONResponse({"ok": True})
            
            logger.info(f"Message from {chat_id}: {text[:100]}")
            
            # Create initial state
            initial_state: AgentState = {
                "user_input": text,
                "chat_id": str(chat_id),
                "intent": None,
                "task_queue": [],
                "working_notes": {},
                "proposed_diff": None,
                "diff_id": None,
                "approval_required": False,
                "approval_decision": None,
                "final_response": None,
                "error": None
            }
            
            # Run graph
            thread_id = str(chat_id)  # Use chat_id as thread_id for persistence
            try:
                result = await run_graph(initial_state, thread_id)
                logger.info(f"Graph execution completed for {chat_id}, intent: {result.get('intent')}")
            except Exception as e:
                logger.error(f"Error running graph: {e}", exc_info=True)
                await send_message(chat_id, f"❌ Error processing command: {str(e)[:200]}")
                return JSONResponse({"ok": True})
            
            # Check if approval is required
            if result.get("approval_required") and result.get("diff_id"):
                # Send approval message with buttons
                diff_id = result["diff_id"]
                response_text = result.get("final_response", "Please approve or reject the proposed changes.")
                
                keyboard = build_approval_keyboard(diff_id)
                try:
                    await send_message(chat_id, response_text, reply_markup=keyboard)
                except Exception as e:
                    logger.error(f"Error sending approval message: {e}")
            elif result.get("final_response"):
                # Send regular response
                try:
                    await send_message(chat_id, result["final_response"])
                    logger.info(f"Sent response to {chat_id}")
                except Exception as e:
                    logger.error(f"Error sending message to {chat_id}: {e}", exc_info=True)
            elif result.get("error"):
                # Send error message
                try:
                    await send_message(chat_id, f"❌ Error: {result['error']}")
                except Exception as e:
                    logger.error(f"Error sending error message: {e}")
            else:
                # Fallback
                try:
                    await send_message(chat_id, "Processing complete.")
                except Exception as e:
                    logger.error(f"Error sending fallback message: {e}")
            
            return JSONResponse({"ok": True})
        
        # Handle callback query (button press)
        if "callback_query" in update:
            callback_query = update["callback_query"]
            callback_id = callback_query["id"]
            chat_id = callback_query["message"]["chat"]["id"]
            data = callback_query.get("data", "")
            
            logger.info(f"Callback from {chat_id}: {data}")
            
            # Parse callback data: "approve:diff_id" or "reject:diff_id"
            if ":" in data:
                action, diff_id = data.split(":", 1)
            else:
                action = data
                diff_id = None
            
            # Answer callback immediately
            await answer_callback_query(callback_id, text="Processing...")
            
            thread_id = str(chat_id)
            
            # Load current state from checkpoint first
            from app.graph.supervisor import get_graph
            graph = get_graph()
            run_config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }
            
            # Get current checkpoint state to preserve proposed_diff
            try:
                checkpoint_state = await graph.aget_state(run_config)
                current_state = checkpoint_state.values if checkpoint_state else {}
            except Exception as e:
                logger.warning(f"Could not load checkpoint state: {e}, using empty state")
                current_state = {}
            
            # Create state update with approval decision
            # LangGraph will merge this with the checkpoint state automatically
            state_update: AgentState = {
                "chat_id": str(chat_id),  # Required field
                "approval_decision": action,  # This is what we're updating
                "task_queue": [],  # Required field
                "working_notes": {},  # Required field
            }
            
            # Preserve critical fields from checkpoint if available
            if current_state:
                if "proposed_diff" in current_state:
                    state_update["proposed_diff"] = current_state["proposed_diff"]
                if "diff_id" in current_state:
                    state_update["diff_id"] = current_state.get("diff_id") or diff_id
                if "user_input" in current_state:
                    state_update["user_input"] = current_state["user_input"]
                if "intent" in current_state:
                    state_update["intent"] = current_state["intent"]
            
            # Run graph - it will merge our update with checkpoint state
            result = await run_graph(state_update, thread_id)
            
            # Send result
            if result.get("final_response"):
                await send_message(chat_id, result["final_response"])
            elif result.get("error"):
                await send_message(chat_id, f"❌ Error: {result['error']}")
            else:
                await send_message(chat_id, "Processing complete.")
            
            return JSONResponse({"ok": True})
        
        # Unknown update type
        logger.warning(f"Unknown update type: {update.keys()}")
        return JSONResponse({"ok": True})
    
    except Exception as e:
        logger.error(f"Error handling webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("RELOAD", "false").lower() == "true"
    )

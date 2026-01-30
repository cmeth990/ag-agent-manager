"""FastAPI server with Telegram webhook endpoint."""
import sys
import os

# Set before any LangGraph import so default recursion limit is 30 (avoids 10000-step loop)
if "LANGGRAPH_DEFAULT_RECURSION_LIMIT" not in os.environ:
    os.environ["LANGGRAPH_DEFAULT_RECURSION_LIMIT"] = "30"

# Flush stderr immediately so Railway shows logs (Python buffers otherwise)
print("[startup] main.py loading", file=sys.stderr, flush=True)
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi import Query
from app.auth import require_admin_key
import uvicorn
from app.telegram import (
    send_message,
    answer_callback_query,
    build_approval_keyboard
)
from app.graph.supervisor import run_graph
from app.graph.state import AgentState
from app.mission import get_crucial_decision_label
from app.task_state import set_task_status, TaskStatus, TaskStateRegistry


def _trigger_mission_continue(chat_id: str) -> None:
    """Run mission work (e.g. expansion) in the meantime while a key decision is pending."""
    from app.queue.mission_continue import trigger_mission_continue
    trigger_mission_continue(chat_id)

# Load .env: first from project root (ag-agent-manager/.env), then cwd (overrides for deploy)
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")
load_dotenv()


# Configure logging to stderr so Railway captures it (use PYTHONUNBUFFERED=1 in Procfile)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
    force=True,
)
logger = logging.getLogger(__name__)
logger.info("App module loaded")

# Durable queue: when True and DATABASE_URL set, webhook enqueues and worker processes
USE_DURABLE_QUEUE = os.getenv("USE_DURABLE_QUEUE", "false").lower() == "true"
_worker_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background worker when durable queue is enabled."""
    global _worker_task
    if USE_DURABLE_QUEUE and os.getenv("DATABASE_URL"):
        from app.queue.worker import start_worker_background
        # task_type=None so worker processes both graph_run and mission_continue
        _worker_task = start_worker_background(task_type=None)
        logger.info("Durable queue worker started (graph_run + mission_continue)")
    yield
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Durable queue worker stopped")


app = FastAPI(title="Telegram KG Manager Bot", lifespan=lifespan)


def _log_recursion_diagnostics():
    """Log recursion diagnostics once at startup for deploy verification."""
    from app.graph.supervisor import RECURSION_DIAG_VERSION
    env_val = os.environ.get("LANGGRAPH_DEFAULT_RECURSION_LIMIT")
    try:
        import langgraph._internal._config as _lg_config
        default = getattr(_lg_config, "DEFAULT_RECURSION_LIMIT", None)
        patched = getattr(_lg_config, "_recursion_cap_patched", False)
    except Exception:
        default = None
        patched = False
    logger.info(
        "[%s] startup: env LANGGRAPH_DEFAULT_RECURSION_LIMIT=%s, langgraph DEFAULT_RECURSION_LIMIT=%s, patched=%s",
        RECURSION_DIAG_VERSION, env_val, default, patched,
    )


@app.on_event("startup")
async def _startup_recursion_diag():
    """Log recursion diagnostics on startup (after app is ready)."""
    try:
        _log_recursion_diagnostics()
    except Exception as e:
        logger.warning("Startup recursion diag: %s", e)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "telegram-kg-manager"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/diagnostics/recursion")
async def diagnostics_recursion():
    """
    Diagnose recursion limit: env, LangGraph default, and whether ensure_config is patched.
    Hit this after deploy to confirm which code is running and why limit might be 10000.
    """
    from app.graph.supervisor import RECURSION_DIAG_VERSION
    try:
        import langgraph._internal._config as _lg_config
        default_limit = getattr(_lg_config, "DEFAULT_RECURSION_LIMIT", None)
        patched = getattr(_lg_config, "_recursion_cap_patched", False)
    except Exception as e:
        default_limit = None
        patched = False
        logger.warning("diagnostics/recursion: %s", e)
    return {
        "recursion_diag_version": RECURSION_DIAG_VERSION,
        "env_LANGGRAPH_DEFAULT_RECURSION_LIMIT": os.environ.get("LANGGRAPH_DEFAULT_RECURSION_LIMIT"),
        "langgraph_DEFAULT_RECURSION_LIMIT": default_limit,
        "ensure_config_patched": patched,
        "hint": "If langgraph_DEFAULT_RECURSION_LIMIT is 10000, env was not set before first import. "
                "If patched is True, ensure_config caps result; if still 10000, patch may not be applied in this process.",
    }


# ----- Call bridge: transcribe voice from bridge page, run graph, sync to Telegram -----
_CALL_BRIDGE_HTML_PATH = Path(__file__).resolve().parent / "static" / "call_bridge.html"


@app.get("/call/bridge", response_class=HTMLResponse)
async def call_bridge(
    room: str = Query(default="lumi-superintendent-911", description="Jitsi room name"),
    chat_id: str = Query(default="", description="Telegram chat_id for syncing replies"),
):
    """
    Serve the call bridge page. User opens mic, speaks; we transcribe, run the bot, send reply to Telegram.
    Open with ?room=...&chat_id=... (chat_id from the link the bot sends when you say 'live call').
    """
    if not _CALL_BRIDGE_HTML_PATH.exists():
        raise HTTPException(status_code=404, detail="Bridge page not found")
    html = _CALL_BRIDGE_HTML_PATH.read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.post("/call/audio")
async def call_audio(
    audio: UploadFile = File(...),
    chat_id: str = Form(...),
):
    """
    Receive audio from the bridge page: transcribe (Whisper), run graph (same as Telegram), send reply to Telegram.
    Returns { transcript, reply }.
    """
    if not chat_id or not chat_id.strip():
        raise HTTPException(status_code=400, detail="chat_id required")
    try:
        body = await audio.read()
    except Exception as e:
        logger.warning("Call bridge: failed to read audio: %s", e)
        raise HTTPException(status_code=400, detail="Failed to read audio")
    if len(body) < 100:
        raise HTTPException(status_code=400, detail="Audio too short")
    from app.voice import transcribe_audio
    transcript = await transcribe_audio(body, filename_hint=audio.filename or "audio.webm")
    if not transcript or not transcript.strip():
        return JSONResponse(
            status_code=200,
            content={"transcript": "", "reply": "Couldn't transcribe that. Try again or say something clearer."},
        )
    thread_id = chat_id.strip()
    initial_state: AgentState = {
        "user_input": transcript.strip(),
        "chat_id": thread_id,
        "intent": None,
        "task_queue": [],
        "working_notes": {},
        "proposed_diff": None,
        "diff_id": None,
        "approval_required": False,
        "approval_decision": None,
        "final_response": None,
        "error": None,
    }
    try:
        result = await run_graph(initial_state, thread_id, config={"recursion_limit": 30})
    except Exception as e:
        logger.exception("Call bridge: graph run failed")
        return JSONResponse(
            status_code=200,
            content={"transcript": transcript, "reply": f"Error: {str(e)[:200]}"},
        )
    reply = result.get("final_response") or result.get("error") or "Done."
    try:
        await send_message(int(chat_id), f"📞 **Call:** {transcript}\n\n{reply}", parse_mode="Markdown")
    except Exception as e:
        logger.warning("Call bridge: failed to send to Telegram: %s", e)
    return JSONResponse(content={"transcript": transcript, "reply": reply})


@app.get("/call/tts")
async def call_tts(text: str = Query(..., min_length=1, max_length=2000)):
    """Return TTS audio (OGG) for the given text. Used by the bridge page to play bot replies."""
    from app.voice import text_to_speech
    audio_bytes = await text_to_speech(text[:2000])
    if not audio_bytes:
        raise HTTPException(status_code=503, detail="TTS not available")
    return Response(content=audio_bytes, media_type="audio/ogg")


@app.get("/telemetry/tasks", dependencies=[Depends(require_admin_key)])
async def telemetry_tasks(limit: int = 20):
    """
    Telemetry: recent task states (for supervisor/state summarization).
    Does not rely on chat memory.
    """
    tasks = TaskStateRegistry.list_recent(limit=limit)
    return {"tasks": tasks, "count": len(tasks)}


@app.get("/telemetry/state", dependencies=[Depends(require_admin_key)])
async def telemetry_state():
    """
    Comprehensive system state from telemetry.
    Supervisor can query this instead of relying on chat memory.
    """
    from app.telemetry.aggregator import get_system_state
    return get_system_state()


@app.get("/telemetry/summary", dependencies=[Depends(require_admin_key)])
async def telemetry_summary():
    """
    Human-readable summary of system state from telemetry.
    """
    from app.telemetry.aggregator import summarize_state
    return {"summary": summarize_state()}


@app.get("/kg/versions", dependencies=[Depends(require_admin_key)])
async def list_kg_versions(limit: int = 20):
    """
    List recent KG versions (changelog).
    """
    from app.kg.rollback import list_versions
    return await list_versions(limit=limit)


@app.get("/kg/versions/{version}", dependencies=[Depends(require_admin_key)])
async def get_kg_version(version: int):
    """
    Get information about a specific KG version.
    """
    from app.kg.rollback import get_version_info
    info = await get_version_info(version)
    if not info:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")
    return info


@app.post("/kg/rollback/{target_version}", dependencies=[Depends(require_admin_key)])
async def rollback_kg(target_version: int):
    """
    Rollback KG to a specific version.
    
    Args:
        target_version: Version number to rollback to (0 = initial state)
    """
    from app.kg.rollback import rollback_to_version
    result = await rollback_to_version(target_version)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Rollback failed"))
    return result


@app.get("/queue/dead-letter", dependencies=[Depends(require_admin_key)])
async def list_dead_letter_queue(limit: int = 50):
    """List tasks in dead-letter queue (for triage)."""
    from app.queue.triage import list_dead_letter_tasks
    tasks = await list_dead_letter_tasks(limit=limit)
    return {"tasks": tasks, "count": len(tasks)}


@app.post("/queue/triage/{task_id}", dependencies=[Depends(require_admin_key)])
async def triage_task(task_id: str, action: str = "retry", updated_payload: Optional[Dict[str, Any]] = None):
    """
    Triage a dead-letter queue task.
    
    Actions: "retry", "update_payload", "skip"
    """
    from app.queue.triage import triage_dead_letter_task
    result = await triage_dead_letter_task(task_id, action, updated_payload=updated_payload)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Triage failed"))
    return result


@app.get("/queue/stuck", dependencies=[Depends(require_admin_key)])
async def list_stuck_tasks(threshold_minutes: int = 30):
    """List stuck tasks (no heartbeat recently)."""
    from app.queue.heartbeat import monitor_stuck_tasks
    result = await monitor_stuck_tasks(stuck_threshold_minutes=threshold_minutes, auto_retry=False)
    return result


def _progress_dashboard_html() -> str:
    """Single-page drill-down dashboard: zoom by level via expand/collapse."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KG Progress</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; margin: 1rem; background: #1a1a2e; color: #eee; }
    h1 { font-size: 1.25rem; margin-bottom: 0.5rem; }
    .summary { color: #aaa; font-size: 0.9rem; margin-bottom: 1rem; }
    .tree { list-style: none; padding-left: 0; margin: 0; }
    .tree li { margin: 0.25rem 0; }
    .node { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.6rem; border-radius: 6px; cursor: pointer; user-select: none; }
    .node:hover { background: rgba(255,255,255,0.08); }
    .node .count { color: #7dd3fc; font-variant-numeric: tabular-nums; min-width: 2.5rem; text-align: right; }
    .node .toggle { width: 1rem; text-align: center; }
    .node .toggle::before { content: "▶"; font-size: 0.7rem; }
    .node.open .toggle::before { content: "▼"; }
    .children { padding-left: 1.25rem; border-left: 1px solid rgba(255,255,255,0.15); margin-left: 0.5rem; }
    .children.hidden { display: none; }
    .level-0 .node { font-weight: 600; }
    .level-1 .node { font-size: 0.95rem; }
    .level-2 .node { font-size: 0.9rem; color: #ccc; }
    .error { color: #f87171; }
    .loading { color: #aaa; }
  </style>
</head>
<body>
  <h1>Knowledge Graph Progress</h1>
  <p class="summary" id="summary">Loading…</p>
  <ul class="tree" id="tree"></ul>
  <script>
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token") || "";
    if (!token) {
      document.getElementById("summary").textContent = "Missing or invalid link. Request a new link from the bot.";
      document.getElementById("summary").className = "summary error";
    } else {
      fetch("/graph/progress/data?token=" + encodeURIComponent(token))
        .then(r => r.ok ? r.json() : Promise.reject(new Error("Unauthorized")))
        .then(data => {
          document.getElementById("summary").textContent = "Total: " + (data.total || 0) + " nodes. Click a row to zoom in/out.";
          renderTree(document.getElementById("tree"), data, 0);
        })
        .catch(() => {
          document.getElementById("summary").textContent = "Link expired or invalid. Request a new link from the bot.";
          document.getElementById("summary").className = "summary error";
        });
    }
    function renderTree(ul, node, level) {
      if (!node) return;
      const children = node.children || [];
      const hasChildren = children.length > 0;
      const count = node.count != null ? node.count : node.total;
      const li = document.createElement("li");
      li.className = "level-" + Math.min(level, 2);
      const div = document.createElement("div");
      div.className = "node" + (hasChildren && level === 0 ? " open" : "");
      div.innerHTML = "<span class=\"toggle\"></span><span class=\"label\">" + (node.label || "KG") + "</span><span class=\"count\">" + (count != null ? count : "") + "</span>";
      li.appendChild(div);
      if (hasChildren) {
        const childUl = document.createElement("ul");
        childUl.className = "children" + (level === 0 ? "" : " hidden");
        children.forEach(c => renderTree(childUl, c, level + 1));
        li.appendChild(childUl);
        div.addEventListener("click", () => {
          div.classList.toggle("open");
          childUl.classList.toggle("hidden");
        });
      }
      ul.appendChild(li);
    }
  </script>
</body>
</html>"""


@app.get("/graph/progress")
async def graph_progress_dashboard(token: Optional[str] = Query(None)):
    """
    Private dashboard: KG progress by hierarchy level. Requires valid token (from bot link).
    Zoom in/out by expanding levels.
    """
    from app.kg.progress import validate_progress_view_token
    if not token or not validate_progress_view_token(token):
        raise HTTPException(status_code=403, detail="Invalid or expired link. Request a new link from the bot.")
    return HTMLResponse(_progress_dashboard_html())


@app.get("/graph/progress/data")
async def graph_progress_data(token: Optional[str] = Query(None)):
    """JSON tree for progress dashboard. Requires valid token."""
    from app.kg.progress import validate_progress_view_token, get_progress_tree
    if not token or not validate_progress_view_token(token):
        raise HTTPException(status_code=403, detail="Invalid or expired token.")
    return get_progress_tree()


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
        logger.info(f"Update keys: {list(update.keys())}")
        logger.info(f"Full update: {update}")
        
        # Handle message
        if "message" in update:
            message = update["message"]
            chat_id = message["chat"]["id"]
            text = message.get("text", "").strip()

            # Talk: voice or video note → download, transcribe, use as text
            if not text and (message.get("voice") or message.get("video_note")):
                voice_or_note = message.get("voice") or message.get("video_note")
                file_id = voice_or_note.get("file_id")
                if file_id:
                    try:
                        from app.telegram import get_file, download_telegram_file
                        from app.voice import transcribe_audio
                        file_info = await get_file(file_id)
                        file_path = file_info.get("file_path")
                        if file_path:
                            audio_bytes = await download_telegram_file(file_path)
                            ext = "ogg" if "ogg" in (file_path or "").lower() else "m4a"
                            transcribed = await transcribe_audio(audio_bytes, filename_hint=f"voice.{ext}")
                            if transcribed:
                                text = transcribed.strip()
                                logger.info(f"Voice from {chat_id} transcribed: {text[:80]}")
                            else:
                                try:
                                    await send_message(chat_id, "Couldn't transcribe that. Try again or type your message.")
                                except Exception:
                                    pass
                                return JSONResponse({"ok": True})
                        else:
                            try:
                                await send_message(chat_id, "Couldn't get voice file. Try again.")
                            except Exception:
                                pass
                            return JSONResponse({"ok": True})
                    except Exception as e:
                        logger.warning("Voice handling failed: %s", e)
                        try:
                            await send_message(chat_id, "Voice message failed. Try typing instead.")
                        except Exception:
                            pass
                        return JSONResponse({"ok": True})

            if not text:
                return JSONResponse({"ok": True})

            logger.info(f"Message from {chat_id}: {text[:100]}")
            thread_id = str(chat_id)

            # Live conversation: if we're waiting for approval, "approve"/"reject" (voice or text) counts as the decision
            text_lower = text.strip().lower()
            if text_lower in ("approve", "reject", "yes", "no"):
                action = "approve" if text_lower in ("approve", "yes") else "reject"
                try:
                    from app.graph.supervisor import get_graph
                    graph = get_graph()
                    run_config = {"configurable": {"thread_id": thread_id}}
                    checkpoint_state = await graph.aget_state(run_config)
                    current_state = checkpoint_state.values if checkpoint_state else {}
                except Exception:
                    current_state = {}
                if current_state.get("approval_required") and not current_state.get("approval_decision"):
                    state_update: AgentState = {
                        "chat_id": thread_id,
                        "approval_decision": action,
                        "task_queue": [],
                        "working_notes": {},
                    }
                    if current_state:
                        for k in ("proposed_diff", "proposed_changes", "improvement_plan", "diff_id", "user_input", "intent", "crucial_decision_type", "crucial_decision_context"):
                            if k in current_state:
                                state_update[k] = current_state[k]
                    set_task_status(thread_id, TaskStatus.IN_PROGRESS, agent="supervisor")
                    try:
                        result = await run_graph(state_update, thread_id, config={"recursion_limit": 30})
                        set_task_status(thread_id, TaskStatus.COMPLETED, agent="supervisor")
                    except Exception as e:
                        set_task_status(thread_id, TaskStatus.FAILED, error=str(e)[:500])
                        try:
                            await send_message(chat_id, f"❌ Error: {str(e)[:200]}")
                        except Exception:
                            pass
                        return JSONResponse({"ok": True})
                    if result.get("final_response"):
                        try:
                            await send_message(chat_id, result["final_response"])
                        except Exception:
                            pass
                    elif result.get("error"):
                        try:
                            await send_message(chat_id, f"❌ {result['error']}")
                        except Exception:
                            pass
                    return JSONResponse({"ok": True})
                # else: not waiting for approval, fall through to normal flow

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
            
            # Durable queue: enqueue and return; worker will run graph and send response
            if USE_DURABLE_QUEUE and os.getenv("DATABASE_URL"):
                try:
                    from app.queue.durable_queue import get_queue
                    from app.queue.worker import TASK_TYPE_GRAPH_RUN
                    queue = get_queue()
                    payload = dict(initial_state)
                    task_id = queue.enqueue(
                        TASK_TYPE_GRAPH_RUN,
                        payload,
                        agent="supervisor",
                        max_retries=3,
                    )
                    logger.info(f"Enqueued task {task_id} for chat_id {chat_id}")
                    return JSONResponse({"ok": True, "queued": True, "task_id": task_id})
                except Exception as e:
                    logger.error(f"Enqueue failed, falling back to inline: {e}")
            
            # Inline: run graph and send response
            set_task_status(thread_id, TaskStatus.IN_PROGRESS, agent="supervisor")
            try:
                result = await run_graph(
                    initial_state, thread_id,
                    config={"recursion_limit": 30}
                )
                set_task_status(thread_id, TaskStatus.COMPLETED, agent="supervisor")
                logger.info(f"Graph execution completed for {chat_id}, intent: {result.get('intent')}")
            except Exception as e:
                set_task_status(thread_id, TaskStatus.FAILED, error=str(e)[:500])
                logger.error(f"Error running graph: {e}", exc_info=True)
                # Clean error message - remove newlines and special chars
                error_msg = str(e).replace('\n', ' ').replace('\r', ' ')[:200]
                if "Recursion limit" in error_msg or "10000" in error_msg:
                    from app.graph.supervisor import get_recursion_diag_string
                    error_msg = f"{error_msg}\n\n{get_recursion_diag_string()}"
                try:
                    await send_message(chat_id, f"❌ Error processing command: {error_msg}")
                except Exception as send_err:
                    logger.error(f"Failed to send error message: {send_err}")
                return JSONResponse({"ok": True})
            
            # Check if approval is required (for both diff and improvements)
            if result.get("approval_required") and (result.get("diff_id") or result.get("proposed_changes")):
                # Send approval message with buttons; prefix with key decision label when set
                diff_id = result.get("diff_id") or f"improve_{hash(result.get('user_input', '')) % 10000}"
                response_text = result.get("final_response", "Please approve or reject the proposed changes.")
                crucial_type = result.get("crucial_decision_type")
                if crucial_type:
                    label = get_crucial_decision_label(crucial_type)
                    response_text = f"🔑 **Key decision: {label}**\n\n{response_text}"
                # Hands-free: add "What next?" so user can say approve/reject by voice
                if os.getenv("TALK_CONVERSATIONAL", "").lower() in ("true", "1", "yes") or os.getenv("TALK_REPLY_VOICE", "").lower() in ("true", "1", "yes"):
                    response_text += "\n\n**What next?** Say *approve* or *reject* (or *begin*, *status*, *continue*)."
                keyboard = build_approval_keyboard(diff_id)
                try:
                    await send_message(chat_id, response_text, reply_markup=keyboard, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Error sending approval message: {e}")
                # Optional TTS so user hears the ask when they can't look at the screen
                if os.getenv("TALK_REPLY_VOICE", "").lower() in ("true", "1", "yes"):
                    try:
                        from app.voice import text_to_speech
                        from app.telegram import send_voice
                        voice_bytes = await text_to_speech(response_text[:4096])
                        if voice_bytes:
                            await send_voice(chat_id, voice_bytes, caption=None)
                    except Exception as tts_err:
                        logger.warning("TTS reply (approval) failed: %s", tts_err)
                # Continue mission work in the meantime (expansion/discovery) so we get closer while user decides
                _trigger_mission_continue(chat_id)
            elif result.get("final_response"):
                # Send regular response (text, and optionally voice if TALK_REPLY_VOICE)
                response_text = result["final_response"]
                if os.getenv("TALK_CONVERSATIONAL", "").lower() in ("true", "1", "yes") or os.getenv("TALK_REPLY_VOICE", "").lower() in ("true", "1", "yes"):
                    response_text += "\n\n**What next?** Say *begin*, *status*, *continue*, or *approve* / *reject* if I'm waiting on you."
                try:
                    await send_message(chat_id, response_text, parse_mode="Markdown")
                    logger.info(f"Sent response to {chat_id}")
                except Exception as e:
                    logger.error(f"Error sending message to {chat_id}: {e}", exc_info=True)
                if os.getenv("TALK_REPLY_VOICE", "").lower() in ("true", "1", "yes"):
                    try:
                        from app.voice import text_to_speech
                        from app.telegram import send_voice
                        voice_bytes = await text_to_speech(response_text[:4096])
                        if voice_bytes:
                            await send_voice(chat_id, voice_bytes, caption=None)
                    except Exception as tts_err:
                        logger.warning("TTS reply failed: %s", tts_err)
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
                if "proposed_changes" in current_state:
                    state_update["proposed_changes"] = current_state["proposed_changes"]
                if "improvement_plan" in current_state:
                    state_update["improvement_plan"] = current_state["improvement_plan"]
                if "diff_id" in current_state:
                    state_update["diff_id"] = current_state.get("diff_id") or diff_id
                if "user_input" in current_state:
                    state_update["user_input"] = current_state["user_input"]
                if "intent" in current_state:
                    state_update["intent"] = current_state["intent"]
                if "crucial_decision_type" in current_state:
                    state_update["crucial_decision_type"] = current_state["crucial_decision_type"]
                if "crucial_decision_context" in current_state:
                    state_update["crucial_decision_context"] = current_state["crucial_decision_context"]
            
            # Run graph - it will merge our update with checkpoint state
            result = await run_graph(
                state_update, thread_id,
                config={"recursion_limit": 30}
            )
            
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

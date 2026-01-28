"""
Improvement Agent Node
Handles conversational improvement requests and makes code changes.
"""
import logging
import os
import subprocess
import json
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from app.graph.state import AgentState
from app.llm.client import get_llm_for_agent
from app.validation.agent_outputs import validate_improvement_agent_output, ValidationError
from app.security.tools import require_tool, SecurityError

logger = logging.getLogger(__name__)

# Base directory for the project
PROJECT_ROOT = Path(__file__).parent.parent.parent


async def improvement_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Conversational agent that understands improvement requests and makes code changes.
    
    Capabilities:
    - Understands natural language improvement requests
    - Analyzes codebase to find relevant files
    - Proposes and implements code changes
    - Requests approval before committing
    """
    user_input = state.get("user_input", "")
    chat_id = state.get("chat_id")
    working_notes = state.get("working_notes") or {}
    prior_context = working_notes.get("improvement_context") or working_notes.get("prior_improvement") or ""
    
    logger.info(f"Improvement agent processing request: {user_input[:100]}...")
    
    llm = get_llm_for_agent(state, agent_name="improvement_agent")
    if not llm:
        return {
            "error": "No LLM configured",
            "final_response": "❌ Improvement agent needs an LLM (set OPENAI_API_KEY or ANTHROPIC_API_KEY in Railway Variables)."
        }

    # Step 1: Understand the request and plan changes (include prior conversation if any)
    analysis_prompt = f"""You are a code improvement agent. Analyze this user request and create a plan:

User Request: {user_input}
{f'Prior context from this conversation: {prior_context}' if prior_context else ''}

Your task:
1. Understand what improvement is being requested
2. Identify which files/modules need to be changed
3. Create a step-by-step plan for implementing the improvement
4. Consider the codebase structure (Python, async/await patterns, error handling)

Project Structure:
- app/graph/ - LangGraph agent nodes
- app/kg/ - Knowledge graph modules
- app/llm/ - LLM client
- app/telegram/ - Telegram bot integration

Respond in JSON format:
{{
    "understanding": "Brief summary of what the user wants",
    "files_to_modify": ["path/to/file1.py", "path/to/file2.py"],
    "files_to_read": ["path/to/file3.py"],  // Files to read for context
    "plan": [
        "Step 1: ...",
        "Step 2: ...",
        "Step 3: ..."
    ],
    "risk_level": "low|medium|high",  // Risk of breaking things
    "estimated_changes": "Brief description of code changes"
}}
"""
    
    try:
        response = await llm.ainvoke(analysis_prompt)
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = str(response)
        
        # Parse JSON response
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            plan = json.loads(json_match.group())
        else:
            return {
                "error": "Failed to parse improvement plan from LLM",
                "final_response": "❌ Could not understand the improvement request. Please be more specific."
            }
    except Exception as e:
        logger.error(f"Error analyzing improvement request: {e}")
        return {
            "error": str(e),
            "final_response": f"❌ Error analyzing request: {str(e)[:200]}"
        }
    
    # Step 2: Read relevant files for context
    files_content = {}
    files_to_read = plan.get("files_to_read", []) + plan.get("files_to_modify", [])
    
    for file_path in files_to_read:
        full_path = PROJECT_ROOT / file_path
        if full_path.exists() and full_path.is_file():
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    files_content[file_path] = f.read()
            except Exception as e:
                logger.warning(f"Could not read {file_path}: {e}")
    
    # Step 3: Generate code changes
    if not plan.get("files_to_modify"):
        return {
            "final_response": f"✅ Analysis complete:\n\n{plan.get('understanding', 'No changes needed')}\n\nNo files need to be modified."
        }
    
    # Generate changes for each file
    proposed_changes = {}
    
    for file_path in plan.get("files_to_modify", []):
        current_content = files_content.get(file_path, "")
        
        change_prompt = f"""Based on this improvement request and the current code, generate the modified code.

User Request: {user_input}
Improvement Plan: {json.dumps(plan, indent=2)}

File to modify: {file_path}
Current code:
```python
{current_content[:4000]}  # Limit to avoid token limits
```

Requirements:
1. Make the requested improvement
2. Maintain existing code style and patterns
3. Add proper error handling
4. Add logging where appropriate
5. Preserve existing functionality
6. Follow Python best practices

Respond with ONLY the complete modified file content in a code block:
```python
// Complete file content here
```
"""
        
        try:
            response = await llm.ainvoke(change_prompt)
            if hasattr(response, 'content'):
                modified_content = response.content
            else:
                modified_content = str(response)
            
            # Extract code from markdown code block
            code_match = re.search(r'```python\n(.*?)\n```', modified_content, re.DOTALL)
            if code_match:
                proposed_changes[file_path] = code_match.group(1)
            else:
                # Try without language tag
                code_match = re.search(r'```\n(.*?)\n```', modified_content, re.DOTALL)
                if code_match:
                    proposed_changes[file_path] = code_match.group(1)
                else:
                    # Use entire response if no code block found
                    proposed_changes[file_path] = modified_content.strip()
            
            logger.info(f"Generated changes for {file_path}")
        except Exception as e:
            logger.error(f"Error generating changes for {file_path}: {e}")
            return {
                "error": f"Failed to generate changes for {file_path}: {str(e)}",
                "final_response": f"❌ Error generating code changes: {str(e)[:200]}"
            }
    
    # Step 4: Create diff summary
    diff_summary = create_diff_summary(files_content, proposed_changes, plan)
    
    # Step 5: Store proposed changes and request approval
    out = {
        "proposed_changes": proposed_changes,
        "improvement_plan": plan,
        "approval_required": True,
        "diff_id": f"improve_{hash(user_input) % 10000}",
        "final_response": diff_summary
    }
    try:
        return validate_improvement_agent_output(out)
    except ValidationError as e:
        logger.warning(f"Improvement agent output validation failed: {e}")
        return {
            "error": str(e),
            "final_response": f"❌ Validation error: {e}. Please try again with a clearer request."
        }


def create_diff_summary(
    original_files: Dict[str, str],
    proposed_changes: Dict[str, str],
    plan: Dict[str, Any]
) -> str:
    """Create a human-readable summary of proposed changes."""
    summary_parts = []
    summary_parts.append("🔧 **Proposed Code Improvements**\n")
    summary_parts.append(f"📋 **Understanding:** {plan.get('understanding', 'N/A')}\n")
    summary_parts.append(f"⚠️ **Risk Level:** {plan.get('risk_level', 'medium').upper()}\n")
    summary_parts.append(f"\n📝 **Files to Modify:** {len(proposed_changes)}\n")
    
    for file_path, new_content in proposed_changes.items():
        original_content = original_files.get(file_path, "")
        original_lines = len(original_content.split('\n')) if original_content else 0
        new_lines = len(new_content.split('\n'))
        
        summary_parts.append(f"\n**{file_path}**")
        summary_parts.append(f"  • Lines: {original_lines} → {new_lines}")
        
        # Show key changes (first 10 lines of diff)
        if original_content:
            original_lines_list = original_content.split('\n')[:5]
            new_lines_list = new_content.split('\n')[:5]
            
            summary_parts.append(f"  • Preview:")
            for i, (old_line, new_line) in enumerate(zip(original_lines_list, new_lines_list)):
                if old_line != new_line:
                    summary_parts.append(f"    - {old_line[:60]}")
                    summary_parts.append(f"    + {new_line[:60]}")
                    break
    
    summary_parts.append(f"\n\n**Plan:**")
    for step in plan.get("plan", [])[:5]:
        summary_parts.append(f"  • {step}")
    
    summary_parts.append(f"\n\n⚠️ **Review the changes carefully before approving.**")
    summary_parts.append(f"Use /approve to apply changes or /reject to cancel.")
    
    return "\n".join(summary_parts)


async def apply_improvements(state: AgentState) -> Dict[str, Any]:
    """
    Apply the approved code improvements.
    """
    proposed_changes = state.get("proposed_changes", {})
    improvement_plan = state.get("improvement_plan", {})
    
    if not proposed_changes:
        return {
            "error": "No proposed changes to apply",
            "final_response": "❌ No changes to apply"
        }
    
    applied_files = []
    errors = []

    # Tool sandboxing: only approved tools (file_write) allowed
    try:
        require_tool("file_write")
    except SecurityError as e:
        logger.error(f"Security: {e}")
        return {
            "error": str(e),
            "final_response": f"❌ Security: File write not allowed. {e}"
        }

    # Apply changes to each file
    for file_path, new_content in proposed_changes.items():
        full_path = PROJECT_ROOT / file_path
        
        try:
            # Ensure directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write new content
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            applied_files.append(file_path)
            logger.info(f"Applied changes to {file_path}")
        except Exception as e:
            error_msg = f"Failed to write {file_path}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
    
    if errors:
        return {
            "error": "; ".join(errors),
            "final_response": f"❌ Errors applying changes:\n" + "\n".join(errors)
        }
    
    # Stage and commit changes (tool sandboxing: git_add_commit must be approved)
    try:
        require_tool("git_add_commit")
    except SecurityError as e:
        logger.error(f"Security: {e}")
        return {
            "error": str(e),
            "final_response": f"❌ Security: Git operations not allowed. {e}"
        }
    try:
        # Stage files
        subprocess.run(
            ["git", "add"] + [str(PROJECT_ROOT / f) for f in applied_files],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True
        )
        
        # Commit
        commit_message = f"Improve: {improvement_plan.get('understanding', 'Code improvements')}"
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True
        )
        
        logger.info(f"Committed changes: {commit_message}")
        
        # Try to push to GitHub
        push_success = False
        push_error = None
        try:
            push_result = subprocess.run(
                ["git", "push"],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True
            )
            push_success = True
            logger.info("Pushed changes to GitHub successfully")
        except subprocess.CalledProcessError as e:
            push_error = e.stderr if e.stderr else str(e)
            logger.warning(f"Git push failed: {push_error}")
        
        if push_success:
            return {
                "final_response": (
                    f"✅ **Improvements Applied & Pushed to GitHub!**\n\n"
                    f"📝 **Modified Files:** {len(applied_files)}\n"
                    f"{chr(10).join(f'  • {f}' for f in applied_files)}\n\n"
                    f"💾 **Committed:** {commit_message}\n"
                    f"🚀 **Pushed to GitHub:** Successfully\n\n"
                    f"✨ Changes are now live on GitHub!"
                )
            }
        else:
            return {
                "final_response": (
                    f"✅ **Improvements Applied & Committed!**\n\n"
                    f"📝 **Modified Files:** {len(applied_files)}\n"
                    f"{chr(10).join(f'  • {f}' for f in applied_files)}\n\n"
                    f"💾 **Committed:** {commit_message}\n"
                    f"⚠️ **Push to GitHub failed:** {push_error[:200] if push_error else 'Unknown error'}\n\n"
                    f"💡 You can push manually with `git push` or ask me to try again."
                )
            }
    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e}")
        return {
            "error": f"Git operation failed: {str(e)}",
            "final_response": (
                f"✅ **Files Modified Successfully**\n\n"
                f"📝 **Modified:** {len(applied_files)}\n"
                f"{chr(10).join(f'  • {f}' for f in applied_files)}\n\n"
                f"⚠️ **Git commit failed.** Changes are saved but not committed.\n"
                f"Error: {str(e)[:200]}"
            )
        }


async def reject_improvements(state: AgentState) -> Dict[str, Any]:
    """Handle rejection of proposed improvements."""
    return {
        "proposed_changes": None,
        "improvement_plan": None,
        "approval_required": False,
        "final_response": "❌ **Improvements Rejected**\n\nNo changes were made to the codebase."
    }


async def push_changes_node(state: AgentState) -> Dict[str, Any]:
    """
    Push committed changes to GitHub.
    """
    try:
        result = subprocess.run(
            ["git", "push"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True
        )
        
        logger.info("Successfully pushed changes to GitHub")
        
        return {
            "final_response": (
                "🚀 **Pushed to GitHub Successfully!**\n\n"
                "✅ All committed changes have been pushed to the remote repository.\n"
                "✨ Your changes are now live on GitHub!"
            )
        }
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        logger.error(f"Git push failed: {error_msg}")
        
        # Check if there are uncommitted changes
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        
        has_uncommitted = bool(status_result.stdout.strip())
        
        if has_uncommitted:
            return {
                "error": "Uncommitted changes detected",
                "final_response": (
                    "⚠️ **Cannot Push**\n\n"
                    "There are uncommitted changes in your working directory.\n"
                    "Please commit your changes first, then try pushing again."
                )
            }
        else:
            return {
                "error": f"Push failed: {error_msg[:200]}",
                "final_response": (
                    f"❌ **Push to GitHub Failed**\n\n"
                    f"Error: {error_msg[:200]}\n\n"
                    "Possible causes:\n"
                    "• No remote repository configured\n"
                    "• Authentication issues\n"
                    "• Network connectivity problems"
                )
            }
    except Exception as e:
        logger.error(f"Unexpected error during git push: {e}")
        return {
            "error": str(e),
            "final_response": f"❌ **Error:** {str(e)[:200]}"
        }

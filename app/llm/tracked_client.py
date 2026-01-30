"""
Cost-tracked LLM client wrapper.
Wraps LLM calls with cost tracking and budget enforcement.
"""
import logging
import time
from typing import Optional, Any, Dict
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from app.cost.tracker import get_cost_tracker, track_llm_call
from app.cost.budget import get_budget_manager, BudgetExceededError
from app.cost.envelopes import get_envelope_manager
from app.circuit_breaker import check_domain_allowed
from app.retry import retry_async, is_retriable_default

logger = logging.getLogger(__name__)


class TrackedLLM:
    """
    Wrapper around BaseChatModel that tracks costs and enforces budgets.
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        model_name: str,
        provider: str,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        agent: Optional[str] = None,
    ):
        self._llm = llm
        self._model_name = model_name
        self._provider = provider
        self._domain = domain
        self._queue = queue
        self._agent = agent
    
    def _extract_tokens(self, response: Any) -> tuple[int, int]:
        """
        Extract input/output tokens from LLM response.
        LangChain responses may have usage_metadata or response_metadata.
        """
        input_tokens = 0
        output_tokens = 0
        
        # Try response_metadata (OpenAI, Anthropic)
        if hasattr(response, 'response_metadata'):
            metadata = response.response_metadata or {}
            # OpenAI format
            if 'token_usage' in metadata:
                usage = metadata['token_usage']
                input_tokens = usage.get('prompt_tokens', 0)
                output_tokens = usage.get('completion_tokens', 0)
            # Anthropic format
            elif 'usage' in metadata:
                usage = metadata['usage']
                input_tokens = usage.get('input_tokens', 0)
                output_tokens = usage.get('output_tokens', 0)
        
        # Try direct attributes (some LangChain versions)
        if hasattr(response, 'input_tokens'):
            input_tokens = response.input_tokens or 0
        if hasattr(response, 'output_tokens'):
            output_tokens = response.output_tokens or 0
        
        # Fallback: estimate from content length (rough approximation)
        if input_tokens == 0 and output_tokens == 0:
            if hasattr(response, 'content'):
                # Rough estimate: ~4 chars per token
                content_len = len(str(response.content))
                output_tokens = max(1, content_len // 4)
                # Input tokens unknown, use a conservative estimate
                input_tokens = output_tokens * 2  # Assume input is ~2x output
        
        return (input_tokens, output_tokens)
    
    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a call (before making it)."""
        from app.cost.tracker import MODEL_PRICING
        pricing = MODEL_PRICING.get(self._model_name, MODEL_PRICING["default"])
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost
    
    async def ainvoke(
        self,
        input: str | BaseMessage | list[BaseMessage],
        config: Optional[Dict] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Async invoke with cost tracking and budget enforcement.
        """
        # Check circuit breaker for domain
        if self._domain and not check_domain_allowed(self._domain):
            raise RuntimeError(f"Domain '{self._domain}' is paused (circuit breaker)")
        
        # Estimate cost before call (rough estimate based on input length)
        # This is conservative - we'll track actual cost after
        input_str = str(input) if isinstance(input, (str, list)) else str(input)
        estimated_input_tokens = len(input_str) // 4  # Rough: 4 chars per token
        estimated_output_tokens = estimated_input_tokens // 2  # Conservative estimate
        estimated_cost = self._estimate_cost(estimated_input_tokens, estimated_output_tokens)
        
        # Check budget envelopes
        envelope_mgr = get_envelope_manager()
        try:
            envelope_mgr.enforce_all_caps(
                task_id=None,  # Could extract from context if available
                agent=self._agent,
                queue=self._queue,
                tool_name=None,  # Could be "llm_call" or specific tool
                additional_cost=estimated_cost,
            )
        except BudgetExceededError as e:
            logger.warning(f"Budget envelope exceeded: {e}")
            raise
        input_str = str(input) if not isinstance(input, list) else str(input[0])
        estimated_input_tokens = len(input_str) // 4  # Rough: 4 chars per token
        estimated_output_tokens = estimated_input_tokens // 2  # Assume output is smaller
        estimated_cost = self._estimate_cost(estimated_input_tokens, estimated_output_tokens)
        
        # Check budget before call
        budget_manager = get_budget_manager()
        try:
            budget_manager.enforce_budget(
                domain=self._domain,
                queue=self._queue,
                additional_cost=estimated_cost,
            )
        except BudgetExceededError as e:
            logger.warning(f"Budget exceeded, blocking LLM call: {e}")
            # Optionally pause domain via circuit breaker
            if self._domain:
                from app.circuit_breaker import CircuitBreakerRegistry
                CircuitBreakerRegistry.pause_domain(self._domain)
                logger.warning(f"Paused domain '{self._domain}' due to budget exceeded")
            raise
        
        # Make the actual call (with retry for transient failures)
        start_time = time.time()
        success = True
        error = None

        def _retriable_llm(exc: BaseException) -> bool:
            if isinstance(exc, (BudgetExceededError, RuntimeError)):
                return False
            return is_retriable_default(exc)

        try:
            response = await retry_async(
                lambda: self._llm.ainvoke(input, config=config, **kwargs),
                max_retries=1,
                backoff_base=2.0,
                retriable=_retriable_llm,
                operation_name="llm_ainvoke",
            )
            
            # Extract actual token usage
            input_tokens, output_tokens = self._extract_tokens(response)
            duration_ms = (time.time() - start_time) * 1000
            
            # Track the call
            call = track_llm_call(
                model=self._model_name,
                provider=self._provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                domain=self._domain,
                queue=self._queue,
                agent=self._agent,
                duration_ms=duration_ms,
                success=True,
            )
            
            # Check budget again after call (in case actual cost exceeded estimate)
            actual_cost = call.cost_usd
            if actual_cost > estimated_cost * 1.5:  # If significantly more than estimate
                try:
                    budget_manager.enforce_budget(
                        domain=self._domain,
                        queue=self._queue,
                        additional_cost=0.0,  # Already recorded, just check
                    )
                except BudgetExceededError:
                    # Budget was exceeded by actual call - pause domain
                    if self._domain:
                        from app.circuit_breaker import CircuitBreakerRegistry
                        CircuitBreakerRegistry.pause_domain(self._domain)
                        logger.warning(f"Paused domain '{self._domain}' due to budget exceeded after call")
            
            return response
            
        except Exception as e:
            success = False
            error = str(e)
            duration_ms = (time.time() - start_time) * 1000
            
            # Track failed call (with estimated tokens)
            track_llm_call(
                model=self._model_name,
                provider=self._provider,
                input_tokens=estimated_input_tokens,
                output_tokens=0,
                domain=self._domain,
                queue=self._queue,
                agent=self._agent,
                duration_ms=duration_ms,
                success=False,
                error=error,
            )
            
            raise
    
    def invoke(
        self,
        input: str | BaseMessage | list[BaseMessage],
        config: Optional[Dict] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Sync invoke with cost tracking and budget enforcement.
        """
        # Check circuit breaker for domain
        if self._domain and not check_domain_allowed(self._domain):
            raise RuntimeError(f"Domain '{self._domain}' is paused (circuit breaker)")
        
        # Estimate cost
        input_str = str(input) if not isinstance(input, list) else str(input[0])
        estimated_input_tokens = len(input_str) // 4
        estimated_output_tokens = estimated_input_tokens // 2
        estimated_cost = self._estimate_cost(estimated_input_tokens, estimated_output_tokens)
        
        # Check budget
        budget_manager = get_budget_manager()
        try:
            budget_manager.enforce_budget(
                domain=self._domain,
                queue=self._queue,
                additional_cost=estimated_cost,
            )
        except BudgetExceededError as e:
            logger.warning(f"Budget exceeded, blocking LLM call: {e}")
            if self._domain:
                from app.circuit_breaker import CircuitBreakerRegistry
                CircuitBreakerRegistry.pause_domain(self._domain)
            raise
        
        # Make call
        start_time = time.time()
        try:
            response = self._llm.invoke(input, config=config, **kwargs)
            
            input_tokens, output_tokens = self._extract_tokens(response)
            duration_ms = (time.time() - start_time) * 1000
            
            track_llm_call(
                model=self._model_name,
                provider=self._provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                domain=self._domain,
                queue=self._queue,
                agent=self._agent,
                duration_ms=duration_ms,
                success=True,
            )
            
            return response
            
        except Exception as e:
            error = str(e)
            duration_ms = (time.time() - start_time) * 1000
            
            track_llm_call(
                model=self._model_name,
                provider=self._provider,
                input_tokens=estimated_input_tokens,
                output_tokens=0,
                domain=self._domain,
                queue=self._queue,
                agent=self._agent,
                duration_ms=duration_ms,
                success=False,
                error=error,
            )
            
            raise
    
    # Delegate other methods to underlying LLM
    def __getattr__(self, name: str):
        return getattr(self._llm, name)


def get_tracked_llm(
    domain: Optional[str] = None,
    queue: Optional[str] = None,
    agent: Optional[str] = None,
    llm: Optional[BaseChatModel] = None,
) -> Optional[TrackedLLM]:
    """
    Get a cost-tracked LLM instance.

    Args:
        domain: Domain name for cost tracking (e.g., "Algebra")
        queue: Queue name for cost tracking (e.g., "source_gathering")
        agent: Agent name for cost tracking (e.g., "source_gatherer")
        llm: Optional pre-built LLM (e.g. manager LLM); if None, uses get_llm() (agents path)

    Returns:
        TrackedLLM wrapper or None if no LLM available
    """
    from app.llm.client import get_llm as _get_llm

    if llm is None:
        llm = _get_llm()
    if not llm:
        return None
    
    # Determine model name and provider
    model_name = "default"
    provider = "unknown"
    
    # Check OpenAI
    if hasattr(llm, 'model_name'):
        model_name = llm.model_name
        provider = "openai"
    elif hasattr(llm, 'model'):
        model_name = llm.model
        # Try to detect provider from model name
        if "gpt" in model_name.lower():
            provider = "openai"
        elif "claude" in model_name.lower():
            provider = "anthropic"
    
    # Check Anthropic
    if hasattr(llm, 'model') and "claude" in str(llm.model).lower():
        provider = "anthropic"
        if hasattr(llm, 'model'):
            model_name = str(llm.model)
    
    # Moonshot/Kimi (OpenAI-compatible with base_url)
    if provider == "unknown" and hasattr(llm, "model"):
        m = str(llm.model).lower()
        if "moonshot" in m or "kimi" in m:
            provider = "moonshot"
            model_name = str(llm.model)
    if getattr(llm, "base_url", None) and "moonshot" in str(llm.base_url).lower():
        provider = "moonshot"
        if hasattr(llm, "model"):
            model_name = str(llm.model)

    # Fallback: check env vars
    import os
    if os.getenv("OPENAI_API_KEY") and provider == "unknown":
        provider = "openai"
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    elif os.getenv("ANTHROPIC_API_KEY") and provider == "unknown":
        provider = "anthropic"
        model_name = "claude-3-haiku-20240307"
    elif (os.getenv("MOONSHOT_API_KEY") or os.getenv("KIMI_API_KEY")) and provider == "unknown":
        provider = "moonshot"
        model_name = os.getenv("MOONSHOT_MODEL", "moonshot-v1-8k")
    
    return TrackedLLM(
        llm=llm,
        model_name=model_name,
        provider=provider,
        domain=domain,
        queue=queue,
        agent=agent,
    )

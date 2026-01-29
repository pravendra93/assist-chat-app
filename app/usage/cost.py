def estimate_cost(tokens: int, cost_per_1k: float) -> float:
    return (tokens / 1000) * cost_per_1k


async def log_llm_usage(
    db,
    tenant_id,
    conversation_id,
    message_id,
    model,
    prompt_tokens,
    completion_tokens,
    cost_usd,
    latency_ms,
):
    query = """
    INSERT INTO llm_usage (
      tenant_id,
      conversation_id,
      message_id,
      model,
      prompt_tokens,
      completion_tokens,
      total_tokens,
      cost_usd,
      latency_ms
    )
    VALUES (
      :tenant_id,
      :conversation_id,
      :message_id,
      :model,
      :prompt_tokens,
      :completion_tokens,
      :total_tokens,
      :cost_usd,
      :latency_ms
    )
    """

    await db.execute(text(query), {
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
    })

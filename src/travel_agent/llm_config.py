"""Shared Ollama request settings and a separate coarse input byte guard."""

import os


def _integer(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, default))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be {minimum}..{maximum}")
    return value


def generation_options():
    return {"num_ctx": _integer("AGENT_CONTEXT_TOKENS", 65536, 1024, 1048576),
            "num_predict": _integer("AGENT_MAX_OUTPUT_TOKENS", 4096, 128, 8192), "temperature": 0}


def input_byte_limit():
    # This is a byte guard, not a tokenizer or a guarantee of fitting num_ctx.
    return _integer("AGENT_MAX_INPUT_BYTES", 196608, 1000, 1048576)

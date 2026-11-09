"""Claude-backed narrator.

narrate(event, ctx) never blocks the game: it returns a pre-generated Claude line
if one is cached, otherwise an instant prewritten fallback line. A background
thread pre-generates the lines that are about to be needed (both morning
outcomes during the night, each possible vote result during the day), so by the
time Botfia speaks, the good line is already waiting.

If there is no API key, the SDK is missing, or the internet is down, everything
still works — the game just uses the fallback bank.
"""

import re
import threading

from . import fallback
from . import prompts

_QUOTES = "\"'“”‘’"


def _clean(text):
    """Strip anything the TTS would read aloud wrong: wrapping quotes, markdown
    emphasis/headings (* _ ` #), and stray newlines. Returns plain spoken prose."""
    t = (text or "").strip()
    while len(t) >= 2 and t[0] in _QUOTES and t[-1] in _QUOTES:
        t = t[1:-1].strip()
    t = re.sub(r"[*_`#]+", "", t)          # markdown characters
    t = re.sub(r"\s+", " ", t).strip()     # collapse newlines/whitespace
    return t


def _key(event, ctx):
    items = sorted((ctx or {}).items())
    return event + "|" + "|".join(f"{k}={v}" for k, v in items)


class Narrator:
    def __init__(self, model="claude-sonnet-4-6", max_tokens=120, timeout=8.0):
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._cache = {}
        self._lock = threading.Lock()
        self._client = None
        self.enabled = False
        try:
            import anthropic
            self._client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY
            # Only mark enabled if a key is actually present.
            import os
            self.enabled = bool(os.getenv("ANTHROPIC_API_KEY"))
        except Exception:
            self.enabled = False

    # ---- the engine calls this; it must be fast and never raise ----
    def narrate(self, event, ctx=None):
        ctx = ctx or {}
        try:
            prompts.assert_public(event, ctx)   # refuse to touch secrets
        except ValueError:
            return fallback.line(event, ctx)
        with self._lock:
            cached = self._cache.get(_key(event, ctx))
        if cached:
            return cached
        # Not pre-generated — speak instantly from the fallback bank, and ask
        # Claude to prepare an upgraded line for next time in the background.
        if self.enabled:
            self._spawn(event, ctx)
        return fallback.line(event, ctx)

    # ---- pre-generation (called ahead of time by the app) ----
    def pregenerate(self, event, ctx=None):
        if not self.enabled:
            return
        ctx = ctx or {}
        try:
            prompts.assert_public(event, ctx)
        except ValueError:
            return
        with self._lock:
            if _key(event, ctx) in self._cache:
                return
        self._spawn(event, ctx)

    def _spawn(self, event, ctx):
        t = threading.Thread(target=self._generate, args=(event, dict(ctx)), daemon=True)
        t.start()

    def _generate(self, event, ctx):
        try:
            system, user = prompts.build(event, ctx)
            client = self._client.with_options(timeout=self.timeout)
            resp = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = _clean("".join(b.text for b in resp.content if b.type == "text"))
            if text:
                with self._lock:
                    self._cache[_key(event, ctx)] = text
        except Exception:
            # Leave it uncached; narrate() already returned a fallback line.
            pass

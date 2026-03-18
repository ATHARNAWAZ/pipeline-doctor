"""
Shared in-memory state for the pipeline-doctor API.

Both the analyze and query routers need access to the same analysis store.
Using a module-level dict (mutable object) ensures all importers reference
the same container — Python's import system guarantees a module is only
loaded once per interpreter, so this is safe.

When this scales beyond a single process (multiple workers, multi-user):
  - Replace `analysis_store` with a Redis-backed store
  - Replace `lineage_store` with a Redis-backed store or rebuild on demand
  - `latest_analysis_id` becomes a Redis key scoped by session/user

The wrapper class pattern (rather than bare module-level variables) prevents
the `from app.state import latest_analysis_id` anti-pattern where importers
get a copy of the primitive and lose sync when it's reassigned.
"""

from __future__ import annotations

from typing import Optional

from app.services.lineage_graph import LineageGraph
from app.services.manifest_parser import ParsedManifest


class _State:
    """Container for mutable shared state.

    Using a class instance rather than bare module globals avoids the
    Python primitive re-binding trap:

        # BAD — importer gets a copy of None, never sees updates
        from app.state import latest_analysis_id

        # GOOD — importer holds a reference to the container object
        from app.state import state
        state.latest_analysis_id = "abc123"  # visible everywhere
    """

    def __init__(self) -> None:
        # Keyed by analysis_id (UUID string) → supports multiple concurrent sessions
        self.analysis_store: dict[str, ParsedManifest] = {}
        self.lineage_store: dict[str, LineageGraph] = {}
        # Most recently completed analysis — used as fallback when callers
        # don't provide an explicit analysis_id
        self.latest_analysis_id: Optional[str] = None


# Single shared instance — import this everywhere
state = _State()

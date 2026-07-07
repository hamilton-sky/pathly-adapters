"""Re-export shim — comms queries are split across domain modules.

Import from the domain module directly for new code:
  db.queries.comms_messages   — board message CRUD
  db.queries.comms_artifacts  — artifact metadata
  db.queries.comms_tasks      — task DAG operations
  db.queries.comms_embeddings — embedding storage and search
"""

from .comms_messages import (  # noqa: F401
    _now,
    post_message,
    set_goal_executor,
    set_message_slug,
    read_message_slug,
    get_messages,
    get_pending_decisions,
    get_active_escalations,
    supersede_message,
    acknowledge_message,
    answer_question,
    get_trash,
    restore_messages,
    purge_expired_trash,
    soft_delete_message,
    update_message_text,
)
from .comms_counts import (  # noqa: F401
    count_goals_for_feature,
    count_features_for_project,
)
from .comms_artifacts import (  # noqa: F401
    attach_artifact_to_message,
    insert_artifact,
    list_artifacts_for_message,
    reindex_artifact_sections,
    update_artifact_indexed_mtime,
    get_artifact_sections,
    get_section,
    find_or_create_artifact_by_path,
    list_artifacts_catalog,
    update_artifact_summary,
    ensure_attached,
)
from .comms_tasks import (  # noqa: F401
    get_ready_tasks,
    get_tasks,
    complete_task,
    claim_task,
    fail_task,
    reclaim_stale_claims,
    count_tasks_for_goal,
    goal_refs_coverage,
)
from .comms_embeddings import (  # noqa: F401
    _RRF_K,
    _DEDUP_PROTECTED_TYPES,
    _dist_of,
    search_by_embedding,
    search_by_keyword,
    search_by_hybrid,
    store_embedding,
    store_chunk_embeddings,
    dedupe_board,
)

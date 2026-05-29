"""CareerLoop REST API — thin FastAPI product layer.

router → service → repository → Supabase (careerloop.*)

This package wraps the existing CareerLoop runtime (SessionStore, repository_v2,
supervisor_graph) behind a stable HTTP contract for the web frontend.

NOTE: The live Supabase schema is the v1 schema (daily_briefs.id, NOT brief_id;
daily_brief_items.recommendation_reason, NOT reason). repository_v2.py targets the
v2 column names and is mid-migration, so this API's repository layer issues SQL
directly against the LIVE schema for correctness. See docs/engineering/API_ARCHITECTURE.md.
"""

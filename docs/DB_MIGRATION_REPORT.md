# CareerLoop Database Migration Report

**Audit Date:** 2026-05-25
**Database:** Supabase (postgresql://aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres)

---

## 1. Schemas Present

- `auth`
- `backup_public_schema`
- `careerloop`
- `emote_app`
- `extensions`
- `graphql`
- `graphql_public`
- `information_schema`
- `net`
- `pg_catalog`
- `pg_temp_0`
- `pg_temp_1`
- `pg_temp_10`
- `pg_temp_11`
- `pg_temp_12`
- `pg_temp_13`
- `pg_temp_14`
- `pg_temp_15`
- `pg_temp_16`
- `pg_temp_17`
- `pg_temp_18`
- `pg_temp_19`
- `pg_temp_2`
- `pg_temp_20`
- `pg_temp_21`
- `pg_temp_22`
- `pg_temp_23`
- `pg_temp_24`
- `pg_temp_25`
- `pg_temp_26`
- `pg_temp_27`
- `pg_temp_28`
- `pg_temp_29`
- `pg_temp_3`
- `pg_temp_30`
- `pg_temp_31`
- `pg_temp_32`
- `pg_temp_33`
- `pg_temp_34`
- `pg_temp_35`
- `pg_temp_36`
- `pg_temp_37`
- `pg_temp_38`
- `pg_temp_39`
- `pg_temp_4`
- `pg_temp_40`
- `pg_temp_41`
- `pg_temp_42`
- `pg_temp_43`
- `pg_temp_44`
- `pg_temp_45`
- `pg_temp_46`
- `pg_temp_47`
- `pg_temp_48`
- `pg_temp_49`
- `pg_temp_5`
- `pg_temp_50`
- `pg_temp_51`
- `pg_temp_52`
- `pg_temp_53`
- `pg_temp_54`
- `pg_temp_55`
- `pg_temp_56`
- `pg_temp_57`
- `pg_temp_58`
- `pg_temp_59`
- `pg_temp_6`
- `pg_temp_7`
- `pg_temp_8`
- `pg_temp_9`
- `pg_toast`
- `pg_toast_temp_0`
- `pg_toast_temp_1`
- `pg_toast_temp_10`
- `pg_toast_temp_11`
- `pg_toast_temp_12`
- `pg_toast_temp_13`
- `pg_toast_temp_14`
- `pg_toast_temp_15`
- `pg_toast_temp_16`
- `pg_toast_temp_17`
- `pg_toast_temp_18`
- `pg_toast_temp_19`
- `pg_toast_temp_2`
- `pg_toast_temp_20`
- `pg_toast_temp_21`
- `pg_toast_temp_22`
- `pg_toast_temp_23`
- `pg_toast_temp_24`
- `pg_toast_temp_25`
- `pg_toast_temp_26`
- `pg_toast_temp_27`
- `pg_toast_temp_28`
- `pg_toast_temp_29`
- `pg_toast_temp_3`
- `pg_toast_temp_30`
- `pg_toast_temp_31`
- `pg_toast_temp_32`
- `pg_toast_temp_33`
- `pg_toast_temp_34`
- `pg_toast_temp_35`
- `pg_toast_temp_36`
- `pg_toast_temp_37`
- `pg_toast_temp_38`
- `pg_toast_temp_39`
- `pg_toast_temp_4`
- `pg_toast_temp_40`
- `pg_toast_temp_41`
- `pg_toast_temp_42`
- `pg_toast_temp_43`
- `pg_toast_temp_44`
- `pg_toast_temp_45`
- `pg_toast_temp_46`
- `pg_toast_temp_47`
- `pg_toast_temp_48`
- `pg_toast_temp_49`
- `pg_toast_temp_5`
- `pg_toast_temp_50`
- `pg_toast_temp_51`
- `pg_toast_temp_52`
- `pg_toast_temp_53`
- `pg_toast_temp_54`
- `pg_toast_temp_55`
- `pg_toast_temp_56`
- `pg_toast_temp_57`
- `pg_toast_temp_58`
- `pg_toast_temp_59`
- `pg_toast_temp_6`
- `pg_toast_temp_7`
- `pg_toast_temp_8`
- `pg_toast_temp_9`
- `pgbouncer`
- `public`
- `realtime`
- `storage`
- `supabase_functions`
- `vault`

## 2. Table Inventory with Row Counts

### auth

| Table | Row Count |
|-------|-----------|
| `audit_log_entries` | 0 |
| `custom_oauth_providers` | 0 |
| `flow_state` | 0 |
| `identities` | 0 |
| `instances` | 0 |
| `mfa_amr_claims` | 0 |
| `mfa_challenges` | 0 |
| `mfa_factors` | 0 |
| `oauth_authorizations` | 0 |
| `oauth_client_states` | 0 |
| `oauth_clients` | 0 |
| `oauth_consents` | 0 |
| `one_time_tokens` | 0 |
| `refresh_tokens` | 0 |
| `saml_providers` | 0 |
| `saml_relay_states` | 0 |
| `schema_migrations` | 76 |
| `sessions` | 0 |
| `sso_domains` | 0 |
| `sso_providers` | 0 |
| `users` | 0 |
| `webauthn_challenges` | 0 |
| `webauthn_credentials` | 0 |

### backup_public_schema

| Table | Row Count |
|-------|-----------|
| `conversation_logs` | 0 |
| `conversations` | 16 |
| `messages` | 73 |
| `session_devices` | 0 |
| `sessions` | 22 |
| `users` | 12 |

### careerloop

| Table | Row Count |
|-------|-----------|
| `application_ledger` | 0 |
| `application_packs` | 0 |
| `applications` | 0 |
| `background_runs` | 3 |
| `companies` | 0 |
| `company_memory` | 0 |
| `daily_brief_items` | 1 |
| `daily_briefs` | 1 |
| `event_timeline` | 0 |
| `followups` | 0 |
| `job_candidates` | 0 |
| `jobs` | 1 |
| `outcome_events` | 0 |
| `outreach_messages` | 0 |
| `people_to_reach` | 0 |
| `positioning_memory` | 0 |
| `run_events` | 7 |
| `sessions` | 13 |
| `strategic_tracks` | 0 |
| `user_evidence` | 0 |
| `user_job_relationships` | 2 |
| `user_preferences` | 0 |

### emote_app

| Table | Row Count |
|-------|-----------|
| `banner_lines` | 7 |
| `blog_images` | 0 |
| `blog_posts` | 6 |
| `checkpoint_blobs` | 243 |
| `checkpoint_migrations` | 10 |
| `checkpoint_writes` | 467 |
| `checkpoints` | 158 |
| `conversation_logs_json` | 10289 |
| `conversations` | 1816 |
| `cookie_consents` | 0 |
| `crack_incidents` | 30 |
| `crisis_resources` | 38 |
| `crisis_state` | 49 |
| `dynamic_conversation_starters` | 346 |
| `email_nudges` | 0 |
| `entity_canonical` | 0 |
| `feedback_logs` | 104 |
| `guest_conversations` | 10 |
| `guest_messages` | 78 |
| `guest_users` | 13 |
| `json_cache` | 6376 |
| `messages` | 6396 |
| `ops_health_checks` | 132 |
| `pattern_corrections` | 0 |
| `pattern_feedback` | 0 |
| `pipeline_checkpoints` | 29 |
| `prompt_leak_incidents` | 2096 |
| `refresh_tokens` | 952 |
| `registry_decision_log` | 2 |
| `semantic_embeddings` | 0 |
| `session_devices` | 0 |
| `session_intelligence_snapshots` | 776 |
| `session_metrics` | 10 |
| `session_scores` | 516 |
| `session_store` | 1 |
| `session_summaries` | 710 |
| `sessions` | 5679 |
| `things_to_remember` | 2168 |
| `turn_scores` | 4145 |
| `user_context_submissions` | 129 |
| `user_emotional_profiles` | 115 |
| `user_kg_turns` | 633 |
| `user_knowledge_graph` | 72 |
| `users` | 514 |

### extensions

| Table | Row Count |
|-------|-----------|

### graphql

| Table | Row Count |
|-------|-----------|

### graphql_public

| Table | Row Count |
|-------|-----------|

### information_schema

| Table | Row Count |
|-------|-----------|
| `sql_features` | 755 |
| `sql_implementation_info` | 12 |
| `sql_parts` | 11 |
| `sql_sizing` | 23 |

### net

| Table | Row Count |
|-------|-----------|
| `_http_response` | 1 |
| `http_request_queue` | 0 |

### pg_catalog

| Table | Row Count |
|-------|-----------|
| `pg_aggregate` | 157 |
| `pg_am` | 7 |
| `pg_amop` | 945 |
| `pg_amproc` | 696 |
| `pg_attrdef` | 442 |
| `pg_attribute` | 6934 |
| `pg_auth_members` | 23 |
| `pg_authid` | 31 |
| `pg_cast` | 229 |
| `pg_class` | 1117 |
| `pg_collation` | 814 |
| `pg_constraint` | 377 |
| `pg_conversion` | 128 |
| `pg_database` | 3 |
| `pg_db_role_setting` | 10 |
| `pg_default_acl` | 27 |
| `pg_depend` | 4568 |
| `pg_description` | 5338 |
| `pg_enum` | 43 |
| `pg_event_trigger` | 6 |
| `pg_extension` | 6 |
| `pg_foreign_data_wrapper` | 0 |
| `pg_foreign_server` | 0 |
| `pg_foreign_table` | 0 |
| `pg_index` | 608 |
| `pg_inherits` | 0 |
| `pg_init_privs` | 237 |
| `pg_language` | 4 |
| `pg_largeobject` | 0 |
| `pg_largeobject_metadata` | 0 |
| `pg_namespace` | 137 |
| `pg_opclass` | 177 |
| `pg_operator` | 799 |
| `pg_opfamily` | 146 |
| `pg_parameter_acl` | 0 |
| `pg_partitioned_table` | 1 |
| `pg_policy` | 22 |
| `pg_proc` | 3446 |
| `pg_publication` | 1 |
| `pg_publication_namespace` | 0 |
| `pg_publication_rel` | 0 |
| `pg_range` | 6 |
| `pg_replication_origin` | 0 |
| `pg_rewrite` | 156 |
| `pg_seclabel` | 0 |
| `pg_sequence` | 15 |
| `pg_shdepend` | 764 |
| `pg_shdescription` | 3 |
| `pg_shseclabel` | 0 |
| `pg_statistic` | 813 |
| `pg_statistic_ext` | 0 |
| `pg_statistic_ext_data` | 0 |
| `pg_subscription` | 0 |
| `pg_subscription_rel` | 0 |
| `pg_tablespace` | 2 |
| `pg_transform` | 0 |
| `pg_trigger` | 242 |
| `pg_ts_config` | 29 |
| `pg_ts_config_map` | 551 |
| `pg_ts_dict` | 29 |
| `pg_ts_parser` | 1 |
| `pg_ts_template` | 5 |
| `pg_type` | 913 |
| `pg_user_mapping` | 0 |

### pg_temp_0

| Table | Row Count |
|-------|-----------|

### pg_temp_1

| Table | Row Count |
|-------|-----------|

### pg_temp_10

| Table | Row Count |
|-------|-----------|

### pg_temp_11

| Table | Row Count |
|-------|-----------|

### pg_temp_12

| Table | Row Count |
|-------|-----------|

### pg_temp_13

| Table | Row Count |
|-------|-----------|

### pg_temp_14

| Table | Row Count |
|-------|-----------|

### pg_temp_15

| Table | Row Count |
|-------|-----------|

### pg_temp_16

| Table | Row Count |
|-------|-----------|

### pg_temp_17

| Table | Row Count |
|-------|-----------|

### pg_temp_18

| Table | Row Count |
|-------|-----------|

### pg_temp_19

| Table | Row Count |
|-------|-----------|

### pg_temp_2

| Table | Row Count |
|-------|-----------|

### pg_temp_20

| Table | Row Count |
|-------|-----------|

### pg_temp_21

| Table | Row Count |
|-------|-----------|

### pg_temp_22

| Table | Row Count |
|-------|-----------|

### pg_temp_23

| Table | Row Count |
|-------|-----------|

### pg_temp_24

| Table | Row Count |
|-------|-----------|

### pg_temp_25

| Table | Row Count |
|-------|-----------|

### pg_temp_26

| Table | Row Count |
|-------|-----------|

### pg_temp_27

| Table | Row Count |
|-------|-----------|

### pg_temp_28

| Table | Row Count |
|-------|-----------|

### pg_temp_29

| Table | Row Count |
|-------|-----------|

### pg_temp_3

| Table | Row Count |
|-------|-----------|

### pg_temp_30

| Table | Row Count |
|-------|-----------|

### pg_temp_31

| Table | Row Count |
|-------|-----------|

### pg_temp_32

| Table | Row Count |
|-------|-----------|

### pg_temp_33

| Table | Row Count |
|-------|-----------|

### pg_temp_34

| Table | Row Count |
|-------|-----------|

### pg_temp_35

| Table | Row Count |
|-------|-----------|

### pg_temp_36

| Table | Row Count |
|-------|-----------|

### pg_temp_37

| Table | Row Count |
|-------|-----------|

### pg_temp_38

| Table | Row Count |
|-------|-----------|

### pg_temp_39

| Table | Row Count |
|-------|-----------|

### pg_temp_4

| Table | Row Count |
|-------|-----------|

### pg_temp_40

| Table | Row Count |
|-------|-----------|

### pg_temp_41

| Table | Row Count |
|-------|-----------|

### pg_temp_42

| Table | Row Count |
|-------|-----------|

### pg_temp_43

| Table | Row Count |
|-------|-----------|

### pg_temp_44

| Table | Row Count |
|-------|-----------|

### pg_temp_45

| Table | Row Count |
|-------|-----------|

### pg_temp_46

| Table | Row Count |
|-------|-----------|

### pg_temp_47

| Table | Row Count |
|-------|-----------|

### pg_temp_48

| Table | Row Count |
|-------|-----------|

### pg_temp_49

| Table | Row Count |
|-------|-----------|

### pg_temp_5

| Table | Row Count |
|-------|-----------|

### pg_temp_50

| Table | Row Count |
|-------|-----------|

### pg_temp_51

| Table | Row Count |
|-------|-----------|

### pg_temp_52

| Table | Row Count |
|-------|-----------|

### pg_temp_53

| Table | Row Count |
|-------|-----------|

### pg_temp_54

| Table | Row Count |
|-------|-----------|

### pg_temp_55

| Table | Row Count |
|-------|-----------|

### pg_temp_56

| Table | Row Count |
|-------|-----------|

### pg_temp_57

| Table | Row Count |
|-------|-----------|

### pg_temp_58

| Table | Row Count |
|-------|-----------|

### pg_temp_59

| Table | Row Count |
|-------|-----------|

### pg_temp_6

| Table | Row Count |
|-------|-----------|

### pg_temp_7

| Table | Row Count |
|-------|-----------|

### pg_temp_8

| Table | Row Count |
|-------|-----------|

### pg_temp_9

| Table | Row Count |
|-------|-----------|

### pg_toast

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_0

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_1

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_10

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_11

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_12

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_13

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_14

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_15

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_16

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_17

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_18

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_19

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_2

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_20

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_21

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_22

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_23

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_24

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_25

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_26

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_27

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_28

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_29

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_3

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_30

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_31

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_32

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_33

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_34

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_35

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_36

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_37

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_38

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_39

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_4

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_40

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_41

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_42

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_43

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_44

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_45

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_46

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_47

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_48

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_49

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_5

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_50

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_51

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_52

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_53

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_54

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_55

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_56

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_57

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_58

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_59

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_6

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_7

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_8

| Table | Row Count |
|-------|-----------|

### pg_toast_temp_9

| Table | Row Count |
|-------|-----------|

### pgbouncer

| Table | Row Count |
|-------|-----------|

### public

| Table | Row Count |
|-------|-----------|
| `checkpoint_blobs` | 117 |
| `checkpoint_migrations` | 10 |
| `checkpoint_writes` | 229 |
| `checkpoints` | 73 |
| `conversation_logs_json` | 0 |
| `semantic_embeddings` | 2 |
| `users` | 14 |

### realtime

| Table | Row Count |
|-------|-----------|
| `messages` | 0 |
| `schema_migrations` | 69 |
| `subscription` | 0 |

### storage

| Table | Row Count |
|-------|-----------|
| `buckets` | 1 |
| `buckets_analytics` | 0 |
| `buckets_vectors` | 0 |
| `migrations` | 61 |
| `objects` | 3 |
| `s3_multipart_uploads` | 0 |
| `s3_multipart_uploads_parts` | 0 |
| `vector_indexes` | 0 |

### supabase_functions

| Table | Row Count |
|-------|-----------|
| `hooks` | 491 |
| `migrations` | 2 |

### vault

| Table | Row Count |
|-------|-----------|
| `secrets` | 0 |

## 3. Foreign Key Inventory

Total FKs across all schemas: **19**

| Schema | Table | Column | References | Constraint |
|--------|-------|--------|------------|------------|
| `careerloop` | `application_ledger` | `track_id` | `careerloop.strategic_tracks(id)` | `application_ledger_track_id_fkey` |
| `careerloop` | `daily_brief_items` | `brief_id` | `careerloop.daily_briefs(id)` | `daily_brief_items_brief_id_fkey` |
| `careerloop` | `jobs` | `company_id` | `careerloop.companies(id)` | `jobs_company_id_fkey` |
| `careerloop` | `positioning_memory` | `track_id` | `careerloop.strategic_tracks(id)` | `positioning_memory_track_id_fkey` |
| `careerloop` | `run_events` | `run_id` | `careerloop.background_runs(run_id)` | `run_events_run_id_fkey` |
| `emote_app` | `blog_images` | `blog_post_id` | `emote_app.blog_posts(id)` | `blog_images_blog_post_id_fkey` |
| `emote_app` | `conversations` | `google_id` | `emote_app.users(google_id)` | `conversations_google_id_fkey` |
| `emote_app` | `cookie_consents` | `google_id` | `emote_app.users(google_id)` | `cookie_consents_google_id_fkey` |
| `emote_app` | `feedback_logs` | `session_id` | `emote_app.conversations(session_id)` | `feedback_logs_session_id_fkey` |
| `emote_app` | `feedback_logs` | `user_id` | `emote_app.users(google_id)` | `feedback_logs_user_id_fkey` |
| `emote_app` | `guest_conversations` | `guest_id` | `emote_app.guest_users(guest_id)` | `guest_conversations_guest_id_fkey` |
| `emote_app` | `guest_messages` | `guest_id` | `emote_app.guest_users(guest_id)` | `guest_messages_guest_id_fkey` |
| `emote_app` | `messages` | `session_id` | `emote_app.conversations(session_id)` | `messages_session_id_fkey` |
| `emote_app` | `pattern_corrections` | `google_id` | `emote_app.users(google_id)` | `pattern_corrections_google_id_fkey` |
| `emote_app` | `pattern_feedback` | `google_id` | `emote_app.users(google_id)` | `pattern_feedback_google_id_fkey` |
| `emote_app` | `session_devices` | `session_id` | `emote_app.conversations(session_id)` | `session_devices_session_id_fkey` |
| `emote_app` | `session_intelligence_snapshots` | `google_id` | `emote_app.users(google_id)` | `fk_google_id` |
| `emote_app` | `things_to_remember` | `google_id` | `emote_app.users(google_id)` | `things_to_remember_google_id_fkey` |
| `emote_app` | `user_emotional_profiles` | `google_id` | `emote_app.users(google_id)` | `user_emotional_profiles_google_id_fkey` |

### CareerLoop Schema FKs: 5

- `application_ledger.track_id` -> `careerloop.strategic_tracks(id)`
- `daily_brief_items.brief_id` -> `careerloop.daily_briefs(id)`
- `jobs.company_id` -> `careerloop.companies(id)`
- `positioning_memory.track_id` -> `careerloop.strategic_tracks(id)`
- `run_events.run_id` -> `careerloop.background_runs(run_id)`

## 4. ID Type Audit

### All ID columns in careerloop + public schemas

| Schema | Table | Column | Data Type | UDT |
|--------|-------|--------|-----------|-----|
| `careerloop` | `application_ledger` | `id` | `uuid` | `uuid` |
| `careerloop` | `application_ledger` | `track_id` | `uuid` | `uuid` |
| `careerloop` | `application_ledger` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `application_packs` | `company_intel_id` | `text` | `text` |
| `careerloop` | `application_packs` | `job_id` | `text` | `text` |
| `careerloop` | `application_packs` | `pack_id` | `uuid` | `uuid` |
| `careerloop` | `application_packs` | `resume_artifact_id` | `text` | `text` |
| `careerloop` | `application_packs` | `run_id` | `uuid` | `uuid` |
| `careerloop` | `application_packs` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `applications` | `application_id` | `uuid` | `uuid` |
| `careerloop` | `applications` | `application_pack_id` | `uuid` | `uuid` |
| `careerloop` | `applications` | `job_id` | `text` | `text` |
| `careerloop` | `applications` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `background_runs` | `run_id` | `text` | `text` |
| `careerloop` | `background_runs` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `companies` | `id` | `uuid` | `uuid` |
| `careerloop` | `company_memory` | `id` | `uuid` | `uuid` |
| `careerloop` | `company_memory` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `daily_brief_items` | `brief_id` | `uuid` | `uuid` |
| `careerloop` | `daily_brief_items` | `id` | `uuid` | `uuid` |
| `careerloop` | `daily_brief_items` | `job_id` | `text` | `text` |
| `careerloop` | `daily_briefs` | `id` | `uuid` | `uuid` |
| `careerloop` | `daily_briefs` | `run_id` | `text` | `text` |
| `careerloop` | `daily_briefs` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `event_timeline` | `id` | `uuid` | `uuid` |
| `careerloop` | `event_timeline` | `reference_id` | `text` | `text` |
| `careerloop` | `event_timeline` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `followups` | `application_id` | `uuid` | `uuid` |
| `careerloop` | `followups` | `followup_id` | `uuid` | `uuid` |
| `careerloop` | `followups` | `person_id` | `uuid` | `uuid` |
| `careerloop` | `followups` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `job_candidates` | `candidate_id` | `uuid` | `uuid` |
| `careerloop` | `job_candidates` | `matched_job_id` | `text` | `text` |
| `careerloop` | `job_candidates` | `run_id` | `uuid` | `uuid` |
| `careerloop` | `jobs` | `canonical_id` | `text` | `text` |
| `careerloop` | `jobs` | `company_id` | `uuid` | `uuid` |
| `careerloop` | `jobs` | `id` | `text` | `text` |
| `careerloop` | `jobs` | `job_id` | `uuid` | `uuid` |
| `careerloop` | `outcome_events` | `application_id` | `uuid` | `uuid` |
| `careerloop` | `outcome_events` | `job_id` | `text` | `text` |
| `careerloop` | `outcome_events` | `outcome_id` | `uuid` | `uuid` |
| `careerloop` | `outcome_events` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `outreach_messages` | `application_id` | `uuid` | `uuid` |
| `careerloop` | `outreach_messages` | `job_id` | `text` | `text` |
| `careerloop` | `outreach_messages` | `message_id` | `uuid` | `uuid` |
| `careerloop` | `outreach_messages` | `person_id` | `uuid` | `uuid` |
| `careerloop` | `outreach_messages` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `people_to_reach` | `company_id` | `uuid` | `uuid` |
| `careerloop` | `people_to_reach` | `job_id` | `text` | `text` |
| `careerloop` | `people_to_reach` | `person_id` | `uuid` | `uuid` |
| `careerloop` | `positioning_memory` | `id` | `uuid` | `uuid` |
| `careerloop` | `positioning_memory` | `track_id` | `uuid` | `uuid` |
| `careerloop` | `positioning_memory` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `run_events` | `event_id` | `text` | `text` |
| `careerloop` | `run_events` | `run_id` | `text` | `text` |
| `careerloop` | `sessions` | `active_artifact_id` | `text` | `text` |
| `careerloop` | `sessions` | `active_brief_id` | `text` | `text` |
| `careerloop` | `sessions` | `active_job_id` | `text` | `text` |
| `careerloop` | `sessions` | `active_pack_id` | `text` | `text` |
| `careerloop` | `sessions` | `current_job_id` | `text` | `text` |
| `careerloop` | `sessions` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `strategic_tracks` | `id` | `uuid` | `uuid` |
| `careerloop` | `strategic_tracks` | `resume_variant_id` | `text` | `text` |
| `careerloop` | `strategic_tracks` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `user_evidence` | `evidence_id` | `uuid` | `uuid` |
| `careerloop` | `user_evidence` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `user_job_relationships` | `job_id` | `text` | `text` |
| `careerloop` | `user_job_relationships` | `shown_in_brief_id` | `uuid` | `uuid` |
| `careerloop` | `user_job_relationships` | `user_id` | `uuid` | `uuid` |
| `careerloop` | `user_preferences` | `user_id` | `uuid` | `uuid` |
| `public` | `checkpoint_blobs` | `thread_id` | `text` | `text` |
| `public` | `checkpoint_writes` | `checkpoint_id` | `text` | `text` |
| `public` | `checkpoint_writes` | `task_id` | `text` | `text` |
| `public` | `checkpoint_writes` | `thread_id` | `text` | `text` |
| `public` | `checkpoints` | `checkpoint_id` | `text` | `text` |
| `public` | `checkpoints` | `parent_checkpoint_id` | `text` | `text` |
| `public` | `checkpoints` | `thread_id` | `text` | `text` |
| `public` | `conversation_logs_json` | `google_id` | `character varying` | `varchar` |
| `public` | `conversation_logs_json` | `id` | `uuid` | `uuid` |
| `public` | `conversation_logs_json` | `session_id` | `uuid` | `uuid` |
| `public` | `emote_conversations` | `google_id` | `character varying` | `varchar` |
| `public` | `emote_conversations` | `id` | `uuid` | `uuid` |
| `public` | `emote_conversations` | `session_id` | `uuid` | `uuid` |
| `public` | `emote_starters` | `id` | `integer` | `int4` |
| `public` | `emote_starters` | `session_id` | `text` | `text` |
| `public` | `emote_starters` | `user_id` | `text` | `text` |
| `public` | `emote_users` | `google_id` | `character varying` | `varchar` |
| `public` | `semantic_embeddings` | `id` | `uuid` | `uuid` |
| `public` | `semantic_embeddings` | `session_id` | `uuid` | `uuid` |
| `public` | `semantic_embeddings` | `user_id` | `character varying` | `varchar` |
| `public` | `user_embedding_stats` | `user_id` | `character varying` | `varchar` |
| `public` | `users` | `id` | `uuid` | `uuid` |

### TEXT IDs in careerloop needing UUID migration: 23

| Schema | Table | Column | Data Type |
|--------|-------|--------|-----------|
| `careerloop` | `application_packs` | `company_intel_id` | `text` |
| `careerloop` | `application_packs` | `job_id` | `text` |
| `careerloop` | `application_packs` | `resume_artifact_id` | `text` |
| `careerloop` | `applications` | `job_id` | `text` |
| `careerloop` | `background_runs` | `run_id` | `text` |
| `careerloop` | `daily_brief_items` | `job_id` | `text` |
| `careerloop` | `daily_briefs` | `run_id` | `text` |
| `careerloop` | `event_timeline` | `reference_id` | `text` |
| `careerloop` | `job_candidates` | `matched_job_id` | `text` |
| `careerloop` | `jobs` | `canonical_id` | `text` |
| `careerloop` | `jobs` | `id` | `text` |
| `careerloop` | `outcome_events` | `job_id` | `text` |
| `careerloop` | `outreach_messages` | `job_id` | `text` |
| `careerloop` | `people_to_reach` | `job_id` | `text` |
| `careerloop` | `run_events` | `event_id` | `text` |
| `careerloop` | `run_events` | `run_id` | `text` |
| `careerloop` | `sessions` | `active_artifact_id` | `text` |
| `careerloop` | `sessions` | `active_brief_id` | `text` |
| `careerloop` | `sessions` | `active_job_id` | `text` |
| `careerloop` | `sessions` | `active_pack_id` | `text` |
| `careerloop` | `sessions` | `current_job_id` | `text` |
| `careerloop` | `strategic_tracks` | `resume_variant_id` | `text` |
| `careerloop` | `user_job_relationships` | `job_id` | `text` |

## 5. Tables Referencing public.users

**Count: 0 tables** need FK migration to `careerloop.users`

No tables reference `public.users`. FK migration not required.

## 6. Recommendations

- **ID Type Migration:** 23 TEXT column(s) in `careerloop` schema should be migrated to UUID.

# USER STATE FORENSICS AUDIT

**Target Email:** siddharth.swami99@gmail.com
**System User ID:** `730d5bab-2587-4507-a16a-70cd662d59c2`
**Generated At:** 2026-05-30T16:02:17+05:30 (Current local time: 2026-05-30)

This document contains the exact database state of the user `siddharth.swami99@gmail.com` across all onboarding, user, and session persistence layers inside the Supabase PostgreSQL database.

---

## 1. Auth Record & Canonical Spine (`careerloop.users`)

The canonical user identity record in `careerloop.users` represents the system identity for all active interactions.

* **`id`**: 730d5bab-2587-4507-a16a-70cd662d59c2 (type: str)
* **`email`**: siddharth.swami99@gmail.com (type: str)
* **`phone`**: None (type: NoneType)
* **`telegram_id`**: None (type: NoneType)
* **`whatsapp_id`**: None (type: NoneType)
* **`linkedin_url`**: None (type: NoneType)
* **`full_name`**: Siddharth Saminathan (type: str)
* **`onboarding_status`**: new (type: str)
* **`signup_source`**: google (type: str)
* **`current_plan`**: free (type: str)
* **`trial_started_at`**: None (type: NoneType)
* **`trial_ends_at`**: None (type: NoneType)
* **`status`**: active (type: str)
* **`created_at`**: 2026-05-29 08:37:45.722168+00:00 (type: datetime)
* **`updated_at`**: 2026-05-29 08:37:45.722168+00:00 (type: datetime)
* **`last_active_at`**: 2026-05-30 10:24:39.324024+00:00 (type: datetime)
* **`telegram_chat_id`**: None (type: NoneType)
* **`phone_number`**: None (type: NoneType)
* **`handle`**: None (type: NoneType)
* **`target_roles`**: AI Product Engineer, AI Engineer, Founding AI Engineer, Machine Learning Engineer, NLP Engineer (type: str)
* **`target_cities`**: Chennai, Bangalore, Bengaluru, Remote (type: str)
* **`salary_expectations`**: None (type: NoneType)
* **`notice_period`**: None (type: NoneType)
* **`career_mode`**: explore (type: str)
* **`onboarding_complete`**: False (type: bool)
* **`master_cv_markdown`**: None (type: NoneType)
* **`work_style_prefs`**: {} (type: dict)

---

## 2. Legacy Auth Record (`public.users`)

The legacy profile table. Note that some older columns remain here.

No record found.

---

## 3. Session State Record (`careerloop.sessions`)

This represents the active, in-memory state serialized to disk to survive backend server reloads.

* **`user_id`**: 730d5bab-2587-4507-a16a-70cd662d59c2 (type: str)
* **`state`**: NEW_USER (type: str)
* **`current_job_id`**: None (type: NoneType)
* **`onboarding_step`**: 1 (type: int)
* **`temp_profile_data`**: {'_active_conversation_id': 'f337f33a-6e80-442d-a9cd-20a44a9d2764'} (type: dict)
* **`updated_at`**: 2026-05-30 10:24:40.325692+00:00 (type: datetime)
* **`active_artifact_type`**: None (type: NoneType)
* **`active_artifact_id`**: None (type: NoneType)
* **`active_job_id`**: None (type: NoneType)
* **`active_brief_id`**: None (type: NoneType)
* **`active_pack_id`**: None (type: NoneType)
* **`current_selection_index`**: None (type: NoneType)

---

## 4. Conversation Records (`careerloop.conversations`)

Active chat contexts initiated by the user.

### Conversation #1

* **`id`**: f337f33a-6e80-442d-a9cd-20a44a9d2764 (type: str)
* **`user_id`**: 730d5bab-2587-4507-a16a-70cd662d59c2 (type: str)
* **`transport`**: cli (type: str)
* **`external_chat_id`**: None (type: NoneType)
* **`status`**: active (type: str)
* **`created_at`**: 2026-05-30 10:24:40.181049+00:00 (type: datetime)
* **`updated_at`**: 2026-05-30 10:24:40.181049+00:00 (type: datetime)

### Conversation #2

* **`id`**: 8105df4c-7dbf-4d99-bdc0-a5deb17d0e8e (type: str)
* **`user_id`**: 730d5bab-2587-4507-a16a-70cd662d59c2 (type: str)
* **`transport`**: cli (type: str)
* **`external_chat_id`**: None (type: NoneType)
* **`status`**: active (type: str)
* **`created_at`**: 2026-05-30 09:41:16.816794+00:00 (type: datetime)
* **`updated_at`**: 2026-05-30 09:41:16.816794+00:00 (type: datetime)

### Conversation #3

* **`id`**: ab7798b6-46de-4d13-827a-6c5f928043de (type: str)
* **`user_id`**: 730d5bab-2587-4507-a16a-70cd662d59c2 (type: str)
* **`transport`**: cli (type: str)
* **`external_chat_id`**: None (type: NoneType)
* **`status`**: active (type: str)
* **`created_at`**: 2026-05-29 18:32:44.785626+00:00 (type: datetime)
* **`updated_at`**: 2026-05-29 18:32:44.785626+00:00 (type: datetime)

### Conversation #4

* **`id`**: 8712ee6d-0145-443f-b388-9829f65261f3 (type: str)
* **`user_id`**: 730d5bab-2587-4507-a16a-70cd662d59c2 (type: str)
* **`transport`**: cli (type: str)
* **`external_chat_id`**: None (type: NoneType)
* **`status`**: active (type: str)
* **`created_at`**: 2026-05-29 15:26:44.536437+00:00 (type: datetime)
* **`updated_at`**: 2026-05-29 15:26:44.536437+00:00 (type: datetime)

---

## 5. Message History Trace (`careerloop.messages` - Last 20 messages)

A listing of the recent message exchanges. This logs the conversation flow.

| Message ID | Conversation ID | Role | Action Type | Created At | Content Preview |
|------------|-----------------|------|-------------|------------|-----------------|
| `0771d4fd-c23a-47d1-9561-879382d80161` | `f337f33a-6e80-442d-a9cd-20a44a9d2764` | `assistant` | `None` | 2026-05-30 10:26:19.031867+00:00 | That looks too short to be a full CV. Please paste your complete resume text, or |
| `6e4b3445-a57e-4030-bc1b-3bb6ee4706bd` | `f337f33a-6e80-442d-a9cd-20a44a9d2764` | `user` | `None` | 2026-05-30 10:26:18.895544+00:00 | wtf¨ |
| `a8b9694d-3f89-4abd-9ca6-b71341cdd0ca` | `f337f33a-6e80-442d-a9cd-20a44a9d2764` | `assistant` | `None` | 2026-05-30 10:26:12.266554+00:00 | That looks too short to be a full CV. Please paste your complete resume text, or |
| `89aaf1dc-05bb-4b95-987e-50f74a62ef21` | `f337f33a-6e80-442d-a9cd-20a44a9d2764` | `user` | `None` | 2026-05-30 10:26:12.128252+00:00 | do you even know my name |
| `68ccc91c-eb4d-4fa8-8be1-3b7d3780ff3a` | `f337f33a-6e80-442d-a9cd-20a44a9d2764` | `assistant` | `None` | 2026-05-30 10:24:40.749793+00:00 | That looks too short to be a full CV. Please paste your complete resume text, or |
| `0fae5b5e-3275-4c65-b211-db9d227e3104` | `f337f33a-6e80-442d-a9cd-20a44a9d2764` | `user` | `None` | 2026-05-30 10:24:40.513639+00:00 | hello |
| `6203220a-bc29-4cf5-b771-b3de004f513a` | `8105df4c-7dbf-4d99-bdc0-a5deb17d0e8e` | `assistant` | `None` | 2026-05-30 09:41:17.706715+00:00 | I couldn't find a confident LinkedIn match for **hello**.  No problem — please p |
| `2949a59f-3963-42ec-b0e4-0750f71d6b56` | `8105df4c-7dbf-4d99-bdc0-a5deb17d0e8e` | `user` | `None` | 2026-05-30 09:41:17.184214+00:00 | hello |
| `cb276350-1ba0-4881-8bda-e43c41b71991` | `ab7798b6-46de-4d13-827a-6c5f928043de` | `assistant` | `None` | 2026-05-29 18:33:00.473451+00:00 | Hey there! 👋 Ready to dive back in or just saying hi? Let me know how I can help |
| `7ca30b02-c033-4b5f-a6eb-52f8cdf86311` | `ab7798b6-46de-4d13-827a-6c5f928043de` | `user` | `None` | 2026-05-29 18:32:45.870142+00:00 | hello |
| `d78e0a5f-f1d2-4072-af85-ae0b7fc473eb` | `8712ee6d-0145-443f-b388-9829f65261f3` | `assistant` | `None` | 2026-05-29 15:37:12.425416+00:00 | Haha, you're the boss! 😄 Let me know when you're ready to get back to job huntin |
| `d2831562-004d-4519-a448-f3e147bade45` | `8712ee6d-0145-443f-b388-9829f65261f3` | `user` | `None` | 2026-05-29 15:37:07.955540+00:00 | yes sir |
| `2fe2c81d-0a69-41a3-831a-06b45b28f4f4` | `8712ee6d-0145-443f-b388-9829f65261f3` | `assistant` | `None` | 2026-05-29 15:36:59.414415+00:00 | Haha, I appreciate you putting in the effort to test me out, bro! 😄 Take a break |
| `5f9ff8dd-ac92-43bf-ba29-07dfb44cb396` | `8712ee6d-0145-443f-b388-9829f65261f3` | `user` | `None` | 2026-05-29 15:36:54.814552+00:00 | bro you are wokring ha good bro i feel very tired testing you wtf |
| `7154d259-aee8-4af9-a7d3-d0848cf7642a` | `8712ee6d-0145-443f-b388-9829f65261f3` | `assistant` | `None` | 2026-05-29 15:36:38.241371+00:00 | Hey Siddharth! 👋 Welcome back. What can I help you with today — want to check yo |
| `8930e329-8700-4d52-bf22-e4c1f75ab601` | `8712ee6d-0145-443f-b388-9829f65261f3` | `user` | `None` | 2026-05-29 15:36:32.430634+00:00 | hi |
| `d2f1f9eb-0125-4b89-ad64-92bf35250117` | `8712ee6d-0145-443f-b388-9829f65261f3` | `assistant` | `None` | 2026-05-29 15:36:19.374636+00:00 | **Today's matches:** Show your latest job brief **Scan for jobs:** Search for ne |
| `4b39f00a-1e91-42fb-b0d8-49f5a70d85b8` | `8712ee6d-0145-443f-b388-9829f65261f3` | `user` | `None` | 2026-05-29 15:36:16.316228+00:00 | Help |
| `6f82cc7d-614d-4f3a-a4b5-6f5b6fff70ef` | `8712ee6d-0145-443f-b388-9829f65261f3` | `user` | `None` | 2026-05-29 15:34:49.105352+00:00 | hi |
| `db195951-7490-4240-ab35-9828ffd0a177` | `8712ee6d-0145-443f-b388-9829f65261f3` | `user` | `None` | 2026-05-29 15:31:20.356439+00:00 | bro wtf |

---

## 6. Onboarding Completeness Checklist (Database-verified)

Based on the actual records queried above:
- **`careerloop.users.onboarding_status`**: `new`
- **`careerloop.sessions.state`**: `NEW_USER`
- **`careerloop.sessions.onboarding_step`**: `1`
- **Resume Status (Master CV Markdown in `careerloop.users` / `public.users`)**: ❌ Not Extracted (Null/Empty)
- **Profile Completeness**: ❌ Incomplete

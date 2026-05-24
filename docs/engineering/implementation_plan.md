# Tal-Inspired Onboarding & Dynamic Deep-Research Routing

This plan outlines the architecture, database changes, state machine transitions, and routing updates required to implement a conversational, LinkedIn-driven onboarding experience and a dynamic, multi-turn company deep-research chatbot node in CareerLoop.

## Proposed Changes

### Session & Routing Layer

#### [MODIFY] [states.py](file:///Users/siddharthsaminathan/projects/CareerLoop/careerloop/session/states.py)
*   Add new states: `ONBOARDING_IDENTIFYING`, `ONBOARDING_PROFILE_CONFIRMATION`, and `RESEARCHING_COMPANY`.
*   Update `normalize_user_state` mapping to support transitions.

#### [MODIFY] [supervisor_graph.py](file:///Users/siddharthsaminathan/projects/CareerLoop/careerloop/session/supervisor_graph.py)
*   Add a new `deep_research` node to invoke dynamic company intelligence reports in real-time.
*   Update `ConversationState` schema to include `pending_research_company` and `specific_question`.
*   Update `route_from_intent` conditional routing to route `RESEARCHING_COMPANY` state to the `deep_research` node.

#### [MODIFY] [llm_chat.py](file:///Users/siddharthsaminathan/projects/CareerLoop/careerloop/llm_chat.py)
*   Upgrade `ChatIntentAgent` to accept the conversational `messages` history rather than just the last user message, resolving pronouns (e.g., "yes, do it" -> "inspect CheQ funding").
*   Add `DEEP_RESEARCH` classification intent.

---

### Onboarding & Scraper Modules

#### [MODIFY] [onboarding_flow.py](file:///Users/siddharthsaminathan/projects/CareerLoop/careerloop/onboarding/onboarding_flow.py)
*   Implement the conversational name gathering step.
*   Hook the LinkedIn discovery search and display profile confirmation card.
*   Trigger the extraction of titles, experience, location, and prefill `users` table preferences in DB.

#### [NEW] [linkedin_scraper.py](file:///Users/siddharthsaminathan/projects/CareerLoop/careerloop/sources/linkedin_scraper.py)
*   Implement `LinkedInScraper` using SerpAPI / DuckDuckGo for discovery.
*   Implement Playwright or Proxycurl profile crawler and parser mapping.

---

### Company Intelligence & Discovery Guards

#### [MODIFY] [company_intel.py](file:///Users/siddharthsaminathan/projects/CareerLoop/careerloop/company_intel.py)
*   Integrate cache-aware `get_or_build_company_intelligence` builder in deep research routing.

#### [MODIFY] [discovery.py](file:///Users/siddharthsaminathan/projects/CareerLoop/careerloop/discovery.py)
*   Wire `verify_opportunity_link` gate inside discovery adapters to filter out expired listings in real-time.

---

## Verification Plan

### Automated Tests
*   `pytest careerloop/tests/test_routing.py` - Verify intent router handles `DEEP_RESEARCH` intent with multi-turn messages.
*   `pytest careerloop/tests/test_onboarding.py` - Verify the new multi-state onboarding transition flow from `IDLE` to `PROFILE_COMPLETE`.

### Manual Verification
*   Run the CLI shell: `./.venv/bin/python3 careerloop/chat_cli.py`
*   Type `/reset` or onboard a new user. Type a name and verify search results.
*   Say "yes" to confirm the profile, verifying that details are scraped and saved to SQLite database.
*   Ask about "CheQ" or "BigRio" funding status, say "yes bro can you do it", and verify the chatbot dynamically runs the intelligence engine and replies with rich real-time funding details.

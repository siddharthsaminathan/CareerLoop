# CareerLoop Interview Playbook
## Auto-Generated from Your Interview Experiences

> This document grows with every interview. The CareerLoop agent updates it automatically.
> Patterns emerge over time. Your weak spots become visible. Your prep becomes targeted.

---

## Patterns Across All Interviews

### Your Recurring Blunders
- **"I don't know" without redirect** — 1 of 1 interview
  - Example: Epic interview — said "I don't know" to get_state, checkpointer method names instead of redirecting to what you DID build

### Most Common Question Types
- **Framework Trivia** — 1 of 1 interviews
  - LangGraph checkpointer, get_state, tool calling mechanics
- **ML Architecture** — 1 of 1 interviews
  - Transformers, decoder vs encoder-decoder, MoE

### Your Strengths
- **ML fundamentals** — consistently strong
  - Correctly explained decoder-only, encoder-decoder, Mixture of Experts
- **Real engineering experience** — stands out
  - DeepSeek cost optimization workflow, NotebookLM hack, 47 commits in 4 days
- **Product thinking** — connects tech to business
  - Hyper-personalization pitch for media company

### Companies & Outcomes
| Company | Role | Date | Outcome |
|---------|------|------|---------|
| Epic | AI Engineer | 2026-05-20 | Pending |

---

## Interview Log

## Company: Epic — AI Engineer
**Date:** 2026-05-20 | **Round:** Technical Screening | **Outcome:** Pending

### Questions Asked
- What is the difference between LangChain and LangGraph?
- How do you persist state in LangGraph? (checkpointer)
- How do you get the state of the graph? (get_state)
- How does the model know which tool to pick? (tool calling mechanics)
- How do LLMs work? (architecture — transformers, decoder-only, encoder-decoder)
- What is MCP and its advantages?
- What bottlenecks have you identified with AI coding tools?
- Do you use AI assistants for coding?
- How do you optimize your workflow and costs?
- Why do you want to work at Epic?

### What Went Well
- ML architecture knowledge — correctly explained GPT as decoder-only, encoder-decoder for older models, MoE for Llama Maverick and DeepSeek
- MCP explanation — described it as connecting external system resources to the model
- Real workflow optimization story — DeepSeek model selection, cost consciousness, NotebookLM hack
- Product thinking — hyper-personalization pitch connecting Emote's emotional layer to media
- Tool calling basics — correctly described the model picking from available tools

### Blunders

#### "How do you persist state in LangGraph?"
**What happened:** Described checkpointing correctly as "tracks internal flow so graph doesn't reinitialize" but didn't use the word "persistence" or name the specific classes (MemorySaver, SqliteSaver).
**Root cause:** Knew the CONCEPT but not the EXACT terminology the interviewer expected.
**Fix:** Next time say: "I use checkpointing for persistence. LangGraph has MemorySaver for dev, SqliteSaver/PostgresSaver for production. In my CareerLoop pipeline, I built custom persistence — JSON artifacts per stage — because I needed structured access to 20+ state fields."

#### "How do you get the state of the graph?"
**What happened:** Said "I don't know" — didn't know the exact method name get_state().
**Root cause:** Didn't prepare LangGraph API memorization. Said "I don't know" without redirecting to experience.
**Fix:** Never say "I don't know" alone. Always follow with: "I don't remember the exact method — in my pipeline I access state through the TypedDict directly. I built an 8-node StateGraph where each node reads/writes 20+ fields."

#### "How does the model know which tool to pick?"
**What happened:** Described it as "model has a list of tools and picks one" — correct but too shallow. Didn't mention tool schemas injected into system prompt, instruction tuning via RLHF, conditional edge routing in LangGraph.
**Root cause:** Knew the WHAT but not the detailed HOW of tool calling mechanics.
**Fix:** "Two layers. First, tool schemas (name, description, parameters JSON) are injected into the system prompt. The model was instruction-tuned to output structured tool_calls. Second, in LangGraph, you bind tools with llm.bind_tools() and add a conditional edge that routes to ToolNode when tool_calls are present."

#### Frame Control — Let interviewer control to LangGraph trivia
**What happened:** After 2nd "I don't know," continued answering trivia questions instead of redirecting to built systems. Interviewer kept asking LangGraph method names for 5+ minutes.
**Root cause:** Didn't recognize the interviewer type (Trivia Gatekeeper) and didn't redirect to impact.
**Fix:** After 2nd trivia question: "I don't memorize method names — I read docs when needed. What I CAN tell you is I built an 8-stage LangGraph pipeline that processes CVs through LLM nodes with JSON schema validation. Let me walk you through the architecture."

### Learnings
- Every "I don't know" must have a "but here's what I DID" follow-up — never leave a gap
- Map your usage to their terminology — "checkpointing" → "I use it for persistence, here's how"
- Recognize Trivia Gatekeeper interviewers early — redirect to impact after 2 trivia questions
- Lead with what you BUILT, not what you memorized — you're a builder, not a framework expert
- Interviewer was testing memorization, not engineering ability — your answers were conceptually correct, just wrong vocabulary

### Follow-Up
- [ ] Send thank-you email — by May 22
- [ ] Memorize LangGraph API names for next technical round (get_state, get_state_history, update_state, SqliteSaver)
- [ ] Prepare deep-dive on CareerLoop LangGraph architecture (8-node graph, state management, parallel S7)
- [ ] Practice redirect phrase: "I don't know the method, but here's what I built with it"

---

## Recommended Prep for Next Interview
<!-- Auto-generated from patterns -->

Based on your 1 interview so far:
1. **Weak area to drill:** Framework API memorization (LangGraph method names, tool calling pattern)
2. **Most common question to prep:** Framework trivia — expect LangGraph/LangChain specifics at Indian companies
3. **Strength to lead with:** Real engineering experience — REDIRECT every trivia question to your built systems

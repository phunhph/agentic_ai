---
workflowType: 'prd'
workflow: 'edit'
classification:
  domain: 'CRM'
  projectType: 'Multi-Agent AI Sales Copilot'
  complexity: 'High'
inputDocuments: []
observations: []
stepsCompleted: ['step-e-01-discovery', 'step-e-02-review', 'step-e-03-edit']
date: '2026-04-11'
lastEdited: '2026-04-11'
editHistory:
  - date: '2026-04-24'
    changes: 'Added anti-rote learning constraints and reasoning-vs-lean integrity contract to prevent memorization drift and preserve execution consistency across personas.'
  - date: '2026-04-24'
    changes: 'Implemented full-system core upgrades: metadata-driven dynamic identity resolution, event lifecycle ack flow (<1.5s target), persona-driven tactician layer, and Trust Firewall gating for learning writes.'
  - date: '2026-04-24'
    changes: 'Aligned with core runtime behavior: corrected ambiguity/trust-gate interpretation, documented deterministic auto-execute for identity-specific queries, and standardized professional response style for result presentation.'
  - date: '2026-04-13'
    changes: 'Formalized Brainstorming gaps: Added SpaceMember identity (Phase 1), Dynamic Sales Profiler + Active Probe (Phase 3), Trust Firewall (DC4) + Persona Adaptation (DC5), FR10-FR12 for Identity & Personalization, NFR5 for Trust Firewall enforcement.'
  - date: '2026-04-11'
    changes: 'Refined Product Scope & Architecture per Party Mode feedback: Re-scoped to Missing Puzzle Syndrome & Ecosystem Ingestion. Added Mixs Nullable structure and Delay-Tolerant thresholds (5s/5m).'
  - date: '2026-04-11'
    changes: 'Major rewrite: Shifted product vision from Data Entry Tool to Sales Copilot based on brainstorming session 2026-04-11. Introduced North Star Principle, Trust Firewall, Dynamic Sales Profiler, Persona-Driven Compass, Dual-Mode Intelligence, and Co-Evolution Architecture.'
  - date: '2026-04-10'
    changes: 'Enforced Google Chat Cards V2 & Rich Formatting for all agent output responses.'
  - date: '2026-04-10'
    changes: 'Marked MVP Phase 1 as DONE. Recorded completion of Ingestion, Multi-Agent Engine, State Management, and E2E Automation Testing.'
  - date: '2026-04-09'
    changes: 'Updated to reflect Multi-Agent Architecture, Pub/Sub ingestion, Tiered Memory, and explicit Data Models'
  - date: '2026-04-09'
    changes: 'Refined FR semantic format, removed implementation leakage, scoped Admin out for MVP.'
---

# Product Requirements Document - NextGen CRM

**Author:** qaz
**Date:** 2026-03-29 (Updated: 2026-04-11)

## 1. Executive Summary

NextGen CRM is an intelligent Sales Copilot that operates as a strategic partner for sales teams through Google Chat. Its singular mission is to **help each salesperson close deals** — not to collect data or enforce compliance. 

The system treats CRM as infrastructure: an organized database that enables comparison, querying, and relationship tracking. It operates on the **"Missing Puzzle Syndrome" philosophy**: B2B Sales inherently involves missing data. Instead of forcing salespeople to fill forms, the system manages this uncertainty gracefully. Data entry is a natural byproduct of **Ecosystem Ingestion** (silently observing and extracting data from existing chats) rather than an explicit goal.

### North Star Principle

> **The Agent's only objective is to help Sales complete their selling mission.** Every system behavior serves this objective. Any feature that does not directly contribute to helping Sales sell is eliminated.

### Design Pillars

1. **Action-First:** The Agent delivers tactical advice before recording data. CRM writes happen silently in the background from conversation context.
2. **Ecosystem Ingestion:** Agent acts as a parasitic observer in the chat ecosystem. It intercepts streams, uses time-delays to let humans interact, and leaves Emoji Signals (🔴/🕵️) without generating bot noise.
3. **Lineage Copilot:** The Agent continuously absorbs tactical logic specifically from CEO/Senior Sales to serve as an expert proxy for junior reps.

## 2. Success Criteria

### User Success
- **Zero-UI Data Entry:** Sales representatives spend 0 minutes per day performing manual data entry.
- **Missing Puzzle Handling:** System intelligently flags when critical information is missing via Emoji Signals instead of blocking workflows.
- **Tactical Daily Compass:** Every salesperson receives a personalized tactical briefing replacing generic reminders.

### Business Success
- **Organic Adoption & Zero Training:** 100% daily active usage driven by natural language interaction.
- **Deal Velocity Improvement:** Measurable reduction in average deal cycle time through proactive Agent coaching.

### Technical Success
- **Flexible Schema ("Mixs" Field):** Core tables process unpredictable information safely using a flexible JSON `mixs` field alongside required core columns.
- **Delay-Tolerant Routing:** Strict 5-second and 5-minute evaluation delays implemented to respect human-to-human interaction within Google Chat Spaces.
- **Core Trust-Gate Accuracy:** Queries with explicit identity signals (exact name/code) must pass trust gate and execute deterministically; clarify mode is reserved for genuinely ambiguous requests only.

## 2.1 Core Runtime Flow (Current Priority)

For the current build stage, the key behavior is validated in the core runtime pipeline (surface-agnostic):

1. **Ingest:** Normalize query and extract intent/entities/filters/update_data with ambiguity score.
2. **Reason:** Build planner trace and decision state (`auto_execute` or `ask_clarify`).
3. **Plan:** Compile schema-safe execution plan from ingest + reason outputs.
4. **Validate + Trust Gate:** Enforce metadata guardrails and reasoning consistency checks.
5. **Execute:** Run query/update only when trusted.
6. **Respond:** Return professional, concise, business-readable output with actionable next step.

**Decision rules**
- Explicit identity + valid plan => prioritize `auto_execute`.
- `ask_clarify` only for high ambiguity, missing target entity, or invalid schema constraints.
- Empty data is an execution outcome, not a trust failure.

## 3. Product Scope

### Phase 1 (Foundation): Patient Harvester & Missing Puzzle Syndrome - [STATUS: DONE/REFINING]
**Focus:** Prove the UI-less, agent-driven chat interaction model while embracing data uncertainty.
**Capabilities:**
- Asynchronous message ingestion via GCP Pub/Sub.
- State Management and Debouncing Engine.
- Multi-Agent Orchestration (Router, Gatekeeper, Analyst, Operator).
- **Missing Puzzle Data Models:** Implementation of Nullable DB models accompanied by a flexible `mixs` JSON key-value field to catch and analyze non-structured attributes without rigid Schema requirements.
- **SpaceMember Identity Model:** Manual configuration of Google Chat sender IDs mapped to CRM user profiles containing role, experience level, and tone preference — foundational data model enabling all downstream persona-driven response adaptation.

### Phase 2 (Ingestion & UX): Silent Observer & Ecosystem Ingestion - [STATUS: PLANNED]
**Focus:** Evolve into a "parasitic" listener that observes deal flow silently and alerts dynamically without noise.
**Capabilities:**
- **Google Drive/Docs Interception:** Capable of reading contents from Google Docs or Drive file links mentioned within the ecosystem to expand context.
- **Time-Delay Interception Rules:** 
  - **Explicit Agent Mention:** Processed IMMEDIATELY (0 delay).
  - **General Space Query (No mentions):** Processed after 5 seconds delay.
  - **Explicit Human Mention:** [MOVED TO POST-MVP] Logic for 5-minute delay to allow human response is deferred.
- **Emoji Signaling:** Use native chat reactions (🔴, 🕵️) to indicate missing logic or data risks instead of spamming space with text messages.

### Phase 3 (Cognitive): B2B Sensemaker & Adaptive Personalization - [STATUS: PLANNED]
**Focus:** Elevate from Data extractor to Cognitive Consultant with persona-aware responses.
**Capabilities:**
- Resolve cause-and-effect relationship mapping within Accounts.
- Identify H2H (Human-to-Human) relationship gaps and generate "Viable Steps" to remove friction in B2B buying committees.
- **Dynamic Sales Profiler:** Automatic tracking of salesperson capability metrics (deal velocity, follow-up frequency, communication depth) to replace manual experience level assignment with data-driven profiling.
- **Persona-Driven Response:** Agent adapts communication style — concise closed-choice guidance for junior reps, strategic open-ended intelligence for senior reps — based on Dynamic Profiler scores.
- **Active Probe:** Agent-initiated proactive questions to Sales when critical data gaps are detected, complementing the existing passive ingestion mode (Dual-Mode Intelligence).

### Phase 4 (Proactive Output): The Extraction Tactician - [STATUS: PLANNED]
**Focus:** Provide strategic weapons to close the deal.
**Capabilities:**
- Push situational scripts and closing tactics automatically when specific deal hurdles are identified via Passive Intel.
- Transition from "Here is what is missing" to "Here is the exact email/question to ask to get what is missing."

### Parallel Phase: The Lineage Copilot & Strategic Escalation - [STATUS: PLANNED]
**Focus:** Transplant CEO/Top-performer DNA into the core bot.
**Capabilities:**
- Independent vector pipeline that stores the CEO's specific negotiation frameworks and playbooks.
- **Strategic Escalation Protocol:** When the Copilot faces ambiguity outside its confidence threshold, it retreats and explicitly @mentions a designated Senior or CEO to intervene in the chat.

## 4. User Journeys

### 1. The Core Update Path (Patient Harvester)
- **Situation:** A sales rep updates a deal in the Account's mapped Google Chat Space: *"Budget is $50k, VP approved. Still missing tech-reqs."*
- **Action:** System waits 5 seconds (no specific mention).
- **Resolution:** Operator extracts exact values into standard columns, dumps unstructured notes into `mixs` JSON field, and reacts with 💾.

### 2. The Silent Observer Path (Emoji Interception)
- **Situation:** Sales rep tags a Solution Engineer: *"@Engineer please send them the standard SLA draft."*
- **Action:** System detects human-to-human tag. Waits 5 minutes.
- **Resolution:** After identifying that standard SLA applies but the customer has custom compliance needs (Missing Puzzle), Agent adds 🔴 reaction to the message and replies: *"Lưu ý: Khách hàng này áp dụng ISO27001, form SLA này cần update Security terms."*

### 3. The Extraction Tactician Path
- **Situation:** Deal stalls at "Evaluating".
- **Resolution:** Agent pushes an Interactive Card suggesting: *"Anh đang chững lại vì chưa biết ai là Economic Buyer. Đề xuất gửi email này để thăm dò: [Template]."*

### 4. The Lineage Escalation Path (Strategic Guardrails)
- **Situation:** Customer asks for a 40% discount in exchange for a 3-year lock-in. 
- **Resolution:** Agent recognizes this breaches standard bounding parameters. Instead of hallucinating, Agent replies: *"Deal này vượt khung chiết khấu chuẩn. @CEO anh vào đánh giá cấu trúc 3 năm này nhé."*

### 5. The Persona-Driven Response Path (Adaptive Personalization)
- **Situation A (Junior):** A new sales rep messages: *"Khách hàng chần chừ về ngân sách, phải làm gì?"*
- **Resolution A:** Agent detects junior experience level → delivers closed-choice guidance: *"Chọn 1 trong 3 hành động: (1) Xin lịch gọi tư vấn giảm cấu hình, (2) Đợi 2 ngày gửi báo giá chiết khấu, (3) Gửi tài liệu ROI."*
- **Situation B (Senior):** A senior rep discusses the same client hesitation.
- **Resolution B:** Agent detects senior experience level → provides strategic intelligence: *"Tín hiệu thụ động cho thấy khách chần chừ. Người này tính D (Quyết đoán) nhưng bị giới hạn quy trình nội bộ. Anh dự tính triển khai chiến thuật nào tiếp theo?"*

## 5. Domain Requirements

- **Internal Tool Data Baseline:** As an internal application, raw chat text does not require strict PII scrubbing.
- **Zero-Retention LLM Processing:** The public cloud LLM (Gemini 2.5 Flash) must be accessed via enterprise API contracts guaranteeing zero-day data retention for model training.

## 6. Innovation Analysis

- **Mixs JSON Anti-Fragility:** Traditional CRM schemas break when B2B conversations wander. The `mixs` field ensures we capture 100% of context without 100% rigid DB coupling.
- **Delay-Tolerant Engine:** The 0s/5s/5m threshold matrix respects the biological pacing of human teams, making the AI feel like a respectful participant rather than an impatient bot. 

## 7. Design Constraints

### North Star Enforcement
- **DC1:** The `mixs` field must be queryable by the Analyst Agent, ensuring flexible data isn't locked away in cold storage.
- **DC2:** CRM data capture must NEVER block, delay, or interrupt the Agent's primary action of delivering tactical advice to the salesperson.

### Action-First Enforcement
- **DC3:** In every Agent response, tactical recommendation or strategic intelligence must be the primary content. CRM confirmation or data status must appear as secondary/auxiliary information only.

### Trust Firewall Enforcement
- **DC4:** Profiler data (experience level, capability metrics, behavioral patterns) collected by the Dynamic Sales Profiler MUST only be used to adapt the Agent's communication style for that specific salesperson. No endpoint, query, or report may expose this data to managers or other users.
- **DC5:** The Agent MUST adapt communication depth and tactical framing based on the sender's profile: closed-choice guidance for junior-level senders, strategic open-ended intelligence for senior-level senders. This adaptation is mandatory from Phase 1 (using manual profile data) and evolves with Dynamic Profiler in Phase 3.

## 8. Functional Requirements

### 1. Ingestion Ecosystem (Phase 1 & 2)
- **FR1:** The Async Worker can ingest Google Chat ecosystem messages asynchronously.
- **FR2:** The Orchestrator can dynamically route message processing buffers based on Mention Rules:
  - Immediate execution (0s) for @Agent mentions.
  - 5-second buffer for unlabeled messages.
  - (5-minute buffer for human mentions is deferred to later phases).
- **FR3:** The Async Worker can execute background evaluations during human-delay thresholds, signaling completion or warnings utilizing exclusively Emoji additions (🔴, 🕵️) to the target message ID.
- **FR4:** The Operator Node can persist unpredictable context beyond standard BANT parameters into a flexible schema for all core entity tables.

### 2. Cognitive Multi-Agent Intelligence (Phase 3 & 4)
- **FR5:** The Router Node can classify user intent (QUERY, UPDATE, CREATE, HELP, COMPASS) via a dedicated evaluation state.
- **FR6:** The Analyst Node can execute read-only analytical queries spanning both rigid schema fields and the flexible schema structure.
- **FR7:** The Extraction Tactician can propose specific communication templates and "Viable Steps" when a deal is stalled (>5 days without activity) or missing >2 out of 4 BANT criteria.
- **FR7.1 (Implemented Core):** Tactician outputs are persona-aware (Junior/Senior/Default) and include next-steps, templates, and probe questions when stalled/empty-result signals occur.

### 3. Lineage Copilot (Parallel Phase)
- **FR8:** The Lineage Copilot can query an independent semantic knowledge store dedicated to CEO/Senior frameworks to guide responses.
- **FR9:** The Gatekeeper Node can execute an explicit @mention escalation fallback to designated human IDs when confidence threshold falls below required operating bounds.

### 4. Identity & Personalization (Phase 1 Foundation + Phase 3 Evolution)
- **FR10:** The System can associate a Google Chat sender ID with a persistent user profile (SpaceMember) containing role, experience level, and tone preference to contextualize all downstream Agent responses.
- **FR11:** The Tactician Node can adapt its communication style (tactical depth, option framing, language register) based on the sender's experience level provided in the user context.
- **FR12:** The Agent can initiate proactive outbound questions to a salesperson when the system detects critical data gaps that affect deal progression (Phase 3 — Active Probe).

## 9. Non-Functional Requirements

### Performance & Latency
- **NFR1 - Acknowledgment Limit:** The Async Worker can apply a processing emoji (⏳) within 1.5 seconds of receiving the async messaging event for immediate-priority tasks.
- **NFR2 - Event Concurrency:** The Orchestrator can maintain context across active Delay-Tolerant thresholds (managing messages waiting up to 5 seconds) for up to 50 concurrent workspace active threads without memory leaks.

### Security & Privacy
- **NFR3 - LLM Zero-Retention:** The LLM client can utilize enterprise endpoints explicitly configured for zero-day data retention.
- **NFR4 - Ephemeral Memory:** The persistence layer can only store chat logs explicitly in the ephemeral datastore, explicitly discarding the raw chat payload after processing.

### Trust & Access Control
- **NFR5 - Trust Firewall:** The persistence layer can store user profile and capability metrics exclusively for persona-driven response adaptation. No API endpoint or query interface may aggregate or expose individual salesperson profiler data for managerial reporting purposes.
- **NFR6 - Learning Trust Firewall (Implemented Core):** Runtime learning writes must pass firewall policy (`allow/quarantine/reject`) with audit logs and redaction policy before persisting to trainset/lesson stores.
- **NFR7 - Event Ack SLA (Implemented Core):** Event ingress must return first lifecycle acknowledgment within configured SLA target (default 1.5s) and emit lifecycle state transitions for observability.
- **NFR8 - Anti-Rote Learning (Implemented Core):** The learning layer must reject duplicate semantic templates with same outcome to avoid rote memorization from surface wording changes.
- **NFR9 - Reasoning/Presentation Separation (Implemented Core):** Persona/lean layers must not alter execution decision or plan; integrity is verified via runtime plan fingerprint checks.

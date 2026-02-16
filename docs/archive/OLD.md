# Backend Functional Context (Current System)

## Scope
This document captures **what the current backend does** so it can be reused as context for a clean rebuild in a new repository.

## Business Goal
The backend powers a marketplace-style platform with:
- identity and role-based access,
- profile onboarding and verification workflows,
- messaging between buyers, producers, and service providers,
- search and AI-assisted profile/query capabilities,
- notifications and operational observability.

## Primary Actors
- `BUYER`
- `PRODUCER`
- `SERVICE_PROVIDER`
- `ADMIN`
- internal services (service-to-service callers)

## Core Domains and Functional Capabilities

## 1) Identity and Session Domain
Service: auth service

Capabilities:
- Email/password account creation and sign-in.
- Session issuance and session verification.
- Role- and type-aware user records (`BUYER`, `PRODUCER`, `SERVICE_PROVIDER`, plus admin role).
- Onboarding state tracking (`hasOnboarded`).
- Administrative bootstrap path for creating an admin account.

Behavioral outcomes:
- Signup requires a valid user type.
- New non-buyer users can be marked as not onboarded.
- Session verification endpoint is used by other services and proxies to authorize requests.

Additional utility endpoints present:
- Check if a user exists by email.
- Testing-oriented list users endpoint.
- Testing-oriented promote user to admin endpoint.

## 2) Profile and Onboarding Domain
Service: profile service

Capabilities:
- Multi-entity onboarding for producers, service providers, and buyers.
- Draft-first registration lifecycle:
- receive registration payload and documents,
- create draft,
- enrich draft with extracted information,
- allow user/admin review and submission.
- Entity profile CRUD for producers, providers, and buyers.
- Application management (pending/review/rejected/approved paths).
- File and asset management for each entity.
- AI-generated profile content lifecycle (generate, approve, reject).
- Template management for profile rendering/content.
- Dashboard and admin metrics endpoints.

Entity onboarding features:
- `PRODUCER` minimal registration flow with document intake and extraction.
- `SERVICE_PROVIDER` minimal registration flow with provider-specific extraction.
- `BUYER` minimal registration flow with buyer-specific extraction.

Draft and submission lifecycle:
- Create draft.
- Retrieve and update draft.
- Submit draft to application/profile path.
- Draft processing status updates (including success and failure states).

Approval side effects:
- Application approval can trigger account creation in auth domain.
- Welcome email is sent with initial login details after certain approvals.

Visibility model:
- Profile files can have privacy levels (`public`, `protected`).
- Anonymous users get public-facing data.
- Authenticated participants may receive broader (protected) visibility based on role and ownership rules.

Private asset capabilities:
- Producer private asset CRUD via dedicated endpoints.
- Provider private asset CRUD via dedicated endpoints.
- Buyer-specific private asset management in buyer module.

Template capabilities:
- Create template.
- List templates.
- Read template by ID.
- Update template.
- Delete template.
- Set active template.
- Fetch active template.

Search capabilities:
- Producer search endpoint.
- Provider search endpoint.
- Index clearing endpoint for search vectors.

Metrics capabilities:
- Public dashboard stats endpoint (counts and aggregates).
- Admin summary metrics endpoint.

## 3) Communication and Conversation Domain
Service: communication service

Capabilities:
- Buyer-to-producer conversation workflow.
- Buyer/producer-to-provider conversation workflow.
- Conversation initiation, accept/reject, listing, and message history retrieval.
- Real-time WebSocket chat delivery for conversation participants.
- Message creation across content types:
- `text`,
- `image`,
- `video`,
- `audio`,
- `file`.
- Message editing and deletion (with ownership constraints).
- Sharing existing private assets into active conversations.

Buyer-producer conversation flow:
- Buyer initiates chat request.
- Producer accepts or rejects.
- Participants exchange text/media messages when accepted.
- Producer can send private assets into the conversation.

Provider conversation flow:
- Buyer or producer initiates provider chat request.
- Provider accepts or rejects.
- Participants exchange text/media messages when accepted.
- Provider can send provider-private assets into the conversation.

Realtime capabilities:
- WebSocket endpoint for buyer-producer conversations.
- WebSocket endpoint for provider conversations.
- Participant-only access enforced by conversation membership.

Notification side effects:
- New chat request notification.
- Chat approval/decline notification.
- New message notification.

## 4) Notification Domain
Service: notification service

Capabilities:
- Persist notifications for a target user.
- List a user’s notifications.
- Mark notification as read.

Notification types currently modeled:
- `chat_request`
- `chat_request_approved`
- `chat_request_declined`
- `new_message`

Notification payloads include:
- conversation identifiers,
- sender/participant info,
- message payload metadata for new-message events.

## 5) Personalization, Retrieval, and AI Assistant Domain
Service: personalization engine service (+ worker)

Capabilities:
- Query answering endpoint with thread continuity.
- Follow-up question generation endpoint.
- Query-time retrieval filtering by metadata (country/entity type).
- Producer info Q&A module under producer routes.
- Settings-manager conversational assistant for authenticated users.
- FAQ management and AI FAQ answer generation.
- Admin management for LLM settings and prompt configuration.
- Model/provider listing endpoints for model-selection UX.
- Knowledge-base document ingestion for retrieval.

Document knowledge-base capabilities:
- Upload source documents.
- Track document lifecycle/status.
- List document inventory with pagination/filtering.
- Delete document and related vector data.

Document processing lifecycle states:
- `QUEUED`
- `PROCESSING`
- `INDEXED`
- `FAILED`

Settings-manager assistant capabilities:
- Authenticated conversational endpoint.
- Uses user identity/type context.
- Performs asset/profile metadata operations for producers/providers.

Operational endpoints:
- Health check endpoint.
- OpenAPI JSON endpoint.
- Swagger UI endpoint.

## 6) API Gateway and Routing Domain
Service: reverse proxy

Capabilities:
- Path-based routing to backend services:
- `/auth/*`
- `/profile/*`
- `/communication/*`
- `/notification/*`
- `/personalization-engine/*`
- WebSocket upgrade handling for chat endpoints.
- Rate limiting and request-size policies.
- CORS behavior at gateway layer for routed APIs.
- Observability UI exposure path (`/observability/*`).

## Cross-Domain Business Rules (Functional)

- User type is mandatory at account creation.
- Role/type controls who can initiate, approve, or participate in chat workflows.
- Only conversation participants can read/send conversation messages.
- Certain actions are ownership-restricted (for example, editing/deleting own messages).
- Private assets are shareable into chat by authorized entity roles.
- Onboarding and approval are draft/application-driven, not immediate direct profile writes.
- Approvals can trigger downstream account provisioning and welcome communication.
- Search/profile views expose different data depending on authentication and role.
- RAG/query behavior depends on indexed knowledge documents and optional retrieval filters.

## Core Data Concepts to Preserve

- User and session identity records.
- Entity profiles:
- producer,
- service provider,
- buyer.
- Drafts for each entity type.
- Applications and approval/rejection state.
- Files and private assets (with privacy metadata).
- Conversations and messages.
- Notifications and read/unread status.
- FAQ items and activation status.
- LLM settings and prompt configuration per service intent.
- Ingested knowledge documents and indexing status.

## Observable External Integrations (Functional Dependencies)

- MongoDB for primary persistence.
- Redis for transient state and queues.
- Object storage (S3-compatible) for uploaded media/documents.
- Vector database (Pinecone) for semantic retrieval/search.
- LLM and embedding providers (OpenAI/OpenRouter).
- Reranking provider (Cohere).
- Email provider for onboarding/application communications.
- Telemetry/trace sink (Phoenix/OpenTelemetry).

## Current Functional Surface by Service (for Migration Planning)

- Auth:
- account auth flows,
- session verify,
- user existence check,
- admin bootstrap/testing utilities.

- Profile:
- onboarding + drafts,
- profile CRUD,
- application approval/rejection,
- files/assets,
- AI profile lifecycle,
- templates,
- search,
- stats.

- Communication:
- two chat tracks (buyer-producer and initiator-provider),
- message CRUD operations,
- private-asset chat sharing,
- realtime websocket transport.

- Notification:
- create/list/mark-read.

- Personalization:
- query + follow-up,
- producer-info Q&A,
- settings-manager assistant,
- FAQ generation/management,
- prompt/LLM settings management,
- document ingestion and indexing lifecycle.

## Functional Gaps to Account for in New Repo Context

- Backend automated tests are not currently part of the backend codebase.
- Backend CI coverage is not currently equivalent to frontend CI.
- Some utility/test-oriented endpoints exist in production code paths and should be treated carefully during parity planning.

## Key Source Files (for traceability)
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/auth_service/src/app.ts`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/auth_service/src/routes/users.ts`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/profile_service/main.py`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/profile_service/routes/profile_route.py`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/profile_service/routes/service_provider_route.py`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/profile_service/routes/buyer_route.py`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/profile_service/routes/search_route.py`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/communication_service/main.py`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/communication_service/routes/conversations.py`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/communication_service/routes/provider_conversations.py`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/notification_service/main.py`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/personalization_engine_service/src/app.ts`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/personalization_engine_service/src/routes/admin/index.ts`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/personalization_engine_service/src/routes/query.ts`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/personalization_engine_service/src/routes/settingsManager.ts`
- `/Users/abdulmunimjundurahman/work/fluid-projects/dp/PGP/backend/services/reverse_proxy/nginx.conf`

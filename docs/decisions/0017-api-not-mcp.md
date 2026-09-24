# 0017. The service is an HTTP API, not an MCP server

- **Status**: Accepted
- **Date**: 2026-09-24
- **Issue**: #56

## Context

The review and the regulation Q&A could be offered in three ways: as an HTTP API a client calls, as tools on an MCP server that any MCP-capable assistant can plug in, or as an agent other agents talk to over an agent-to-agent protocol (A2A). The course touches all three: the first session prefers an API because MCP servers "are insecure by definition", and the multi-agent session explains that MCP connects an agent to tools while A2A connects agents to agents, possibly across companies.

## Decision

**A typed HTTP API**, as built: FastAPI, Pydantic contracts, OpenAPI at `/docs`. The Streamlit client is one consumer; in a real marketplace the business backend would be the other.

Why not MCP as the interface:

- **Access control lives in HTTP.** The API key, the rate limit and the service token are checked before a request reaches any model ([ADR 0014](0014-grounding-and-retrieval-security.md), #53). An MCP server hands a catalogue of tools to whatever client connects, and the fine-grained "who may do what, how often" has to be rebuilt around it.
- **The contract is the product.** A review is a validated structure (findings, severity, verdict, citations) that the marketplace renders and stores. An MCP tool returns content for a model to read and rephrase, which is exactly where citations stop being checkable.
- **A tool description is another prompt.** Every MCP tool exposes a description an external model reads and acts on; that is new injection surface for no gain in this product.

Inside the service, the agent's tools (#38) are **in-process functions** the loop executes when the model asks for them: no MCP server in between, no network hop, and the permission check in front of them (#43).

## Where MCP and A2A would come in

- **MCP**, for internal use: a team member asking Claude Desktop "¿qué dice la LAU sobre la fianza?" through a thin MCP adapter that calls this same API with its own key. It would be an adapter over the API, never a second implementation.
- **A2A**, as a product: a portal's publishing agent asking this service to review a listing before it goes live, on its own compute and budget. That needs discovery, per-caller quotas and a stronger sandbox, because the caller is another company's model. It is the natural next step once the service has more than one client, and it is out of scope for the delivery.

## Consequences

- One interface to secure, document and test. The OpenAPI schema is the contract for every client.
- Offering MCP or A2A later is an adapter plus its own credentials, with the guards of the API still in front.

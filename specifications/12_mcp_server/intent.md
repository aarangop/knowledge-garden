# 12 — MCP Server

## Problem

The Knowledge Garden's semantic search capability (spec 10) is currently accessible only via the FastAPI REST API or the CLI. An LLM like Claude cannot use it directly while generating a response — it must either be given search results out-of-band or rely on the user to manually copy-paste relevant notes.

The Model Context Protocol (MCP) defines a standard interface that lets LLM clients (Claude Desktop, Claude Code, and compatible tools) call server-defined tools dynamically during a conversation. Adding an MCP server to Knowledge Garden makes the semantic graph a live, callable knowledge source: the LLM invokes `search_notes` itself, reads the results, and grounds its response in actual content from the vaults — a RAG workflow without a separate retrieval pipeline or additional orchestration code.

## Desired behavior

Running `uv run kg-mcp` starts a standalone MCP server that connects to the same Neo4j instance as the FastAPI server and exposes four tools:

1. **`search_notes`** — Embed the query and run a vector similarity search. Returns a JSON array of matching chunks with their note title, vault, content excerpt, heading context, and similarity score.
2. **`get_note`** — Retrieve the full markdown content of a note by title (case-insensitive). Returns the content string or an error message if no note is found.
3. **`list_vaults`** — Return a JSON array of all ingested vault names and their note counts.
4. **`get_graph_stats`** — Return a JSON object with high-level counts: notes, chunks, similarity edges, related-to edges, and vault names.

The MCP server reads configuration exclusively from environment variables (the same `AppSettings` used by the FastAPI server) and can be registered in Claude Desktop's `claude_desktop_config.json` with a single `uv run` entry.

## Open questions

- This spec assumes spec 10 (search API) has been implemented first: `get_note_by_id` and `get_stats` are defined there. Spec 12 reuses those `GraphStore` methods unchanged (no forward declarations, no stubs).
- The `get_note_by_title` method on `GraphStore` is a new addition first introduced in this spec (not in spec 10). It performs a case-insensitive match on `n.title` using Cypher `toLower()`.

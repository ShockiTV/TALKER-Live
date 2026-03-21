## Requirements

### Requirement: Embeddings via Ollama nomic-embed-text

The Python service SHALL compute all embeddings by calling the Ollama `/api/embeddings` endpoint with model `nomic-embed-text` (768 dimensions). The Ollama client SHALL reuse the configured Ollama base URL. If Ollama is unavailable, embedding SHALL fail gracefully with a logged warning and the entity SHALL be stored without an embedding (excluded from vector search results).

#### Scenario: Embedding computed on first ingest
- **WHEN** an Event node with a given `(ts, cs)` does not exist in Neo4j
- **THEN** `embedding_client.embed(text)` is called and the 768d vector stored on the node

#### Scenario: No re-embed on reuse
- **WHEN** an Event node already exists in Neo4j with an `embedding` property
- **THEN** the Ollama API is NOT called; the existing embedding is reused

#### Scenario: Ollama pull on startup
- **WHEN** the Python service starts and Neo4j is available
- **THEN** the service checks if `nomic-embed-text` is present in Ollama and pulls it if absent, before accepting WS connections

### Requirement: Token count stored per node

Every `Event`, `MemoryNode`, `Background`, and `GlobalEvent` node SHALL have a `token_count` integer property estimated as `len(text) // 4` at ingest time.

#### Scenario: Token count present on node
- **WHEN** an Event is ingested with 200-character text
- **THEN** the node has `token_count = 50`

### Requirement: Hybrid context retrieval with token budget

A `retrieval.py` module SHALL be added to the `storage/` layer. It SHALL execute hybrid search (vector similarity + BM25 fulltext), merge results using Reciprocal Rank Fusion (RRF, k=60), and greedily pack results up to a caller-specified token budget, returning chunks in ascending `game_time_ms` order.

#### Scenario: Character-scoped retrieval
- **WHEN** `retrieve_context(session_id, char_id, query_text, budget=4000)` is called
- **THEN** only nodes reachable from `(:Session)-[:SCOPES]->(:Character {game_id: char_id})-[:WITNESSED|HAS_SUMMARY|HAS_DIGEST|HAS_CORE]` are considered

#### Scenario: Global scope includes world events
- **WHEN** the retrieval call requests `scope="global"`
- **THEN** `(:Session)-[:HAS_GLOBAL_EVENT]` nodes are included in the candidate set

#### Scenario: RRF merges two ranked lists
- **WHEN** vector search returns 50 candidates and BM25 returns 20 with overlap
- **THEN** duplicates are merged, scored by `1/(k + rank_v) + 1/(k + rank_b)` with k=60, and sorted by RRF score descending

#### Scenario: Greedy packing respects budget
- **WHEN** top-scored chunks total 5000 tokens and budget is 4000
- **THEN** chunks are added in RRF rank order until adding the next would exceed budget; that chunk is skipped

#### Scenario: Output is chronologically ordered
- **WHEN** packing is complete
- **THEN** the returned list is sorted by `game_time_ms` ascending regardless of RRF score order

#### Scenario: Name-based BM25 via Character fulltext index
- **WHEN** query text contains a character name like `"Lukash"`
- **THEN** the fulltext index on `Character.name` enables events INVOLVING that character to receive boosted BM25 rank

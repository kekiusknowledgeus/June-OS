# Memory

Data lives in `data/june.db`. Memory records contain text, category, normalized deduplication key, explicit/inferred status, source, project, confidence, importance, created/updated timestamps and last-seen timestamp. Identity, preferences, people, projects, goals, tasks, decisions, events, ideas, knowledge, conversations, routines and environment can all be represented as categories.

Explicit `Remember …` requests and dashboard saves have stronger persistence. The agent can propose durable candidates only through the approval-gated memory tool; it cannot set the explicit flag. Ordinary conversation is retained as conversation history, not automatically promoted into personal memory. Exact normalized duplicates merge persistence/confidence metadata. Contradictory or paraphrased memories are not silently merged.

Retrieval uses local TF-IDF, latent semantic analysis and a small concept vocabulary for associations such as wireless/inductive power and humanoid/robotics. Importance and age influence ranking; explicit records do not decay. This provides a lightweight semantic baseline without uploading embeddings. It is less capable than a pretrained semantic model, especially outside the concept vocabulary and on tiny corpora. Replace `EmbeddingProvider.rank()` to improve it independently of the brain. Search considers the 2,000 most recently updated memories; very large libraries need a persistent vector index.

Only six relevant memories and bounded recent messages enter model context. File and tool observations remain untrusted. The working world tracks active task/project and recent observations in memory, while projects, tasks and conversation survive restart. It does not pretend old window observations are current after restart.

The dashboard can create, edit, pin, unpin and forget memories. Records now include tags, people, subject, source history, last access and active/superseded status. Explicit shared subjects link conflicting records without silently choosing truth. Approved merge/resolve operations preserve provenance and revision history. Pinned and explicit memories do not decay; an in-memory bounded ranking cache avoids repeated computation and invalidates when content changes. Broad automatic contradiction detection and a large persistent vector index remain future work.

Forgetting a memory does not erase the original conversation or an audit entry; those are separate local records. Back up the database with SQLite's backup API or while June is stopped, including WAL files if copying a running database.

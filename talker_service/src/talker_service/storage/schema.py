"""Schema/index initialization for Neo4j graph memory."""

from __future__ import annotations

from loguru import logger


SCHEMA_STATEMENTS = [
    """
    CREATE VECTOR INDEX event_embedding_idx IF NOT EXISTS
    FOR (n:Event)
    ON (n.embedding)
    OPTIONS {indexConfig: {'vector.dimensions': 768, 'vector.similarity_function': 'cosine'}}
    """,
    """
    CREATE VECTOR INDEX memory_embedding_idx IF NOT EXISTS
    FOR (n:MemoryNode)
    ON (n.embedding)
    OPTIONS {indexConfig: {'vector.dimensions': 768, 'vector.similarity_function': 'cosine'}}
    """,
    """
    CREATE VECTOR INDEX background_embedding_idx IF NOT EXISTS
    FOR (n:Background)
    ON (n.embedding)
    OPTIONS {indexConfig: {'vector.dimensions': 768, 'vector.similarity_function': 'cosine'}}
    """,
    """
    CREATE VECTOR INDEX global_event_embedding_idx IF NOT EXISTS
    FOR (n:GlobalEvent)
    ON (n.embedding)
    OPTIONS {indexConfig: {'vector.dimensions': 768, 'vector.similarity_function': 'cosine'}}
    """,
    """
    CREATE FULLTEXT INDEX character_name_fulltext IF NOT EXISTS
    FOR (n:Character)
    ON EACH [n.name]
    """,
]


def init_schema(client) -> bool:
    """Initialize required indexes if Neo4j is available."""
    if not client or not client.is_available():
        logger.info("Neo4j unavailable - skipping schema init")
        return False

    for statement in SCHEMA_STATEMENTS:
        client.execute_write(statement)

    logger.info("Neo4j schema initialization complete")
    return True

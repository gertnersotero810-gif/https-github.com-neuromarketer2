import re
from sqlalchemy import text

class ReadOnlySQLError(Exception):
    """Exception raised when a query is not a read-only SELECT statement."""
    pass

def validate_select_only(query: str) -> None:
    # Strip whitespace and make uppercase
    clean_query = query.strip().upper()
    
    # Must start with SELECT
    if not clean_query.startswith("SELECT"):
        raise ReadOnlySQLError(f"Forbidden: Query must start with SELECT. Query: {query[:50]}")
    
    # Check for forbidden keywords anywhere in the query to prevent multi-statement exploits
    forbidden_keywords = {
        "INSERT", "UPDATE", "DELETE", "DROP", "CREATE",
        "ALTER", "TRUNCATE", "GRANT", "REVOKE"
    }
    
    # Tokenize query by word characters to avoid false matches
    words = set(re.findall(r"\b\w+\b", clean_query))
    intersect = forbidden_keywords.intersection(words)
    if intersect:
        raise ReadOnlySQLError(f"Forbidden keywords detected: {', '.join(intersect)}")

async def text_to_sql_tool(question: str, session) -> list[dict]:
    validate_select_only(question)
    
    result = await session.execute(text(question))
    return [dict(row) for row in result.mappings().all()]

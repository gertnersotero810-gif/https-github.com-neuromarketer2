import ast
import uuid
import pandas as pd
from uuid import UUID
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.raw_metric import RawMetric
from app.core.llm_provider import LLMProvider

class ScriptSecurityError(Exception):
    pass

class ScriptGenerationError(Exception):
    pass

# Strict security sandbox allowed globals per ARCHITECTURE.md Section 8
ALLOWED_GLOBALS = {
    "__builtins__": {
        "len": len, "range": range, "str": str, "int": int,
        "float": float, "list": list, "dict": dict,
        "isinstance": isinstance, "enumerate": enumerate,
    },
    "pd": pd,
    "datetime": datetime,
}

def validate_script_ast(script_code: str) -> None:
    """
    Validates Python AST before execution to prevent security exploits.
    """
    try:
        tree = ast.parse(script_code)
    except SyntaxError as e:
        raise ScriptGenerationError(f"Invalid Python syntax: {e}")
        
    for node in ast.walk(tree):
        # 1. Block Import/ImportFrom
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ScriptSecurityError("Imports are not allowed in LLM scripts.")
            
        # 2. Block restricted calls (eval, exec, open, __import__, compile)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec", "open", "__import__", "compile"}:
                    raise ScriptSecurityError(f"Call to '{node.func.id}' is forbidden.")
                    
        # 3. Block restricted names (os, sys, subprocess, httpx, requests, socket)
        if isinstance(node, ast.Name):
            if node.id in {"os", "sys", "subprocess", "httpx", "requests", "socket"}:
                raise ScriptSecurityError(f"Usage of '{node.id}' is forbidden.")

def execute_normalization_script(script_code: str, df: pd.DataFrame) -> pd.DataFrame:
    """
    Executes AST-validated pandas script within a secure sandbox environment.
    """
    # 1. Validate AST first
    validate_script_ast(script_code)
    
    # 2. Prepare sandbox local environment
    local_vars = {"df": df}
    
    try:
        exec(script_code, ALLOWED_GLOBALS, local_vars)
    except Exception as e:
        raise ScriptGenerationError(f"Script execution failed: {e}")
        
    # Retrieve the normalized DataFrame
    df_normalized = local_vars.get("df_normalized") or local_vars.get("df")
    if not isinstance(df_normalized, pd.DataFrame):
        raise ScriptGenerationError("Script did not produce a valid pandas DataFrame.")
        
    return df_normalized

async def generate_normalization_script(
    headers: List[str],
    samples: List[Dict[str, Any]],
    llm: LLMProvider,
    tenant_id: str,
) -> str:
    """
    Stub method for Task 2.2 LLM Script Generation.
    """
    return ""

async def save_normalized_batch(
    df: pd.DataFrame,
    project_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> int:
    """
    Saves a normalized DataFrame into raw_metrics table using PostgreSQL ON CONFLICT upsert.
    """
    if df.empty:
        return 0
        
    rows = df.to_dict(orient="records")
    total_inserted = 0
    
    # Batch size of 1000 rows
    for i in range(0, len(rows), 1000):
        batch = rows[i:i+1000]
        
        # Prepare values for database insertion
        values = []
        for row in batch:
            campaign_id = row.get("campaign_id")
            raw_date = row.get("date")
            metric_date = None
            if raw_date:
                try:
                    metric_date = pd.to_datetime(raw_date).date()
                except Exception:
                    pass
            
            values.append({
                "tenant_id": tenant_id,
                "project_id": project_id,
                "import_batch": uuid.uuid4(),
                "raw_data": row,
                "normalized": row,
                "metric_date": metric_date,
                "campaign_id": str(campaign_id) if campaign_id is not None else None
            })
            
        stmt = pg_insert(RawMetric).values(values)
        
        # ON CONFLICT update on JSONB expression paths
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                "tenant_id", 
                "project_id",
                text("(normalized->>'campaign_id')"),
                text("(normalized->>'date')")
            ],
            set_={
                "normalized": stmt.excluded.normalized,
                "metric_date": stmt.excluded.metric_date,
                "campaign_id": stmt.excluded.campaign_id,
                "import_batch": stmt.excluded.import_batch,
                "raw_data": stmt.excluded.raw_data
            }
        )
        
        await db.execute(stmt)
        total_inserted += len(batch)
        
    return total_inserted

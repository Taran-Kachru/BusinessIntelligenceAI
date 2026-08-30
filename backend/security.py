"""
security.py — Access Control & Audit (Objective 8)

Provides audit log access and user context parsing.
Actual RLS enforcement happens in database.py.

Computed by: DuckDB SQL queries over access_log table
"""

from typing import List
from .models import AccessLogEntry, UserContext
import yaml
import logging

logger = logging.getLogger(__name__)

def get_access_log(db_conn, limit: int = 50) -> List[AccessLogEntry]:
    """Retrieve the recent access audit log."""
    cursor = db_conn.cursor()
    try:
        df = cursor.execute(
            f"SELECT * FROM access_log ORDER BY timestamp DESC LIMIT {limit}"
        ).df()
        
        logs = []
        for _, row in df.iterrows():
            logs.append(AccessLogEntry(
                timestamp=row["timestamp"],
                user_id=row["user_id"],
                resource=row["resource"],
                action=row["action"],
                allowed=bool(row["allowed"]),
                details=row.get("details")
            ))
        return logs
    except Exception as e:
        logger.error(f"Failed to fetch access log: {e}")
        return []
    finally:
        cursor.close()

def parse_user_context(user_id_header: str) -> UserContext:
    """Parse simulated auth header into UserContext using kpi_contract.yaml."""
    # Defaults
    if not user_id_header:
        user_id_header = "CEO"
        
    try:
        with open("kpi_contract.yaml", "r") as f:
            config = yaml.safe_load(f)
            
        personas = config.get("personas", {})
        
        # Exact match or fallback
        if user_id_header in personas:
            p = personas[user_id_header]
            return UserContext(
                user_id=user_id_header,
                role=p.get("role", "regional_manager"),
                name=user_id_header.replace("_", " "),
                allowed_regions=p.get("regions", ["ALL"]),
                can_view_pii=p.get("pii_access", False)
            )
            
        # Fallback to CEO
        return UserContext(
            user_id="CEO",
            role="ceo",
            name="Chief Executive Officer",
            allowed_regions=["ALL"],
            can_view_pii=True
        )
    except Exception as e:
        logger.warning(f"Failed to parse user context, defaulting to CEO: {e}")
        return UserContext(
            user_id="CEO",
            role="ceo",
            name="Chief Executive Officer",
            allowed_regions=["ALL"],
            can_view_pii=True
        )

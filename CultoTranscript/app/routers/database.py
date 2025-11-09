"""
Database Viewer Router
API endpoints for read-only database inspection and export
"""
import csv
import io
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import inspect, MetaData, Table, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.web.auth import require_auth
from app.common.database import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter()

# Sensitive columns to hide from all views
SENSITIVE_COLUMNS = {"password", "password_hash", "api_key", "secret", "token", "secret_key"}

# Maximum rows allowed for export
MAX_EXPORT_ROWS = 1000


def get_table_names(db: Session) -> list[str]:
    """Get list of all table names in the database"""
    inspector = inspect(db.bind)
    return inspector.get_table_names()


def is_sensitive_column(column_name: str) -> bool:
    """Check if a column name is sensitive and should be hidden"""
    return column_name.lower() in SENSITIVE_COLUMNS


@router.get("/tables")
async def list_tables(
    user: str = Depends(require_auth),
    db: Session = Depends(get_db_session)
):
    """
    List all tables in the database with row counts

    Returns:
        JSON with list of tables and their row counts
    """
    try:
        inspector = inspect(db.bind)
        table_names = inspector.get_table_names()

        tables_with_counts = []
        for table_name in sorted(table_names):
            try:
                # Get row count
                result = db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                count = result.scalar()

                tables_with_counts.append({
                    "name": table_name,
                    "count": count
                })
            except SQLAlchemyError as e:
                logger.warning(f"Could not get count for table {table_name}: {e}")
                tables_with_counts.append({
                    "name": table_name,
                    "count": 0
                })

        return {"tables": tables_with_counts}

    except Exception as e:
        logger.error(f"Error listing tables: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/table/{table_name}")
async def get_table_data(
    table_name: str,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    user: str = Depends(require_auth),
    db: Session = Depends(get_db_session)
):
    """
    Get paginated data from a specific table

    Args:
        table_name: Name of the table to query
        page: Page number (1-indexed)
        limit: Number of rows per page (max 100)
        search: Optional search term to filter across all columns
        sort_by: Optional column name to sort by
        sort_order: Sort order (asc or desc)

    Returns:
        JSON with columns, rows, pagination info
    """
    try:
        # Validate table name exists
        table_names = get_table_names(db)
        if table_name not in table_names:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        # Reflect table schema
        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=db.bind)

        # Get columns (filter out sensitive ones)
        columns = []
        visible_columns = []
        for col in table.columns:
            if not is_sensitive_column(col.name):
                columns.append({
                    "name": col.name,
                    "type": str(col.type)
                })
                visible_columns.append(col)

        # Build base query
        query = db.query(table)

        # Apply search filter
        if search:
            search_filters = []
            for col in visible_columns:
                # Only search on string/text columns
                if 'VARCHAR' in str(col.type).upper() or 'TEXT' in str(col.type).upper():
                    search_filters.append(col.ilike(f"%{search}%"))

            if search_filters:
                from sqlalchemy import or_
                query = query.filter(or_(*search_filters))

        # Get total count
        total = query.count()

        # Apply sorting
        if sort_by and sort_by in [col.name for col in visible_columns]:
            sort_col = table.columns[sort_by]
            if sort_order == "desc":
                query = query.order_by(sort_col.desc())
            else:
                query = query.order_by(sort_col.asc())

        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        # Execute query
        results = query.all()

        # Convert results to dictionaries
        rows = []
        for row in results:
            row_dict = {}
            for col in visible_columns:
                value = getattr(row, col.name)
                # Convert datetime to ISO format string
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                # Convert other non-serializable types to string
                elif not isinstance(value, (str, int, float, bool, type(None))):
                    value = str(value)
                row_dict[col.name] = value
            rows.append(row_dict)

        # Calculate pagination info
        total_pages = (total + limit - 1) // limit  # Ceiling division

        return {
            "columns": columns,
            "rows": rows,
            "total": total,
            "page": page,
            "pages": total_pages,
            "limit": limit
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying table {table_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/table/{table_name}/export")
async def export_table_csv(
    table_name: str,
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    user: str = Depends(require_auth),
    db: Session = Depends(get_db_session)
):
    """
    Export table data to CSV file

    Args:
        table_name: Name of the table to export
        search: Optional search filter (same as table endpoint)
        sort_by: Optional sort column
        sort_order: Sort order (asc or desc)

    Returns:
        CSV file download
    """
    try:
        # Validate table name exists
        table_names = get_table_names(db)
        if table_name not in table_names:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        # Reflect table schema
        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=db.bind)

        # Get visible columns
        visible_columns = []
        for col in table.columns:
            if not is_sensitive_column(col.name):
                visible_columns.append(col)

        # Build query
        query = db.query(table)

        # Apply search filter (same logic as get_table_data)
        if search:
            search_filters = []
            for col in visible_columns:
                if 'VARCHAR' in str(col.type).upper() or 'TEXT' in str(col.type).upper():
                    search_filters.append(col.ilike(f"%{search}%"))

            if search_filters:
                from sqlalchemy import or_
                query = query.filter(or_(*search_filters))

        # Apply sorting
        if sort_by and sort_by in [col.name for col in visible_columns]:
            sort_col = table.columns[sort_by]
            if sort_order == "desc":
                query = query.order_by(sort_col.desc())
            else:
                query = query.order_by(sort_col.asc())

        # Limit to MAX_EXPORT_ROWS
        query = query.limit(MAX_EXPORT_ROWS)

        # Execute query
        results = query.all()

        # Generate CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([col.name for col in visible_columns])

        # Write rows
        for row in results:
            csv_row = []
            for col in visible_columns:
                value = getattr(row, col.name)
                # Convert datetime to ISO format
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                # Convert None to empty string
                elif value is None:
                    value = ''
                # Convert other types to string
                elif not isinstance(value, (str, int, float)):
                    value = str(value)
                csv_row.append(value)
            writer.writerow(csv_row)

        # Prepare response
        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={table_name}.csv"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting table {table_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

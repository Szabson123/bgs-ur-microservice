from typing import Any, Dict, List
from sqlalchemy import text
from sqlalchemy.orm import Session
from utils import safe_decode_bytes

def get_phase_traceability_data(db: Session, phase_id: str) -> List[Dict[str, Any]]:
    sql_query = text("""
        SELECT TOP (100)
            bt.[Board],
            bt.[BoardStart],
            bt.[AssemblyFormID],
            bt.[Result],
            bt.[FT],
            bt.[FP],
            pm.[InternalCode]
        FROM (
            SELECT DISTINCT 
                pm.[AssemblyFormID],
                ps.[InternalCode]
            FROM [Eclipse].[dbo].[ProcessesMatrix] AS pm
            INNER JOIN [Eclipse].[dbo].[ProcessesSteps] AS ps
                ON pm.[ProcessStepID] = ps.[ProcessStepID]
            WHERE pm.[PhaseId] = :phase_id
        ) AS pm
        CROSS APPLY (
            SELECT TOP (100) *
            FROM [Eclipse].[dbo].[BoardTraceability] AS b
            WHERE b.[AssemblyFormID] = pm.[AssemblyFormID]
            ORDER BY b.[BoardStart] DESC
        ) AS bt
        ORDER BY bt.[BoardStart] DESC;
    """)

    result = db.execute(sql_query, {"phase_id": phase_id})
    return [dict(row) for row in result.mappings().all()]


def get_measures_for_failed_boards(
    db: Session, msns: List[str]
) -> List[Dict[str, Any]]:
    if not msns:
        return []

    params = {f"m{i}": msn for i, msn in enumerate(msns)}
    values_clause = ", ".join(f"(:m{i})" for i in range(len(msns)))

    sql_query = text(f"""
        SELECT 
            h.[IdParts],
            h.[MSN],
            h.[IdPhase],
            h.[TestDateTime],
            h.[IdRack],
            h.[Result],
            m.[measure]
        FROM [Measure].[dbo].[HeaderDataLog] AS h
        JOIN (
            VALUES {values_clause}
        ) AS failed(MSN)
            ON h.[MSN] = failed.MSN
        JOIN [Measure].[dbo].[MeasureDataLog] AS m 
            ON h.[IDMeasure] = m.[IDMeasure]
        ORDER BY h.[TestDateTime] DESC;
    """)

    result = db.execute(sql_query, params)
    
    clean_records = []
    for row in result.mappings().all():
        row_dict = dict(row)
        for key, value in row_dict.items():
            if isinstance(value, bytes):
                row_dict[key] = safe_decode_bytes(value)
        clean_records.append(row_dict)

    return clean_records



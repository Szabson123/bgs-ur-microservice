from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_eclipse_db, get_postgres_db
from queries.assembly_form_query import get_measures_for_failed_boards, get_phase_traceability_data
from sqlalchemy import text
from datetime import datetime
import time
from pydantic import BaseModel, ConfigDict, Field

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from utils import safe_decode_bytes


router = APIRouter(prefix="/ur", tags=["UR Analytics"])

class FailRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Test: Optional[str] = None
    IdParts: Optional[int] = None
    MSN: Optional[str] = None
    IdPhase: Optional[int] = None
    TestDateTime: Optional[datetime] = None
    IdRack: Any = None
    Result: Optional[int] = None
    Item: Optional[str] = None


class AllFailsResponse(BaseModel):
    available_parts_ids: List[int]
    total_count: int
    records: List[FailRecord]


def clean_row_data(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in row_dict.items():
        if isinstance(value, bytes):
            row_dict[key] = safe_decode_bytes(value)
    return row_dict


@router.get("/v2/get_all_fails/", response_model=AllFailsResponse)
def get_all_fails(
    phase_id: Any = Query(6204215, description="Identyfikator fazy (IdPhase)"),
    parts_id: Optional[int] = Query(None, description="Opcjonalny filtr IdParts"),
    start_date: datetime = Query(datetime(2026, 8, 24, 0, 0, 0)),
    end_date: datetime = Query(datetime(2026, 9, 24, 0, 0, 0)),
    limit: int = Query(100000, le=100000),
    db: Session = Depends(get_eclipse_db),
):
    parts_filter = ""
    params: Dict[str, Any] = {
        "start_date": start_date,
        "end_date": end_date,
        "phase_id": phase_id,
    }

    if parts_id is not None:
        parts_filter = "AND [IdParts] = :parts_id"
        params["parts_id"] = parts_id

    sql_query = text(f"""
        SELECT TOP ({int(limit)})
               h.[Test],
               h.[IdParts],
               h.[MSN],
               h.[IdPhase],
               h.[TestDateTime],
               h.[IdRack],
               h.[Result],
               m.[Item]
        FROM (
            SELECT TOP ({int(limit)})
                   [IDMeasure],
                   [Test],
                   [IdParts],
                   [MSN],
                   [IdPhase],
                   [TestDateTime],
                   [IdRack],
                   [Result]
            FROM [Measure].[dbo].[HeaderDataLog] WITH (NOLOCK, INDEX([IDX_TestDateTime_IdPhase_Result]))
            WHERE [TestDateTime] >= :start_date
              AND [TestDateTime] < :end_date
              AND [IdPhase] = :phase_id
              AND [Result] != 1
              {parts_filter}
        ) AS h
        JOIN [Measure].[dbo].[MeasureDataLog] AS m WITH (NOLOCK)
          ON h.[IDMeasure] = m.[IDMeasure];
    """)

    result = db.execute(sql_query, params)
    
    raw_rows = [clean_row_data(dict(r)) for r in result.mappings().all()]

    available_parts_ids = sorted(
        {r["IdParts"] for r in raw_rows if r.get("IdParts") is not None}
    )

    return {
        "available_parts_ids": available_parts_ids,
        "total_count": len(raw_rows),
        "records": raw_rows,
    }


def calculate_phase_fpy(
    db: Session,
    phase_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> float:
    
    date_filter = ""
    params: Dict[str, Any] = {"phase_id": phase_id}

    if start_date:
        date_filter += " AND b.[BoardStart] >= :start_date"
        params["start_date"] = start_date
    if end_date:
        date_filter += " AND b.[BoardStart] < :end_date"
        params["end_date"] = end_date

    sql_query = text(f"""
        WITH PhaseForms AS (
            SELECT DISTINCT pm.[AssemblyFormID]
            FROM [Eclipse].[dbo].[ProcessesMatrix] AS pm
            WHERE pm.[PhaseId] = :phase_id
        )
        SELECT 
            SUM(CASE WHEN b.[FT] = 1 THEN 1 ELSE 0 END) AS total_first_tests,
            SUM(CASE WHEN b.[FT] = 1 AND b.[FP] = 1 THEN 1 ELSE 0 END) AS total_first_passes
        FROM [Eclipse].[dbo].[BoardTraceability] AS b
        INNER JOIN PhaseForms AS pf 
            ON b.[AssemblyFormID] = pf.[AssemblyFormID]
        WHERE 1 = 1 {date_filter};
    """)

    row = db.execute(sql_query, params).mappings().first()
    if not row:
        return 0.0

    total_first_tests = row["total_first_tests"] or 0
    total_first_passes = row["total_first_passes"] or 0

    if total_first_tests == 0:
        return 0.0

    return round((total_first_passes / total_first_tests) * 100.0, 2)


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
    return [clean_row_data(dict(row)) for row in result.mappings().all()]


@router.get("/v2/get_all_ur_breakdown_info/{phase_id}")
def get_all_ur_breakdown_info(
    phase_id: str,
    start_date: Optional[datetime] = Query(None, description="Data startu do wyliczenia FPY"),
    end_date: Optional[datetime] = Query(None, description="Data końca do wyliczenia FPY"),
    db: Session = Depends(get_eclipse_db),
):
    last_100 = get_phase_traceability_data(db, phase_id)

    if not last_100:
        raise HTTPException(
            status_code=404, detail="Brak danych dla podanego phase_id"
        )

    current_internal_code = last_100[0]["InternalCode"]

    fpy = calculate_phase_fpy(
        db=db,
        phase_id=phase_id,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "current_internal_code": current_internal_code,
        "fpy": fpy,
        "last_35_test": last_100[:35],
        "total_fetched": len(last_100),
    }


class MachineKPISchema(BaseModel):
    machine_id: int
    machine_name: str
    phase_id: Optional[str] = Field(None, description="Identyfikator fazy maszyny")
    alias: Optional[str] = Field(None, description="Alias maszyny")
    sigip_num: Optional[str] = Field(None, description="Numer SIGIP")
    total_failures: int
    resolved_failures: int
    mttr_hours: float = Field(..., description="Średni czas trwania naprawy w godzinach")
    mtbf_hours: float = Field(..., description="Średni czas między awariami w godzinach")
    mttr_interval: Optional[str] = Field(None, description="Format interwału czasu trwania naprawy")
    mtbf_interval: Optional[str] = Field(None, description="Format interwału bezawaryjnej pracy")


# --- Zapytanie SQL z parametrami bazodanowymi ---
KPI_SQL = text("""
WITH params AS (
    SELECT 
        CAST(:machine_id AS bigint) AS target_machine_id,
        CAST(:range_start AS timestamptz) AS range_start,
        CAST(:range_end AS timestamptz) AS range_end
),
breakdown_durations AS (
    SELECT 
        b.id AS breakdown_id,
        b.created_at AS reported_at,
        MIN(bm.created_at) FILTER (WHERE bm.status = 'ED') AS ended_at,
        EXTRACT(EPOCH FROM (
            MIN(bm.created_at) FILTER (WHERE bm.status = 'ED') - b.created_at
        )) AS repair_duration_seconds
    FROM public.ur_breakdown b
    CROSS JOIN params p
    LEFT JOIN public.ur_breakdownmove bm ON bm.breakdown_id = b.id
    WHERE b.machine_id = p.target_machine_id
      AND b.created_at >= p.range_start 
      AND b.created_at <= p.range_end
    GROUP BY b.id, b.created_at
),
aggregated AS (
    SELECT 
        m.id AS machine_id,
        m.name AS machine_name,
        m.phase_id AS phase_id,
        m.alias AS alias,
        m.sigip_num AS sigip_num,
        EXTRACT(EPOCH FROM (p.range_end - p.range_start)) AS total_period_seconds,
        COUNT(bd.breakdown_id) AS total_failures,
        COUNT(bd.repair_duration_seconds) AS resolved_failures,
        COALESCE(SUM(bd.repair_duration_seconds), 0) AS total_downtime_seconds
    FROM public.ur_machine m
    CROSS JOIN params p
    LEFT JOIN breakdown_durations bd ON TRUE
    WHERE m.id = p.target_machine_id
    GROUP BY m.id, m.name, m.phase_id, m.alias, m.sigip_num, p.range_start, p.range_end
)
SELECT 
    machine_id,
    machine_name,
    phase_id,
    alias,
    sigip_num,
    total_failures,
    resolved_failures,
    CAST(
        ROUND(
            CAST(
                CASE 
                    WHEN resolved_failures > 0 
                    THEN (total_downtime_seconds / resolved_failures / 3600.0)
                    ELSE 0 
                END AS numeric
            ), 2
        ) AS double precision
    ) AS mttr_hours,
    CAST(
        ROUND(
            CAST(
                CASE 
                    WHEN total_failures > 0 
                    THEN ((total_period_seconds - total_downtime_seconds) / total_failures / 3600.0)
                    ELSE (total_period_seconds / 3600.0)
                END AS numeric
            ), 2
        ) AS double precision
    ) AS mtbf_hours,
    CASE 
        WHEN resolved_failures > 0 
        THEN CAST(CAST((total_downtime_seconds / resolved_failures || ' seconds') AS interval) AS text)
        ELSE '00:00:00'
    END AS mttr_interval,
    CASE 
        WHEN total_failures > 0 
        THEN CAST(CAST((((total_period_seconds - total_downtime_seconds) / total_failures) || ' seconds') AS interval) AS text)
        ELSE CAST(CAST((total_period_seconds || ' seconds') AS interval) AS text)
    END AS mtbf_interval
FROM aggregated;
""")


# --- Endpoint ---
@router.get("/{machine_id}/kpi", response_model=MachineKPISchema)
def get_machine_kpi(
    machine_id: int,
    date_from: datetime = Query(..., description="Początek zakresu np. 2026-01-01T00:00:00Z"),
    date_to: datetime = Query(..., description="Koniec zakresu np. 2026-03-31T23:59:59Z"),
    db: Session = Depends(get_postgres_db)
):
    if date_from >= date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parametr 'date_from' musi być wcześniejszy niż 'date_to'."
        )

    result = db.execute(
        KPI_SQL,
        {
            "machine_id": machine_id,
            "range_start": date_from,
            "range_end": date_to
        }
    ).mappings().first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maszyna o ID {machine_id} nie została znaleziona."
        )

    return result
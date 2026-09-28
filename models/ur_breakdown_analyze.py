from sqlalchemy import table, column, select

board_trace = table(
    "BoardTraceability",
    column("Board"),
    column("BoardStart"),
    column("AssemblyFormID"),
    column("Result"),
    column("FT"),
    column("FP"),
    schema="Eclipse.dbo"
)

process_matrix = table(
    "ProcessesMatrix",
    column("ProcessStepID"),
    column("PhaseID"),
    column("AssemblyFormID"),
    schema="Eclipse.dbo"
)

process_internal_code = table(
    "ProcessesSteps",
    column("InternalCode"),
    column("ProcessStepID"),
    schema="Eclipse.dbo"
)

goldens_data = table(
    "goldensample_mastersample",
    column("sn"),
    column("date_crated"),
    column("expire_date"),
    schema="public"
)
from v2.contracts import ExecutionPlan, RequestFilter
from v2.execute.validator import validate_execution_plan
from v2.ingest.parser import ingest_query
from v2.plan.compiler import compile_execution_plan
from v2.reason.core import reason_about_query


def test_v2_ingest_contract():
    result = ingest_query("thong tin account Demo Account 8")
    assert result.normalized_query
    assert isinstance(result.entities, list)
    assert isinstance(result.request_filters, list)


def test_v2_plan_compile():
    ingest = ingest_query("thong tin account Demo Account 8")
    reason = reason_about_query(ingest)
    plan = compile_execution_plan(ingest, reason)
    assert plan.root_table
    assert plan.limit > 0


def test_v2_validator_rejects_unknown_table():
    plan = ExecutionPlan(
        root_table="table_not_exists",
        where_filters=[RequestFilter(field="table_not_exists.name", op="eq", value="x")],
        limit=10,
    )
    result = validate_execution_plan(plan)
    assert not result.ok

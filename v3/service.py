from __future__ import annotations
import time
import re
from dataclasses import asdict

from v2.memory import get_session_context, update_session_context
from v2.execute import execute_plan
from v2.plan import compile_execution_plan
from v2.contracts import ExecutionPlan, IngestResult, RequestFilter
from v2.learn.trainset import append_trainset_sample
from v3.agent.context_resolver import ContextResolver
from v3.agent.semantic_reasoner import SemanticReasoner
from v3.agent.lean_router import LeanRouter
from v3.agent.response_architect import ResponseArchitect

class V3Service:
    def __init__(self):
        self.context_resolver = ContextResolver()
        self.reasoner = SemanticReasoner()
        self.lean_router = LeanRouter()
        self.architect = ResponseArchitect()

    def run_pipeline(self, query: str, session_id: str = None, role: str = "DEFAULT") -> dict:
        start_time = time.time()
        is_lean = False
        is_correction = False
        
        if not session_id:
            session_id = f"v3-{int(start_time)}"
        
        # 0. Regex Fast Path (Zero Latency for basic queries)
        q_clean = query.lower().strip()
        # Pattern for "danh sách [table]" or "tháng [X]"
        list_match = re.search(r"(danh sách|tất cả|liệt kê|tháng|trong tháng)\s+([\d/]+)?\s*(account|khách hàng|user|sales|hợp đồng|cơ hội|contact|opps|opp)", q_clean)
        if list_match:
            from v2.metadata import MetadataProvider
            provider = MetadataProvider()
            table_alias = list_match.group(3)
            table_name = provider.get_table_by_alias(table_alias) or "hbl_account"
            is_lean = True
            
            # Simple date detection for month
            month_match = re.search(r"tháng (\d+)", q_clean)
            where_filters = []
            if month_match:
                month = int(month_match.group(1))
                year = 2026 if "2026" in q_clean else 2025
                where_filters.append({"field": f"{table_name}.createdon", "op": "range", "value": [f"{year}-{month:02d}-01", f"{year}-{month:02d}-31"]})

            reasoning_result = {
                "intent": "retrieve",
                "primary_entity": table_name,
                "entities": [table_name],
                "thought_process": "Fast Path: Regex matching for list/time query.",
                "suggested_response": f"Dạ, đây là danh sách {table_alias} trong {month_match.group(0) if month_match else 'hệ thống'} mà bạn yêu cầu:"
            }
            # Execute directly using V2 execution logic
            plan = ExecutionPlan(root_table=table_name, join_path=[], where_filters=where_filters, limit=100)
            data = execute_plan(plan)
            latency = time.time() - start_time
            
            # Fill count
            assistant_response = reasoning_result["suggested_response"].replace("[số lượng]", str(len(data)))
            
            return {
                "ok": True, "is_lean": True, "resolved_query": query, "context_result": {"query": query},
                "reasoning": reasoning_result, "execution_result": data,
                "assistant_response": assistant_response, "latency_ms": int(latency * 1000)
            }
        
        # 1. Fast Path: Lean Routing
        lean_match = self.lean_router.match(query)
        if lean_match:
            is_lean = True
            resolved_query = query
            reasoning_result = lean_match
            # Convert sample filters to RequestFilter objects
            filters = [RequestFilter(**f) if isinstance(f, dict) else f for f in lean_match.get("filters", [])]
            ingest = IngestResult(raw_query=query, normalized_query=query, intent=lean_match.get("intent"), entities=lean_match.get("entities"), request_filters=filters)
            plan = compile_execution_plan(ingest, lean_match)
        else:
            # 2. Context Resolution
            history = get_session_context(session_id)
            context_result = self.context_resolver.resolve(query, history)
            resolved_query = context_result["query"]
            is_correction = context_result.get("is_correction", False)

            # 3. Semantic Reasoning
            reasoning_result = self.reasoner.reason(resolved_query)
            
            # 4. Planning & Execution
            # Convert filters to RequestFilter for compile_execution_plan
            raw_filters = reasoning_result.get("filters", [])
            filters = []
            for f in raw_filters:
                if isinstance(f, dict):
                    filters.append(RequestFilter(field=f.get("field"), op=f.get("op"), value=f.get("value")))
            
            ingest = IngestResult(
                raw_query=query,
                normalized_query=resolved_query,
                intent=reasoning_result.get("intent", "retrieve"),
                entities=reasoning_result.get("entities", []),
                request_filters=filters
            )
            plan = compile_execution_plan(ingest, reasoning_result)

        # 5. Execution
        data = execute_plan(plan)
        
        # 6. Learning Step
        if not is_lean and data:
            sample = {
                "query": query,
                "normalized_query": resolved_query.lower(),
                "query_template": self.lean_router._gen_template(resolved_query),
                "intent": reasoning_result.get("intent"),
                "primary_entity": reasoning_result.get("primary_entity"),
                "entities": reasoning_result.get("entities"),
                "filters": [f.__dict__ if hasattr(f, "__dict__") else f for f in ingest.request_filters],
                "success_label": True,
                "source": "v3_auto_learn"
            }
            append_trainset_sample(sample)

        # 7. Final Response
        assistant_response = reasoning_result.get("suggested_response")
        
        # Smart Data Summary
        if data and len(data) == 1:
            record = data[0]
            summary_parts = []
            from v2.metadata import MetadataProvider
            provider = MetadataProvider()
            root_table = reasoning_result.get("primary_entity")
            if root_table:
                priority_fields = provider.get_identity_priority_fields(root_table)
                for field in priority_fields:
                    if field in record and record[field] is not None:
                        label = field.replace(f"{root_table}_", "").replace("_", " ").title()
                        summary_parts.append(f"- **{label}**: {record[field]}")
                if summary_parts:
                    assistant_response = f"{assistant_response or 'Dạ, đây là thông tin chi tiết:'}\n\n" + "\n".join(summary_parts)

        if assistant_response:
            count = len(data) if data else 0
            assistant_response = assistant_response.replace("[số lượng]", str(count))
            assistant_response = assistant_response.replace("[count]", str(count))

        if not assistant_response:
            if not data:
                assistant_response = "Dạ, tôi đã kiểm tra nhưng chưa thấy dữ liệu phù hợp."
            else:
                assistant_response = f"Dạ, tôi đã tìm thấy {len(data)} kết quả cho bạn."

        latency = time.time() - start_time
        return {
            "ok": True,
            "is_lean": is_lean,
            "resolved_query": resolved_query,
            "reasoning": reasoning_result,
            "execution_result": data,
            "assistant_response": assistant_response,
            "latency_ms": int(latency * 1000)
        }

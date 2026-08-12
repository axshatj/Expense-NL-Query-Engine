"""
Unified Query Pipeline: Orchestrates Stage 1 (IR generation), Stage 2 (DB execution), and Stage 3 (Grounded Answer).
"""
import time
import logging
from datetime import date
from typing import Dict, Any, Optional
from src.query_engine.ir_generator import generate_ir
from src.query_engine.db_executor import execute_ir
from src.query_engine.grounded_answer import generate_grounded_answer

logger = logging.getLogger(__name__)



class QueryPipeline:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def run(
        self,
        question: str,
        ref_date: Optional[date] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes an end-to-end natural language question against the transaction database.
        Returns execution telemetry including JSON IR, SQL query, DB result, grounded answer, and latency.
        """
        logger.info(f"Query Pipeline execution started for question: '{question}'")
        start_time = time.perf_counter()
        
        if ref_date is None:
            ref_date = date(2026, 8, 11)

        # Stage 1: NL -> IR
        ir = generate_ir(question, ref_date=ref_date, api_key=api_key)
        logger.info(f"Stage 1 Complete: Generated IR (intent: '{ir.intent}', metric: '{ir.metric}')")

        # Stage 2: IR -> DB execution
        db_result = execute_ir(ir, db_path=self.db_path)
        sql_info = db_result.get("query_sql") or db_result.get("primary_period", {}).get("sql", "N/A")
        logger.info(f"Stage 2 Complete: Executed parameterized query against DB. SQL: '{sql_info}'")

        # Stage 3: DB result -> Grounded answer
        grounded_res = generate_grounded_answer(question, db_result, api_key=api_key)
        logger.info(
            f"Stage 3 Complete: Grounded answer generated. is_grounded: {grounded_res['is_grounded']}, "
            f"fallback_used: {grounded_res['fallback_used']}"
        )

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(f"Query Pipeline finished successfully in {elapsed_ms}ms. Response: '{grounded_res['answer']}'")

        return {
            "question": question,
            "ref_date": ref_date.isoformat(),
            "answer": grounded_res["answer"],
            "is_grounded": grounded_res["is_grounded"],
            "fallback_used": grounded_res["fallback_used"],
            "ir": ir.model_dump(),
            "db_result": db_result,
            "latency_ms": elapsed_ms
        }


def answer_question(
    question: str,
    ref_date: Optional[date] = None,
    api_key: Optional[str] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Helper function to run a single question through the pipeline."""
    pipeline = QueryPipeline(db_path=db_path)
    return pipeline.run(question, ref_date=ref_date, api_key=api_key)

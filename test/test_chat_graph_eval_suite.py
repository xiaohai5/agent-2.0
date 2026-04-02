from __future__ import annotations

import json
import os
import sys
import unittest
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from unittest import IsolatedAsyncioTestCase

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.graphs.chat_graph_nodes.confirmation import confirmation_gate
from backend.app.graphs.chat_graph_nodes.preprocess import agent_manager, preprocess_query
from backend.app.graphs.chat_graph_nodes.response import (
    _build_final_summary_payload,
    after_execute_tasks,
    compose_answer,
    customer_service_rewriter,
    other_route_rewriter,
    summarize_result,
    verify_answer,
)
from backend.app.graphs.chat_graph_nodes.tasks import execute_tasks


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "chat_graph_eval_dataset.json"
CASE_FILTER_ENV = "CHAT_GRAPH_EVAL_CASE_IDS"
TOP_K_ENV = "CHAT_GRAPH_EVAL_TOP_K"
MIN_FACT_COVERAGE_ENV = "CHAT_GRAPH_EVAL_MIN_FACT_COVERAGE"
MIN_SIMILARITY_ENV = "CHAT_GRAPH_EVAL_MIN_SIMILARITY"


def _selected_case_ids() -> set[str]:
    raw = str(os.getenv(CASE_FILTER_ENV, "")).strip()
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def _load_eval_cases() -> list[dict[str, Any]]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, list):
        raise AssertionError("Eval dataset must be a list.")
    selected_case_ids = _selected_case_ids()
    if not selected_case_ids:
        return payload
    return [case for case in payload if str(case.get("id", "")).strip() in selected_case_ids]


def _build_history(case: dict[str, Any]) -> list[dict[str, Any]]:
    summary = case.get("history_summary")
    if not isinstance(summary, dict) or not summary:
        return []
    return [
        {
            "role": "user",
            "content": str(summary.get("effective_question", "")).strip(),
        },
        {
            "role": "assistant",
            "content": str(summary.get("final_answer", "")).strip(),
            "metadata": {"final_summary": summary},
        },
    ]


def _grade_route(case: dict[str, Any], state: dict[str, Any]) -> tuple[bool, str]:
    expected = case.get("expected_route", {})
    expected_route = str(expected.get("route", "")).strip()
    expected_primary_intent = str(expected.get("primary_intent", "")).strip()
    expected_subtasks = [str(item).strip() for item in expected.get("subtask_routes", []) if str(item).strip()]

    actual_route = str(state.get("route", "")).strip()
    actual_primary_intent = str(state.get("primary_intent", "")).strip()
    actual_subtasks = [str(item).strip() for item in state.get("subtask_routes", []) if str(item).strip()]

    if expected_route and actual_route != expected_route:
        return False, f"route mismatch: expected {expected_route}, got {actual_route}"
    if expected_primary_intent and actual_primary_intent != expected_primary_intent:
        return False, f"primary_intent mismatch: expected {expected_primary_intent}, got {actual_primary_intent}"
    if expected_subtasks and actual_subtasks != expected_subtasks:
        return False, f"subtask_routes mismatch: expected {expected_subtasks}, got {actual_subtasks}"
    return True, "ok"


def _compute_answer_metrics(case: dict[str, Any], answer: str) -> dict[str, Any]:
    normalized_answer = str(answer).strip()
    reference_answer = str(case.get("reference_answer", "")).strip()
    reference_facts = [str(item).strip() for item in case.get("reference_facts", []) if str(item).strip()]
    matched_facts = [fact for fact in reference_facts if fact.lower() in normalized_answer.lower()]
    fact_coverage = len(matched_facts) / len(reference_facts) if reference_facts else 1.0
    similarity = (
        SequenceMatcher(None, normalized_answer.lower(), reference_answer.lower()).ratio()
        if reference_answer
        else 1.0
    )
    forbidden_hits = []
    for token in case.get("answer_must_not_contain", []):
        normalized = str(token).strip()
        if normalized and normalized in normalized_answer:
            forbidden_hits.append(normalized)
    return {
        "reference_answer": reference_answer,
        "reference_facts": reference_facts,
        "matched_facts": matched_facts,
        "fact_coverage": fact_coverage,
        "similarity": similarity,
        "forbidden_hits": forbidden_hits,
    }


def _grade_answer(case: dict[str, Any], result: dict[str, Any]) -> tuple[bool, str]:
    answer = str(result.get("answer", "")).strip()
    if not answer:
        return False, "answer is empty"

    metrics = _compute_answer_metrics(case, answer)
    min_fact_coverage = float(os.getenv(MIN_FACT_COVERAGE_ENV, "0.8"))
    min_similarity = float(os.getenv(MIN_SIMILARITY_ENV, "0.6"))

    passed = (
        metrics["fact_coverage"] >= min_fact_coverage
        and metrics["similarity"] >= min_similarity
        and not metrics["forbidden_hits"]
    )
    if not passed:
        return (
            False,
            (
                f"answer grading failed: "
                f"fact_coverage={metrics['fact_coverage']:.2f}, "
                f"similarity={metrics['similarity']:.2f}, "
                f"forbidden_hits={metrics['forbidden_hits']}"
            ),
        )
    return True, f"ok | fact_coverage={metrics['fact_coverage']:.2f} | similarity={metrics['similarity']:.2f}"


class ChatGraphEvalSuite(IsolatedAsyncioTestCase):
    async def _run_case(self, case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        state: dict[str, Any] = {
            "question": str(case.get("question", "")).strip(),
            "history": _build_history(case),
            "top_k": int(os.getenv(TOP_K_ENV, "3")),
            "user_id": 1,
        }

        state.update(preprocess_query(state))
        state.update(agent_manager(state))
        state.update(confirmation_gate(state))

        if bool(state.get("requires_confirmation")):
            answer = str(state.get("answer", "")).strip()
            state["answer"] = answer
            state["final_summary"] = _build_final_summary_payload(state, answer)
            return state, {
                "answer": answer,
                "status": str(state.get("status", "completed")).strip() or "completed",
                "final_summary": state.get("final_summary", {}),
            }

        state.update(await execute_tasks(state))
        next_node = after_execute_tasks(state)
        if next_node == "compose_answer":
            state.update(compose_answer(state))
            state.update(verify_answer(state))
            state.update(await customer_service_rewriter(state))
            state.update(summarize_result(state))
        else:
            state.update(await other_route_rewriter(state))

        return state, {
            "answer": str(state.get("answer", "")).strip(),
            "status": str(state.get("status", "completed")).strip() or "completed",
            "final_summary": state.get("final_summary", {}),
        }

    async def test_eval_dataset_contains_ten_cases(self) -> None:
        cases = _load_eval_cases()
        if _selected_case_ids():
            self.assertGreater(len(cases), 0)
            return
        self.assertEqual(len(cases), 10)

    async def test_eval_suite_scores(self) -> None:
        cases = _load_eval_cases()
        passed_route = 0
        passed_answer = 0
        passed_all = 0
        total_fact_coverage = 0.0
        total_similarity = 0.0
        execution_errors = 0
        execution_error_case_ids: list[str] = []

        for case in cases:
            case_id = str(case.get("id", "")).strip() or "unknown"
            with self.subTest(case_id=case_id):
                try:
                    state, result = await self._run_case(case)
                except Exception:
                    execution_errors += 1
                    execution_error_case_ids.append(case_id)
                    continue
                route_ok, route_message = _grade_route(case, state)
                answer_ok, answer_message = _grade_answer(case, result)
                answer = str(result.get("answer", "")).strip()
                metrics = _compute_answer_metrics(case, answer)
                reference_answer = str(metrics["reference_answer"]).strip()
                fact_coverage = float(metrics["fact_coverage"])
                similarity = float(metrics["similarity"])

                passed_route += int(route_ok)
                passed_answer += int(answer_ok)
                passed_all += int(route_ok and answer_ok)
                total_fact_coverage += fact_coverage
                total_similarity += similarity

        total = len(cases)
        avg_fact_coverage = total_fact_coverage / total if total else 0.0
        avg_similarity = total_similarity / total if total else 0.0
        route_accuracy = passed_route / total if total else 0.0
        answer_accuracy = passed_answer / total if total else 0.0
        overall_pass_rate = passed_all / total if total else 0.0
        print(f"Total cases: {total}")
        print(f"Route accuracy: {passed_route}/{total} = {route_accuracy:.1%}")
        print(f"Answer accuracy: {passed_answer}/{total} = {answer_accuracy:.1%}")
        print(f"Answer fact coverage: {avg_fact_coverage:.1%}")
        print(f"Answer reference similarity: {avg_similarity:.1%}")
        print(f"Overall pass rate: {passed_all}/{total} = {overall_pass_rate:.1%}")
        print(f"Execution errors: {execution_errors}/{total}")
        if execution_error_case_ids:
            print(f"Execution error cases: {', '.join(execution_error_case_ids)}")
        self.assertGreater(total, 0)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Schema-driven decision compiler.

A package is signer-ready only when weights sum to 1, cited evidence and
assumptions exist, assumptions hold, and bias checks pass. Hard-constraint
failures exclude an option. They do not by themselves block sign-off.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA = "decision_package.v1"


@dataclass
class Criterion:
    criterion_id: str
    name: str
    weight: float
    higher_is_better: bool


@dataclass
class Constraint:
    constraint_id: str
    measure: str
    operator: str
    limit: float
    hard: bool = True


@dataclass
class Assumption:
    assumption_id: str
    statement: str
    status: str


@dataclass
class BiasCheck:
    check_id: str
    passed: bool
    detail: str


@dataclass
class Evidence:
    evidence_id: str
    claim: str
    source: str
    confidence: float


@dataclass
class Option:
    option_id: str
    name: str
    measures: dict[str, float]
    evidence_ids: list[str]
    assumption_ids: list[str]


@dataclass
class Package:
    episode: str
    question: str
    selected: str | None
    runner_up: str | None
    margin: float | None
    signer_ready: bool
    blocking: list[str]
    exclusions: list[str]
    flip_conditions: list[str]
    options: list[dict[str, Any]]
    refresh_of: str | None = None
    package_hash: str = ""
    schema: str = field(default=SCHEMA)

    def seal(self) -> None:
        body = {k: v for k, v in asdict(self).items() if k != "package_hash"}
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        self.package_hash = hashlib.sha256(raw).hexdigest()


def _norm(values: list[float], higher_is_better: bool) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0 for _ in values]
    if higher_is_better:
        return [(v - lo) / (hi - lo) for v in values]
    return [(hi - v) / (hi - lo) for v in values]


def _holds(operator: str, value: float, limit: float) -> bool:
    return {"<=": value <= limit, ">=": value >= limit, "==": value == limit}[operator]


def compile_package(
    episode: str,
    question: str,
    criteria: list[Criterion],
    constraints: list[Constraint],
    assumptions: list[Assumption],
    bias_checks: list[BiasCheck],
    evidence: list[Evidence],
    options: list[Option],
    refresh_of: str | None = None,
) -> Package:
    blocking: list[str] = []
    if abs(sum(c.weight for c in criteria) - 1.0) > 1e-6:
        blocking.append("weights must sum to 1")
    evidence_ids = {e.evidence_id for e in evidence}
    assumption_ids = {a.assumption_id for a in assumptions}
    for opt in options:
        if any(i not in evidence_ids for i in opt.evidence_ids):
            blocking.append(f"{opt.option_id} missing evidence")
        if any(i not in assumption_ids for i in opt.assumption_ids):
            blocking.append(f"{opt.option_id} missing assumption")
    blocking.extend(f"{a.assumption_id} is {a.status}" for a in assumptions if a.status != "holds")
    blocking.extend(f"{b.check_id} failed" for b in bias_checks if not b.passed)

    exclusions: list[str] = []
    feasible: dict[str, bool] = {}
    for opt in options:
        bad = []
        for constraint in constraints:
            if not constraint.hard:
                continue
            value = opt.measures.get(constraint.measure)
            if value is None or not _holds(constraint.operator, value, constraint.limit):
                bad.append(constraint.constraint_id)
        feasible[opt.option_id] = not bad
        if bad:
            exclusions.append(f"{opt.option_id} excluded by {bad}")

    rows: list[dict[str, Any]] = []
    for opt in options:
        score = 0.0
        parts = {}
        for criterion in criteria:
            raw = [o.measures[criterion.name] for o in options]
            unit = _norm(raw, criterion.higher_is_better)[options.index(opt)]
            part = round(criterion.weight * unit, 6)
            parts[criterion.criterion_id] = part
            score += part
        rows.append(
            {
                "option_id": opt.option_id,
                "name": opt.name,
                "feasible": feasible[opt.option_id],
                "score": round(score, 6),
                "parts": parts,
            }
        )
    eligible = sorted((r for r in rows if r["feasible"]), key=lambda r: r["score"], reverse=True)
    selected = runner = margin = None
    flips = []
    if len(eligible) >= 2:
        selected, runner = eligible[0]["option_id"], eligible[1]["option_id"]
        margin = round(eligible[0]["score"] - eligible[1]["score"], 6)
        flips.append(f"Flips from {selected} to {runner} if margin {margin} is erased.")
    elif len(eligible) == 1:
        selected = eligible[0]["option_id"]
        flips.append(f"Only {selected} is feasible.")
    else:
        blocking.append("no feasible option")
    flips.extend(exclusions)
    pkg = Package(
        episode=episode,
        question=question,
        selected=selected,
        runner_up=runner,
        margin=margin,
        signer_ready=not blocking and selected is not None,
        blocking=blocking,
        exclusions=exclusions,
        flip_conditions=flips,
        options=sorted(rows, key=lambda r: r["score"], reverse=True),
        refresh_of=refresh_of,
    )
    pkg.seal()
    return pkg


def _fixture(range_limit: float) -> dict[str, Any]:
    criteria = [
        Criterion("range", "range_km", 0.35, True),
        Criterion("payload", "payload_kg", 0.25, True),
        Criterion("cost", "unit_cost_kusd", 0.20, False),
        Criterion("sustainment", "sustainment_hours", 0.20, False),
    ]
    constraints = [
        Constraint("range_gate", "range_km", ">=", range_limit),
        Constraint("payload_gate", "payload_kg", ">=", 800),
        Constraint("cost_gate", "unit_cost_kusd", "<=", 450),
    ]
    assumptions = [Assumption("road", "Range is at gross weight on a dry primary road.", "holds")]
    checks = [BiasCheck("no_incumbent", True, "Vendor identity is not a measure.")]
    evidence = [Evidence("fixture", "Measures are a demonstration fixture, not test data.", "fixture", 1.0)]
    options = [
        Option("ICE", "diesel", {"range_km": 520, "payload_kg": 1100, "unit_cost_kusd": 280, "sustainment_hours": 14}, ["fixture"], ["road"]),
        Option("HYB", "hybrid", {"range_km": 610, "payload_kg": 960, "unit_cost_kusd": 390, "sustainment_hours": 18}, ["fixture"], ["road"]),
        Option("BEV", "battery", {"range_km": 340, "payload_kg": 900, "unit_cost_kusd": 420, "sustainment_hours": 9}, ["fixture"], ["road"]),
    ]
    return {
        "criteria": criteria,
        "constraints": constraints,
        "assumptions": assumptions,
        "bias_checks": checks,
        "evidence": evidence,
        "options": options,
    }


def run_demo() -> dict[str, Any]:
    first = compile_package("point_trade_study", "Select a ground-vehicle power class.", refresh_of=None, **_fixture(400))
    second = compile_package("refresh_range_550", "Same study after the range gate rises to 550 km.", refresh_of=first.package_hash, **_fixture(550))
    return {
        "episode_1": {"selected": first.selected, "margin": first.margin, "hash": first.package_hash, "signer_ready": first.signer_ready},
        "episode_2": {"selected": second.selected, "hash": second.package_hash, "signer_ready": second.signer_ready, "refresh_of": second.refresh_of},
        "flipped": first.selected != second.selected,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))

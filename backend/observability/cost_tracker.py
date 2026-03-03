"""
Cost Tracker — AI Startup Survival Metric
═══════════════════════════════════════════════════════
AI cost explosion kills startups.

Tracks:
  - Cost per interview (text vs voice)
  - Tokens per insight generated
  - Daily AI spend
  - Model usage distribution
  - Cost efficiency trends

Example Insight: "Voice interviews cost 4× text interviews"
→ Now product decisions improve.
"""

import time
import threading
from collections import deque, defaultdict
from datetime import datetime, date
from typing import Optional, Dict, List


# ── Pricing (per 1M tokens) ──
MODEL_PRICING = {
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "default": {"input": 0.10, "output": 0.40},
}

# AssemblyAI pricing per minute of audio
ASSEMBLYAI_PRICE_PER_MINUTE = 0.00416  # $0.25/hr ≈ $0.00416/min


class CostEntry:
    """A single cost event."""

    def __init__(
        self,
        service: str,  # "gemini", "assemblyai", etc.
        model: str,
        task_type: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        audio_minutes: float = 0.0,
        cost_usd: float = 0.0,
        survey_id: Optional[int] = None,
        session_id: Optional[str] = None,
        channel: str = "text",
    ):
        self.timestamp = datetime.now().isoformat()
        self.date_key = date.today().isoformat()
        self.epoch = time.time()
        self.service = service
        self.model = model
        self.task_type = task_type
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.audio_minutes = audio_minutes
        self.cost_usd = cost_usd
        self.survey_id = survey_id
        self.session_id = session_id
        self.channel = channel

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "service": self.service,
            "model": self.model,
            "task_type": self.task_type,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "audio_minutes": round(self.audio_minutes, 2) if self.audio_minutes else 0,
            "cost_usd": round(self.cost_usd, 6),
            "channel": self.channel,
            "survey_id": self.survey_id,
        }


class CostTracker:
    """
    AI Cost Observability Engine.

    Features:
    - Automatic cost calculation from token usage and model pricing
    - Daily budget tracking with overage alerts
    - Cost breakdown by: model, task type, channel (text/voice), survey
    - Cost per interview and per insight metrics
    - Voice vs text cost comparison
    - Cost trend analysis over time
    """

    def __init__(self, daily_budget_usd: float = 10.0, max_entries: int = 10000):
        self._lock = threading.RLock()
        self._entries: deque = deque(maxlen=max_entries)
        self._daily_budget = daily_budget_usd

        # Daily aggregation
        self._daily_costs: Dict[str, float] = defaultdict(float)
        self._daily_tokens: Dict[str, int] = defaultdict(int)

        # Breakdowns
        self._by_model: Dict[str, dict] = defaultdict(lambda: {
            "cost": 0.0, "tokens": 0, "calls": 0,
        })
        self._by_task: Dict[str, dict] = defaultdict(lambda: {
            "cost": 0.0, "tokens": 0, "calls": 0,
        })
        self._by_channel: Dict[str, dict] = defaultdict(lambda: {
            "cost": 0.0, "calls": 0, "interviews": set(),
        })
        self._by_survey: Dict[int, dict] = defaultdict(lambda: {
            "cost": 0.0, "tokens": 0, "calls": 0,
        })

        # Totals
        self._total_cost = 0.0
        self._total_tokens = 0
        self._total_entries = 0
        self._total_interviews_costed = 0
        self._total_insights_costed = 0
        self._start_time = time.time()

    def calculate_cost(self, model: str, tokens_in: int, tokens_out: int,
                       audio_minutes: float = 0.0) -> float:
        """Calculate the cost for a single AI call."""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
        text_cost = (tokens_in * pricing["input"] / 1_000_000) + (tokens_out * pricing["output"] / 1_000_000)
        audio_cost = audio_minutes * ASSEMBLYAI_PRICE_PER_MINUTE if audio_minutes > 0 else 0.0
        return text_cost + audio_cost

    def record_cost(
        self,
        service: str = "gemini",
        model: str = "gemini-2.5-flash",
        task_type: str = "general",
        tokens_in: int = 0,
        tokens_out: int = 0,
        audio_minutes: float = 0.0,
        cost_usd: Optional[float] = None,
        survey_id: Optional[int] = None,
        session_id: Optional[str] = None,
        channel: str = "text",
        is_interview: bool = False,
        is_insight: bool = False,
    ):
        """Record a cost event. If cost_usd is None, it will be auto-calculated."""
        if cost_usd is None:
            cost_usd = self.calculate_cost(model, tokens_in, tokens_out, audio_minutes)

        entry = CostEntry(
            service=service, model=model, task_type=task_type,
            tokens_in=tokens_in, tokens_out=tokens_out,
            audio_minutes=audio_minutes, cost_usd=cost_usd,
            survey_id=survey_id, session_id=session_id, channel=channel,
        )

        total_tokens = tokens_in + tokens_out

        with self._lock:
            self._entries.append(entry)
            self._total_cost += cost_usd
            self._total_tokens += total_tokens
            self._total_entries += 1

            # Daily
            self._daily_costs[entry.date_key] += cost_usd
            self._daily_tokens[entry.date_key] += total_tokens

            # Model breakdown
            bm = self._by_model[model]
            bm["cost"] += cost_usd
            bm["tokens"] += total_tokens
            bm["calls"] += 1

            # Task breakdown
            bt = self._by_task[task_type]
            bt["cost"] += cost_usd
            bt["tokens"] += total_tokens
            bt["calls"] += 1

            # Channel breakdown
            bc = self._by_channel[channel]
            bc["cost"] += cost_usd
            bc["calls"] += 1
            if session_id:
                bc["interviews"].add(session_id)

            # Survey breakdown
            if survey_id:
                bs = self._by_survey[survey_id]
                bs["cost"] += cost_usd
                bs["tokens"] += total_tokens
                bs["calls"] += 1

            if is_interview:
                self._total_interviews_costed += 1
            if is_insight:
                self._total_insights_costed += 1

    # ── Query Methods ──

    def get_daily_spend(self, days: int = 7) -> List[dict]:
        """Get daily spend for the last N days."""
        with self._lock:
            sorted_days = sorted(self._daily_costs.items(), reverse=True)[:days]

        return [
            {
                "date": day,
                "cost_usd": round(cost, 6),
                "tokens": self._daily_tokens.get(day, 0),
                "budget_usd": self._daily_budget,
                "budget_remaining": round(self._daily_budget - cost, 6),
                "overage_pct": round(max(0, (cost - self._daily_budget) / self._daily_budget * 100), 2),
            }
            for day, cost in sorted_days
        ]

    def get_model_breakdown(self) -> dict:
        """Get cost breakdown by model."""
        with self._lock:
            result = {}
            for model, data in self._by_model.items():
                calls = data["calls"]
                result[model] = {
                    "total_cost_usd": round(data["cost"], 6),
                    "total_tokens": data["tokens"],
                    "total_calls": calls,
                    "avg_cost_per_call": round(data["cost"] / max(calls, 1), 6),
                    "cost_share_pct": round(data["cost"] / max(self._total_cost, 0.0001) * 100, 2),
                }
            return result

    def get_task_breakdown(self) -> dict:
        """Get cost breakdown by task type."""
        with self._lock:
            result = {}
            for task, data in self._by_task.items():
                calls = data["calls"]
                result[task] = {
                    "total_cost_usd": round(data["cost"], 6),
                    "total_tokens": data["tokens"],
                    "total_calls": calls,
                    "avg_cost_per_call": round(data["cost"] / max(calls, 1), 6),
                }
            return result

    def get_channel_comparison(self) -> dict:
        """Compare costs between text and voice channels."""
        with self._lock:
            result = {}
            for channel, data in self._by_channel.items():
                interview_count = len(data["interviews"])
                result[channel] = {
                    "total_cost_usd": round(data["cost"], 6),
                    "total_calls": data["calls"],
                    "unique_interviews": interview_count,
                    "avg_cost_per_interview": round(
                        data["cost"] / max(interview_count, 1), 6
                    ),
                }
            return result

    def get_survey_costs(self, survey_id: int = None) -> dict:
        """Get cost data for a specific survey or all surveys."""
        with self._lock:
            if survey_id:
                data = self._by_survey.get(survey_id, {"cost": 0, "tokens": 0, "calls": 0})
                return {
                    "survey_id": survey_id,
                    "total_cost_usd": round(data["cost"], 6),
                    "total_tokens": data["tokens"],
                    "total_calls": data["calls"],
                }
            else:
                return {
                    "surveys_tracked": len(self._by_survey),
                    "top_costs": sorted(
                        [
                            {"survey_id": sid, "cost_usd": round(d["cost"], 6), "calls": d["calls"]}
                            for sid, d in self._by_survey.items()
                        ],
                        key=lambda x: x["cost_usd"],
                        reverse=True,
                    )[:10],
                }

    def get_cost_per_interview(self) -> dict:
        """Calculate average cost per interview."""
        with self._lock:
            return {
                "total_cost_usd": round(self._total_cost, 6),
                "total_interviews_costed": self._total_interviews_costed,
                "avg_cost_per_interview": round(
                    self._total_cost / max(self._total_interviews_costed, 1), 6
                ),
            }

    def get_cost_per_insight(self) -> dict:
        """Calculate average cost per insight generated."""
        with self._lock:
            return {
                "total_cost_usd": round(self._total_cost, 6),
                "total_insights_costed": self._total_insights_costed,
                "tokens_per_insight": round(
                    self._total_tokens / max(self._total_insights_costed, 1), 1
                ),
                "avg_cost_per_insight": round(
                    self._total_cost / max(self._total_insights_costed, 1), 6
                ),
            }

    def get_budget_status(self) -> dict:
        """Get today's budget status."""
        today = date.today().isoformat()
        with self._lock:
            today_spend = self._daily_costs.get(today, 0.0)
            return {
                "date": today,
                "budget_usd": self._daily_budget,
                "spent_usd": round(today_spend, 6),
                "remaining_usd": round(self._daily_budget - today_spend, 6),
                "utilization_pct": round(today_spend / max(self._daily_budget, 0.01) * 100, 2),
                "over_budget": today_spend > self._daily_budget,
            }

    def get_recent_costs(self, limit: int = 30) -> List[dict]:
        """Get recent cost events."""
        with self._lock:
            entries = list(self._entries)[-limit:]
        entries.reverse()
        return [e.to_dict() for e in entries]

    # ── Stats ──

    def stats(self) -> dict:
        uptime = time.time() - self._start_time
        with self._lock:
            return {
                "engine": "CostTracker",
                "total_cost_usd": round(self._total_cost, 6),
                "total_tokens": self._total_tokens,
                "total_events": self._total_entries,
                "daily_budget_usd": self._daily_budget,
                "budget_status": self.get_budget_status(),
                "models_tracked": len(self._by_model),
                "task_types_tracked": len(self._by_task),
                "channels_tracked": len(self._by_channel),
                "surveys_tracked": len(self._by_survey),
                "cost_per_interview": round(
                    self._total_cost / max(self._total_interviews_costed, 1), 6
                ),
                "uptime_seconds": round(uptime, 1),
            }


# ── Global Singleton ──
cost_tracker = CostTracker()

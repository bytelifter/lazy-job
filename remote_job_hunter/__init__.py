"""
remote_job_hunter — Advanced automated job hunting & application pipeline.

CLI batch pipeline for discovering, filtering, matching, and applying
to high-value remote contractor & freelance positions.
"""

from .ai_writer import LocalAIWriter
from .applier import ApplicationOrchestrator, ApplicationResult
from .cv_parser import CVParser, UserProfile
from .fetcher import JobFetcher, JobOffer
from .matcher import JobMatcher, ScoredOffer
from .reporter import Reporter

__all__ = [
    "CVParser",
    "UserProfile",
    "JobFetcher",
    "JobOffer",
    "JobMatcher",
    "ScoredOffer",
    "Reporter",
    "LocalAIWriter",
    "ApplicationOrchestrator",
    "ApplicationResult",
]

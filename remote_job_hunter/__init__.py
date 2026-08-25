"""
remote_job_hunter — Sistema avanzato di job hunting automatizzato.

Pipeline batch CLI per la ricerca, il filtraggio e il matching
di offerte contractor/freelance remote ad alta remunerazione.
"""

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
]

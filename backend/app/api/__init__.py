"""Routers FastAPI."""

from app.api import comments, ext, jobs, metrics, persons, posts

__all__ = ["comments", "ext", "jobs", "metrics", "persons", "posts"]

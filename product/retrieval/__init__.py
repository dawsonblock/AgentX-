"""Retrieval module for building bounded context."""

from .codegraph_service.app import CodeGraphService, get_service

__all__ = ["CodeGraphService", "get_service"]

"""Compatibility KV helpers for generated command code."""

from .backends.sqlite import (
    KvContext,
    KvError,
    KvOperationError,
    KvResult,
    kv_append,
    kv_delete,
    kv_get,
    kv_merge,
    kv_query,
    kv_set,
)

__all__ = [
    "KvContext",
    "KvError",
    "KvOperationError",
    "KvResult",
    "kv_append",
    "kv_delete",
    "kv_get",
    "kv_merge",
    "kv_query",
    "kv_set",
]

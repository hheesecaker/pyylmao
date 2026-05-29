from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ...kvstore import delete_path, get_path, set_path, split_path
from ...state import JsonState


class KvError(Enum):
    NOT_FOUND = 2
    TYPE_ERROR = 3


_MISSING = object()
_default_state: JsonState | None = None


class KvOperationError(RuntimeError):
    def __init__(self, error: KvError, message: str):
        super().__init__(message)
        self.error = error


def configure_default_state(state: JsonState) -> None:
    global _default_state
    _default_state = state


@dataclass
class KvResult:
    _success: bool
    _value: Any = None
    _stats: Any = None
    _errors: list[KvError] | None = None
    _include_stats: bool = False

    def __bool__(self) -> bool:
        return self._success

    def __iter__(self):
        if isinstance(self._value, (list, tuple)):
            return iter(self._value)
        return iter(())

    def success(self) -> bool:
        return self._success

    def failed(self) -> bool:
        return not self._success

    def expect(self, expected_type: type | tuple[type, ...] | None = None) -> Any:
        if not self._success:
            raise RuntimeError(f"kv operation failed: {self._errors or []}")
        if expected_type is not None and self._value is not None and not isinstance(self._value, expected_type):
            raise TypeError(f"expected {expected_type}, got {type(self._value)}")
        return self._value

    def unwrap(self) -> Any:
        return self.expect()

    def json(self) -> str:
        return json.dumps(self._value, ensure_ascii=False)

    def stats(self) -> Any:
        return self._stats

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self._success,
            "value": self._value,
            "stats": self._stats,
            "errors": [error.name for error in self._errors or []],
        }


class KvContext:
    def __init__(self, prefix: str = "", state: JsonState | None = None):
        self.state = state or _default_state
        if self.state is None:
            raise RuntimeError("KvContext requires a configured JsonState")
        self.prefix = str(prefix).strip(".")
        self.root = self.state.data.setdefault("kvstore", {})

    def get(self, path: str = ".", default: Any = _MISSING, include_stats: bool = False) -> KvResult:
        found, value = get_path(self.root, self._parts(path))
        if found:
            return KvResult(True, value, _include_stats=include_stats)
        if default is not _MISSING:
            return KvResult(True, default, _include_stats=include_stats)
        return KvResult(False, None, _errors=[KvError.NOT_FOUND], _include_stats=include_stats)

    def set(self, path: str, value: Any, include_stats: bool = False) -> KvResult:
        set_path(self.root, self._parts(path), value)
        self.state.save()
        return KvResult(True, None, _include_stats=include_stats)

    def append(self, path: str, value: Any, include_stats: bool = False) -> KvResult:
        parts = self._parts(path)
        found, current = get_path(self.root, parts)
        if not found:
            set_path(self.root, parts, [])
            found, current = get_path(self.root, parts)
        if not isinstance(current, list):
            return KvResult(False, None, _errors=[KvError.TYPE_ERROR], _include_stats=include_stats)
        current.append(value)
        self.state.save()
        return KvResult(True, None, _include_stats=include_stats)

    def merge(self, path: str, value: Any, include_stats: bool = False) -> KvResult:
        if not isinstance(value, dict):
            return KvResult(False, None, _errors=[KvError.TYPE_ERROR], _include_stats=include_stats)
        parts = self._parts(path)
        found, current = get_path(self.root, parts)
        if not found:
            set_path(self.root, parts, json.loads(json.dumps(value)))
            self.state.save()
            return KvResult(True, None, _include_stats=include_stats)
        if not isinstance(current, dict):
            return KvResult(False, None, _errors=[KvError.TYPE_ERROR], _include_stats=include_stats)
        merge_dict(current, value)
        self.state.save()
        return KvResult(True, None, _include_stats=include_stats)

    def delete(self, path: str) -> KvResult:
        if delete_path(self.root, self._parts(path)):
            self.state.save()
            return KvResult(True, None)
        return KvResult(False, None, _errors=[KvError.NOT_FOUND])

    def _parts(self, path: str) -> list[str]:
        prefix_parts = split_path(self.prefix)
        raw = str(path).strip()
        if raw in {"", "."}:
            return prefix_parts
        return prefix_parts + split_path(raw)


def kv_get(path: str, default: Any = _MISSING) -> Any:
    root, _ = default_root()
    parts = split_path(path)
    found, value = get_path(root, parts)
    if found:
        return value
    if default is not _MISSING:
        return default
    raise KvOperationError(KvError.NOT_FOUND, f"Path '{path}' is not set")


def kv_set(path: str, value: Any) -> bool:
    root, state = default_root()
    set_path(root, split_path(path), value)
    state.save()
    return True


def kv_append(path: str, value: Any) -> bool:
    root, state = default_root()
    parts = split_path(path)
    found, current = get_path(root, parts)
    if not found:
        set_path(root, parts, [])
        found, current = get_path(root, parts)
    if not isinstance(current, list):
        raise KvOperationError(KvError.TYPE_ERROR, f"Path '{path}' is not a list")
    current.append(value)
    state.save()
    return True


def kv_merge(path: str, value: Any) -> bool:
    if not isinstance(value, dict):
        raise KvOperationError(KvError.TYPE_ERROR, "merge value is not a dictionary")
    root, state = default_root()
    parts = split_path(path)
    found, current = get_path(root, parts)
    if not found:
        set_path(root, parts, json.loads(json.dumps(value)))
        state.save()
        return True
    if not isinstance(current, dict):
        raise KvOperationError(KvError.TYPE_ERROR, f"Path '{path}' is not a dictionary")
    merge_dict(current, value)
    state.save()
    return True


def kv_delete(path: str) -> bool:
    root, state = default_root()
    deleted = delete_path(root, split_path(path))
    if deleted:
        state.save()
    return deleted


def kv_query(expression: str) -> Any:
    path, _, op = str(expression).partition("|")
    value = kv_get(path.strip())
    op = op.strip()
    if op == "keys":
        if isinstance(value, dict):
            return list(value.keys())
        if isinstance(value, list):
            return list(range(len(value)))
        return []
    if op == "length":
        try:
            return len(value)
        except TypeError:
            return 0
    if op:
        raise KvOperationError(KvError.TYPE_ERROR, f"Unsupported query operator: {op}")
    return value


def default_root() -> tuple[dict[str, Any], JsonState]:
    if _default_state is None:
        raise RuntimeError("KV helpers require a configured JsonState")
    return _default_state.data.setdefault("kvstore", {}), _default_state


def merge_dict(target: dict[str, Any], value: dict[str, Any]) -> None:
    for key, incoming in value.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(incoming, dict):
            merge_dict(current, incoming)
        else:
            target[key] = json.loads(json.dumps(incoming))

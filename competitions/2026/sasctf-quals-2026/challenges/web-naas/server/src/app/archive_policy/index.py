from collections.abc import Mapping
from typing import Any

SCAN_DEFAULTS = {
    "tier": "basic",
    "backend": "inline",
    "hold": "pending",
    "interlock": "closed",
}

RUNTIME_KEYS = (
    "tier",
    "backend",
    "hold",
    "interlock",
    "descriptor_ref",
    "reference_map",
    "provider",
)


def _mapping_items(value: Any):
    if hasattr(value, "items"):
        return value.items()
    if hasattr(value, "keys"):
        return ((key, value[key]) for key in value.keys())
    return None


def scan_policy(root_mapping) -> dict:
    visible = dict(SCAN_DEFAULTS)
    if isinstance(root_mapping, Mapping):
        for key in SCAN_DEFAULTS:
            if key in root_mapping:
                visible[key] = root_mapping[key]
        policy_index = root_mapping.get("policy_index")
    else:
        policy_index = None

    if policy_index is None:
        return visible

    entries = _mapping_items(policy_index)
    if entries is None:
        return visible
    try:
        for key, value in entries:
            if key in SCAN_DEFAULTS:
                visible[key] = value
    except Exception:
        return dict(SCAN_DEFAULTS)
    return visible


def runtime_value(root_mapping, key, default=None):
    policy_index = None
    if isinstance(root_mapping, Mapping):
        policy_index = root_mapping.get("policy_index")
    if hasattr(policy_index, "get"):
        return policy_index.get(key, default)
    try:
        if policy_index is not None and key in policy_index:
            return policy_index[key]
    except Exception:
        pass
    if isinstance(root_mapping, Mapping):
        return root_mapping.get(key, default)
    return default


def runtime_policy(root_mapping) -> dict:
    return {
        key: runtime_value(root_mapping, key, SCAN_DEFAULTS.get(key))
        for key in RUNTIME_KEYS
    }

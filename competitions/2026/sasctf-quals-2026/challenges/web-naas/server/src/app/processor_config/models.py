from typing import Literal

from pydantic import BaseModel, ConfigDict


class ProcessorScopeModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    owner_id: str
    billing_id: str
    storage_uid: str
    processor_ref: str
    mode: Literal["audit", "compact", "restore"]
    tier: Literal["basic", "archive"] = "basic"
    provider: str = "local"
    session_ref: str | None = None
    provider_url: str | None = None
    attestation_class: str = "standard"
    evidence_hold: str = "pending"
    safety_interlock: str = "closed"
    reference_root: str | None = None
    session_start_ms: int | None = None


class ArchiveMountState(BaseModel):
    model_config = ConfigDict(extra="allow")

    owner_id: str
    billing_id: str
    storage_uid: str
    mount: str
    cap: str
    backend: Literal["inline", "repair"] = "inline"
    tier: Literal["basic", "archive"] = "basic"
    policy_index: object | None = None
    reference_map: object | None = None
    descriptor_ref: object | None = None
    hold: str = "pending"
    interlock: str = "closed"

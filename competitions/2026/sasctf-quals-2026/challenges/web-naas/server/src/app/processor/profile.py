import json

from app.processor_config.hydrate import apply_patch
from app.processor_config.models import ProcessorScopeModel
from app.processor_config.scope import maintenance_session_start


def build_processor_scope(
    user, billing, storage, processor_ref: str, mode: str, options_json: str
):
    session_start_ms = maintenance_session_start()
    scope_model = ProcessorScopeModel(
        owner_id=str(user.id),
        billing_id=billing.uid,
        storage_uid=storage.uid,
        processor_ref=processor_ref,
        mode=mode,
        tier="basic",
    )
    user_options = json.loads(options_json or "{}")
    if not isinstance(user_options, dict):
        user_options = {}
    user_options.pop("session_start_ms", None)
    scope_model = apply_patch(scope_model, user_options)
    scope_model.owner_id = str(user.id)
    scope_model.billing_id = billing.uid
    scope_model.storage_uid = storage.uid
    scope_model.processor_ref = processor_ref
    scope_model.tier = "basic"
    scope_model.session_start_ms = session_start_ms
    scope = scope_model.model_dump(mode="json")
    scope["owner_id"] = str(user.id)
    scope["billing_id"] = billing.uid
    scope["storage_uid"] = storage.uid
    scope["processor_ref"] = processor_ref
    scope["tier"] = "basic"
    scope["session_start_ms"] = session_start_ms
    return json.dumps(scope, sort_keys=True), scope

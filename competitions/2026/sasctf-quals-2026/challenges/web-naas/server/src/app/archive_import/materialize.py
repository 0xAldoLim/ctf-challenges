from app.storage.paths import archive_file

from .bundle import RestorePlan
from .transactions import copy_to_path


def materialize_restore_plan(plan: RestorePlan, destination_storage_uid: str) -> None:
    copy_to_path(plan.source, archive_file(destination_storage_uid))

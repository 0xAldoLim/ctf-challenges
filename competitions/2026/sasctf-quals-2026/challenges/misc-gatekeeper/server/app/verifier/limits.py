from typing import Final

from .address_space import SPACE

_CODE_BYTES: Final = SPACE.by_name("user-code").length
_DATA_BYTES: Final = SPACE.by_name("user-data").length


class Limits:
    code_bytes: Final = _CODE_BYTES
    data_bytes: Final = _DATA_BYTES
    program_bytes: Final = _CODE_BYTES + _DATA_BYTES
    file_bytes: Final = 2 * 1024
    step_budget: Final = 25000
    wall_clock_s: Final = 25
    solver_ms: Final = 5000
    solver_bytes: Final = 1024 * 1024 * 1024
    symbolic_window: Final = 0x100
    trusted_frame_window: Final = 0x200

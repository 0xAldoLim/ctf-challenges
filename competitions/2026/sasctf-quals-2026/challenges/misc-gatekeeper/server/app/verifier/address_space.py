import enum
from dataclasses import dataclass, field
from typing import Final, Iterator, Optional


class Perm(enum.Flag):
    NONE = 0
    R = enum.auto()
    W = enum.auto()
    X = enum.auto()

    @classmethod
    def parse(cls, spec: str) -> "Perm":
        bits = cls.NONE
        if "r" in spec:
            bits |= cls.R
        if "w" in spec:
            bits |= cls.W
        if "x" in spec:
            bits |= cls.X
        return bits


@dataclass(frozen=True, slots=True)
class Segment:
    name: str
    base: int
    limit: int
    perm: Perm
    children: tuple["Segment", ...] = field(default_factory=tuple)

    def holds(self, addr: int) -> bool:
        return self.base <= addr < self.limit

    def grants(self, right: Perm) -> bool:
        return right in self.perm

    @property
    def length(self) -> int:
        return self.limit - self.base


_TRUSTED_ROUTINES: Final = {
    "create_file_plain": (0x80000000, 0x2000),
    "isqrt": (0x80002000, 0x2000),
    "read_file_plain": (0x80004000, 0x2000),
    "readc": (0x80008000, 0x2000),
    "mini_printf": (0x8000A000, 0x1000),
}


class AddressSpace:
    def __init__(self, roots: tuple[Segment, ...]) -> None:
        self._roots = roots
        self._by_name = {seg.name: seg for seg in self._descend(roots)}

    @staticmethod
    def _descend(segs: tuple[Segment, ...]) -> Iterator[Segment]:
        for seg in segs:
            yield seg
            yield from AddressSpace._descend(seg.children)

    @classmethod
    def build(cls, layout) -> "AddressSpace":
        roots: list[Segment] = []
        for name, base, length, perms, *rest in layout:
            children: tuple[Segment, ...] = ()
            if rest and rest[0]:
                children = tuple(
                    Segment(cn, cb, cb + cl, Perm.parse(perms))
                    for cn, cb, cl in rest[0]
                )
            roots.append(
                Segment(name, base, base + length, Perm.parse(perms), children)
            )
        return cls(tuple(roots))

    def locate(self, addr: int) -> Optional[Segment]:
        for root in self._roots:
            if not root.holds(addr):
                continue
            return next((c for c in root.children if c.holds(addr)), root)
        return None

    def by_name(self, name: str) -> Optional[Segment]:
        return self._by_name.get(name)

    def all_segments(self) -> Iterator[Segment]:
        yield from self._descend(self._roots)

    def _allows(self, addr: int, right: Perm) -> bool:
        seg = self.locate(addr)
        return seg is not None and seg.grants(right)

    def may_read(self, addr: int) -> bool:
        return self._allows(addr, Perm.R)

    def may_write(self, addr: int) -> bool:
        return self._allows(addr, Perm.W)

    def may_exec(self, addr: int) -> bool:
        return self._allows(addr, Perm.X)

    def _with(self, right: Perm) -> tuple[Segment, ...]:
        return tuple(s for s in self.all_segments() if s.grants(right))

    def executable(self) -> tuple[Segment, ...]:
        return self._with(Perm.X)

    def readable(self) -> tuple[Segment, ...]:
        return self._with(Perm.R)

    def writable(self) -> tuple[Segment, ...]:
        return self._with(Perm.W)


_LAYOUT: Final = (
    ("gatekeeper-mmio", 0x13370000, 0x01000, "---"),
    ("handles-table", 0x13400000, 0x80000, "---"),
    (
        "trusted-funcs",
        0x80000000,
        0x10000,
        "--x",
        tuple((name, base, ln) for name, (base, ln) in _TRUSTED_ROUTINES.items()),
    ),
    ("user-code", 0x00300000, 0x10000, "r-x"),
    ("user-data", 0x00310000, 0x10000, "rw-"),
    ("stack", 0x00320000, 0x20000, "rw-"),
)

SPACE: Final = AddressSpace.build(_LAYOUT)

for _required in (
    "user-code",
    "user-data",
    "stack",
    "trusted-funcs",
    "handles-table",
    "gatekeeper-mmio",
):
    assert SPACE.by_name(_required) is not None, _required
assert SPACE.by_name("user-code").limit == SPACE.by_name("user-data").base
assert SPACE.by_name("user-data").limit == SPACE.by_name("stack").base

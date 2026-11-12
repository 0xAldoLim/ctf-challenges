from verifier.address_space import AddressSpace, SPACE


def test_locate_top_level():
    seg = SPACE.locate(0x13370010)
    assert seg is not None
    assert seg.name == "gatekeeper-mmio"


def test_locate_child():
    seg = SPACE.locate(0x80001000)
    assert seg is not None
    assert seg.name == "create_file_plain"


def test_permission_checks():
    code = SPACE.by_name("user-code")
    assert code is not None
    assert SPACE.may_exec(code.base)
    assert not SPACE.may_write(code.base)

    data = SPACE.by_name("user-data")
    assert data is not None
    assert SPACE.may_read(data.base)
    assert SPACE.may_write(data.base)
    assert not SPACE.may_exec(data.base)


def test_custom_address_space():
    layout = (
        ("gatekeeper-mmio", 0x13370000, 0x1000, "---"),
        ("handles-table", 0x13400000, 0x20000, "---"),
        ("uart", 0xFFFF0000, 0x1000, "rw-"),
        (
            "trusted-funcs",
            0x80000000,
            0x10000,
            "r-x",
            (
                ("create_file_plain", 0x80000000, 0x2000),
                ("read_file_plain", 0x80004000, 0x2000),
            ),
        ),
        ("user-code", 0x80010000, 0x10000, "r-x"),
        ("user-data", 0x80020000, 0x10000, "rw-"),
        ("stack", 0x80030000, 0x20000, "rw-"),
    )

    space = AddressSpace.build(layout)

    assert space.locate(0x80001000).name == "create_file_plain"
    assert space.locate(0x13400010).name == "handles-table"
    assert space.locate(0x12345678) is None

    code = space.by_name("user-code")
    assert code is not None
    assert space.may_exec(code.base)
    assert not space.may_write(code.base)

    data = space.by_name("user-data")
    assert data is not None
    assert space.may_read(data.base)
    assert space.may_write(data.base)
    assert not space.may_exec(data.base)

    assert space.by_name("non-existent") is None
    assert len(list(space.all_segments())) == 9

def format_size(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB")
    current = float(max(0, value))
    for unit in units:
        if current < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(current)} {unit}"
            return f"{current:.1f} {unit}"
        current /= 1024
    return f"{int(current)} B"

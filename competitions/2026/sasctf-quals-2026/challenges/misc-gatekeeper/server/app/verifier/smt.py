from triton import SOLVER_STATE

_INCONCLUSIVE = (SOLVER_STATE.UNKNOWN, SOLVER_STATE.TIMEOUT, SOLVER_STATE.OUTOFMEM)


def mkbv(actx, value, bits):
    return actx.bv(int(value) & ((1 << bits) - 1), bits)


def under_pc(ctx, *constraints):
    actx = ctx.getAstContext()
    return actx.land([ctx.getPathPredicate(), *constraints])


def solve(ctx, node):
    model, status, _elapsed_ms = ctx.getModel(node, True)
    if status in _INCONCLUSIVE:
        raise ValueError(f"solver could not decide the query (state={status})")
    return model, status


def sat(ctx, node) -> bool:
    model, status = solve(ctx, node)
    return status == SOLVER_STATE.SAT and model is not None

import json
import sys
import ast
import traceback


SAFE_BUILTINS = {
    'len': len,
    'range': range,
    'min': min,
    'max': max,
    'abs': abs,
    'int': int,
    'str': str,
    'bool': bool,
    'list': list,
    'tuple': tuple,
    'dict': dict,
    'enumerate': enumerate,
    'ord': ord,
}


ALLOWED_NODES = {
    ast.Module,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.Assign,
    ast.AugAssign,
    ast.Expr,
    ast.For,
    ast.While,
    ast.If,
    ast.Return,
    ast.Break,
    ast.Continue,
    ast.Pass,

    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Subscript,
    ast.Slice,

    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.Call,

    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.FloorDiv,
    ast.USub,
    ast.UAdd,
    ast.And,
    ast.Or,
    ast.Not,

    ast.BitAnd,
    ast.BitOr,
    ast.BitXor,
    ast.LShift,
    ast.RShift,

    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
}


FORBIDDEN_NODES = (
    ast.Attribute,
    ast.Import,
    ast.ImportFrom,
    ast.Try,
    ast.Raise,
    ast.With,
    ast.Lambda,
    ast.ClassDef,
    ast.Global,
    ast.Nonlocal,
    ast.Delete,
    ast.Yield,
    ast.YieldFrom,
    ast.Await,
    ast.AsyncFunctionDef,
    ast.IfExp,
)


class KernelValidationError(Exception):
    pass


def loc(node) -> str:
    line = getattr(node, 'lineno', 0)
    col = getattr(node, 'col_offset', 0)

    if line:
        return f' at line {line}, column {col}'

    return ''


def validate_code(code: str):
    try:
        tree = ast.parse(code, mode='exec')
    except SyntaxError as e:
        line = e.lineno or 0
        col = e.offset or 0
        raise KernelValidationError(f'SyntaxError at line {line}, column {col}')

    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_NODES):
            raise KernelValidationError(
                f'Forbidden syntax: {type(node).__name__}{loc(node)}'
            )

        if type(node) not in ALLOWED_NODES and not isinstance(node, FORBIDDEN_NODES):
            raise KernelValidationError(
                f'Forbidden syntax: {type(node).__name__}{loc(node)}'
            )

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise KernelValidationError(
                    f'Only direct function calls are allowed{loc(node)}'
                )


def normalize_aux_data(aux_data):
    if not isinstance(aux_data, list):
        aux_data = []

    out = []

    for value in aux_data[:64]:
        if isinstance(value, bool):
            value = int(value)

        if not isinstance(value, int):
            value = 0

        value &= 0xffffffff
        out.append(value)

    while len(out) < 64:
        out.append(0)

    return out


def format_runtime_error(exc: BaseException) -> str:
    tb = traceback.extract_tb(exc.__traceback__)

    user_frame = None
    for frame in reversed(tb):
        if frame.filename == '<string>':
            user_frame = frame
            break

    exc_name = type(exc).__name__

    if user_frame:
        return (
            f'Runtime error: {exc_name} '
            f'at line {user_frame.lineno}, in {user_frame.name}'
        )

    return f'Runtime error: {exc_name}'


def main():
    raw = sys.stdin.read()
    data = json.loads(raw)

    code = data.get('code', '')
    mapdata = data.get('mapdata', '')
    aux_data = normalize_aux_data(data.get('aux_data', []))

    validate_code(code)

    env = {'__builtins__': SAFE_BUILTINS}
    exec(code, env)

    kernel = env.get('player_kernel')
    if kernel is None:
        raise KernelValidationError('player_kernel not found')

    out_ref = [0] * 65
    kernel(mapdata, aux_data, out_ref)

    action = out_ref[0]
    if not isinstance(action, int):
        action = 0

    result = {
        'action': action,
        'aux_data': normalize_aux_data(aux_data),
    }

    sys.stdout.write(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except KernelValidationError as e:
        sys.stderr.write(str(e))
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(format_runtime_error(e))
        sys.exit(1)
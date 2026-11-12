const arrays = new Map();

function writeLine(line) {
    std.out.puts(line + "\n");
    std.out.flush();
}

function ok() {
    writeLine("OK");
}

function fail(message) {
    writeLine(`ERR @ ${message}`);
}

function okValue(name, value) {
    writeLine(`OK @ ${name} @ ${value}`);
}

function usage() {
    writeLine("commands");
    writeLine("  help");
    writeLine("  new <name>");
    writeLine("  list");
    writeLine("  drop <name>");
    writeLine("  set <name> <index> <value>");
    writeLine("  copy <dst_name> <dst> <src_name> <src>");
    writeLine("  get <name> <index>");
    writeLine("  del <name> <index>");
    writeLine("  add <name> <dst> <lhs> <rhs>");
    writeLine("  sub <name> <dst> <lhs> <rhs>");
    writeLine("  mul <name> <dst> <lhs> <rhs>");
    writeLine("  div <name> <dst> <lhs> <rhs>");
    writeLine("  extend <state> <coeffs> [count]");
    writeLine("  quit");
}

function expectArray(name) {
    const arr = arrays.get(name);
    if (!arr) {
        throw new Error(`unknown array '${name}'`);
    }
    return arr;
}

function parseIndex(raw) {
    if (!/^-?\d+$/.test(raw)) {
        throw new Error(`invalid index '${raw}'`);
    }
    const value = Number(raw);
    if (!Number.isSafeInteger(value) || value < 0) {
        throw new Error(`invalid index '${raw}'`);
    }
    return value;
}

function parseCount(raw) {
    const value = parseIndex(raw);
    if (value === 0) {
        throw new Error("count must be positive");
    }
    return value;
}

function parseBig(raw) {
    let text = raw;
    if (text.endsWith("n")) {
        text = text.slice(0, -1);
    }
    try {
        return BigInt(text);
    } catch (error) {
        throw new Error(`invalid bigint '${raw}'`);
    }
}

function readBig(arr, idx) {
    const value = arr[idx];
    if (typeof value !== "bigint") {
        throw new Error(`slot ${idx} is not a bigint`);
    }
    return value;
}

function dumpValue(value) {
    if (typeof value === "bigint") {
        return value.toString();
    }
    if (value === undefined) {
        return "undefined";
    }
    if (value === null) {
        return "null";
    }
    return String(value);
}

function computeBinary(op, lhs, rhs) {
    switch (op) {
    case "add":
        return lhs + rhs;
    case "sub":
        return lhs - rhs;
    case "mul":
        return lhs * rhs;
    case "div":
        if (rhs === 0n) {
            throw new Error("division by zero");
        }
        return lhs / rhs;
    default:
        throw new Error(`unsupported op '${op}'`);
    }
}

function runExtend(state, coeffs, count) {
    if (state.length < coeffs.length) {
        state.length = coeffs.length;
    }

    let produced = 0n;

    for (let round = 0; round < count; round++) {
        let next = 0n;
        const base = state.length - coeffs.length;

        for (let i = 0; i < coeffs.length; i++) {
            const coeff = coeffs[i];
            const term = state[base + i];
            next += (term ?? 0n) * (coeff ?? 0n);
        }

        state.push(next);
        produced = next;
    }

    return produced;
}

function handleNew(parts) {
    if (parts.length !== 2) {
        throw new Error("usage: new <name>");
    }
    const name = parts[1];
    if (!/^[A-Za-z0-9_.-]{1,32}$/.test(name)) {
        throw new Error("invalid array name");
    }
    if (arrays.has(name)) {
        throw new Error(`array '${name}' already exists`);
    }
    arrays.set(name, []);
    ok();
}

function handleList(parts) {
    if (parts.length !== 1) {
        throw new Error("usage: list");
    }
    if (arrays.size === 0) {
        ok();
        return;
    }
    for (const [name, arr] of arrays) {
        okValue(name, arr.length);
    }
}

function handleDrop(parts) {
    if (parts.length !== 2) {
        throw new Error("usage: drop <name>");
    }
    if (!arrays.delete(parts[1])) {
        throw new Error(`unknown array '${parts[1]}'`);
    }
    ok();
}

function handleSet(parts) {
    if (parts.length !== 4) {
        throw new Error("usage: set <name> <index> <value>");
    }
    const arr = expectArray(parts[1]);
    const idx = parseIndex(parts[2]);
    arr[idx] = parseBig(parts[3]);
    ok();
}

function handleGet(parts) {
    if (parts.length !== 3) {
        throw new Error("usage: get <name> <index>");
    }
    const arr = expectArray(parts[1]);
    const idx = parseIndex(parts[2]);
    okValue(`${parts[1]}[${idx}]`, dumpValue(arr[idx]));
}

function handleCopy(parts) {
    if (parts.length !== 5) {
        throw new Error("usage: copy <dst_name> <dst> <src_name> <src>");
    }
    const dstArr = expectArray(parts[1]);
    const dst = parseIndex(parts[2]);
    const srcArr = expectArray(parts[3]);
    const src = parseIndex(parts[4]);
    dstArr[dst] = srcArr[src];
    ok();
}

function handleDelete(parts) {
    if (parts.length !== 3) {
        throw new Error("usage: del <name> <index>");
    }
    const arr = expectArray(parts[1]);
    const idx = parseIndex(parts[2]);
    delete arr[idx];
    ok();
}

function handleBinary(parts) {
    if (parts.length !== 5) {
        throw new Error(`usage: ${parts[0]} <name> <dst> <lhs> <rhs>`);
    }
    const arr = expectArray(parts[1]);
    const dst = parseIndex(parts[2]);
    const lhs = readBig(arr, parseIndex(parts[3]));
    const rhs = readBig(arr, parseIndex(parts[4]));
    arr[dst] = computeBinary(parts[0], lhs, rhs);
    ok();
}

function handleExtend(parts) {
    if (parts.length !== 3 && parts.length !== 4) {
        throw new Error("usage: extend <state> <coeffs> [count]");
    }
    const state = expectArray(parts[1]);
    const coeffs = expectArray(parts[2]);
    const count = parts.length === 4 ? parseCount(parts[3]) : 1;
    const produced = runExtend(state, coeffs, count);
    okValue("result", produced.toString());
}

function dispatch(line) {
    const trimmed = line.trim();
    if (trimmed === "") {
        return true;
    }

    const parts = trimmed.split(/\s+/);

    switch (parts[0]) {
    case "help":
        usage();
        return true;
    case "new":
        handleNew(parts);
        return true;
    case "list":
        handleList(parts);
        return true;
    case "drop":
        handleDrop(parts);
        return true;
    case "set":
        handleSet(parts);
        return true;
    case "copy":
        handleCopy(parts);
        return true;
    case "get":
        handleGet(parts);
        return true;
    case "del":
        handleDelete(parts);
        return true;
    case "add":
    case "sub":
    case "mul":
    case "div":
        handleBinary(parts);
        return true;
    case "extend":
        handleExtend(parts);
        return true;
    case "quit":
    case "exit":
        ok();
        return false;
    default:
        throw new Error(`unknown command '${parts[0]}'`);
    }
}

function main() {
    writeLine("JSculator by AI Bro");
    writeLine("type help to see list of commands");
    std.out.puts("> ");
    std.out.flush();

    for (;;) {
        const line = std.in.getline();
        if (line === null) {
            break;
        }

        try {
            if (!dispatch(line)) {
                break;
            }
        } catch (error) {
            fail(error.message ?? String(error));
        }

        std.out.puts("> ");
        std.out.flush();
    }
}

main();

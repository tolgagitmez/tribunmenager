"""Compile the real patched policy header without cloning or linking the game."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
REVISION = '087414cde936c3e26ed0b8c244d9d85425ec5657'
BLOB = '15754f92c9f9bcdf8563cf67202f418b74a46739'
TARGET = 'src/onthepitch/aitactics.hpp'


def blob_id(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def literal(node, constants):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in constants:
        return constants[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return literal(node.left, constants) + literal(node.right, constants)
    raise ValueError('Unsupported header patch expression')


def replay(header, patch):
    tree = ast.parse(patch)
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = node.value.value
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'apply']
    if len(functions) != 1:
        raise ValueError('Expected one apply function')
    fn = functions[0]
    def is_header_edit(n):
        return (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'edit' and
                len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) and n.args[1].value == TARGET)
    all_edits = [n for n in ast.walk(fn) if is_header_edit(n)]
    direct = [n.value for n in fn.body if isinstance(n, ast.Expr) and is_header_edit(n.value)]
    if not direct or set(direct) != set(all_edits):
        raise ValueError('Missing or conditional header edits')
    count = 0
    for call in direct:
        if len(call.args) != 3 or call.keywords or not isinstance(call.args[2], ast.List):
            raise ValueError('Unsupported header edit call')
        for pair in call.args[2].elts:
            if not isinstance(pair, ast.Tuple) or len(pair.elts) != 2:
                raise ValueError('Unsupported edit pair')
            old, new = (literal(n, constants) for n in pair.elts)
            if not old or header.count(old) != 1:
                raise ValueError('Unexpected header anchor: ' + repr(old[:160]))
            header = header.replace(old, new, 1)
            count += 1
    return header, count


def main():
    if json.loads((HERE / 'upstream.json').read_text())['revision'] != REVISION:
        raise ValueError('Pinned revision changed; refresh policy header deliberately')
    raw = (HERE / 'policy-preflight/aitactics.upstream.hpp').read_bytes()
    if blob_id(raw) != BLOB:
        raise ValueError('Pinned upstream policy header integrity mismatch')
    header, count = replay(raw.decode('utf-8'), (HERE / 'short_match_patch.py').read_text())
    with tempfile.TemporaryDirectory(prefix='tribun-policy-') as d:
        root = Path(d)
        (root / 'aitactics.hpp').write_text(header, encoding='utf-8')
        exe = root / 'attack-policy-test'
        env = {k: v for k, v in os.environ.items() if not k.startswith('TRIBUN_')}
        print(f'Replayed {count} header edits; sha256={hashlib.sha256(header.encode()).hexdigest()}', flush=True)
        subprocess.run(['c++', '-std=c++17', '-UNDEBUG', '-I', str(root), str(HERE / 'attack-policy-test.cpp'), '-o', str(exe)], check=True, env=env, timeout=120)
        subprocess.run([str(exe)], check=True, env=env, timeout=60)
    print('Patched policy header and assertion executable passed; full native engine NOT built.', flush=True)


if __name__ == '__main__':
    main()

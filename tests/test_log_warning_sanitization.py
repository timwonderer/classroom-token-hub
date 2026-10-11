"""Execute the flagged warning calls without importing the app or using a DB."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _sanitizer():
    tree = ast.parse((ROOT / 'app/utils/helpers.py').read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'sanitize_for_log')
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'helpers.py', 'exec'), namespace)
    return namespace['sanitize_for_log']


@pytest.mark.parametrize('filename, expected_calls', [('app/__init__.py', 1), ('wsgi.py', 7)])
def test_flagged_warnings_cannot_forge_lines(filename, expected_calls):
    tree = ast.parse((ROOT / filename).read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr in {'warning', 'error'}
             and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                     and child.func.id == 'sanitize_for_log' for child in ast.walk(node))]
    assert len(calls) == expected_calls
    malicious = 'value\r\nFAKE\t\x1b\x85\u2028\u2029'
    logger = Mock()
    namespace = {
        'app': SimpleNamespace(logger=logger),
        'request': SimpleNamespace(path=malicious, url=malicious, remote_addr=malicious, method=malicious),
        'real_ip': malicious, 'error_msg': malicious, 'limit_description': malicious, 'in_request_context': True, 'error_type': 'test',
        'sanitize_for_log': _sanitizer(),
    }
    for call in calls:
        exec(compile(ast.Expression(call), filename, 'eval'), namespace)
    for call in [*logger.warning.call_args_list, *logger.error.call_args_list]:
        message = call.args[0] % call.args[1:]
        assert all(character.isprintable() for character in message)
        assert 'FAKE' in message and '\\x0d\\x0a' in message


def test_sanitizer_preserves_text_and_escapes_all_control_characters():
    sanitize = _sanitizer()
    assert sanitize('/student/dashboard?x=1') == '/student/dashboard?x=1'
    assert sanitize(None) == 'None'
    for codepoint in [*range(32), *range(127, 160), 0x2028, 0x2029]:
        assert sanitize(chr(codepoint)) == f'\\x{codepoint:02x}'

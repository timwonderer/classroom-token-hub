"""Firewall CLI failure and input boundaries, without contacting DigitalOcean."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIREWALL_ID = '12345678-1234-1234-1234-123456789abc'


@pytest.fixture(params=['add-github-actions-to-firewall.py', 'create-github-actions-firewall.py'])
def script(request):
    spec = importlib.util.spec_from_file_location('firewall_script', ROOT / 'scripts' / request.param)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_missing_doctl_exits_with_diagnostic(script, monkeypatch, capsys):
    identifier = FIREWALL_ID if script.__file__.endswith('add-github-actions-to-firewall.py') else '123'
    monkeypatch.setattr(script.sys, 'argv', [script.__file__, identifier])
    run = Mock(side_effect=FileNotFoundError('doctl'))
    monkeypatch.setattr(script.subprocess, 'run', run)
    with pytest.raises(SystemExit) as error:
        script.main()
    assert error.value.code == 1
    assert 'doctl' in capsys.readouterr().out
    run.assert_called_once_with(['doctl', 'version'], capture_output=True, text=True)


@pytest.mark.parametrize('identifier', ['--help', '1;echo injected', '1\n2', '', '0'])
def test_invalid_ids_never_spawn(script, identifier, monkeypatch):
    monkeypatch.setattr(script.sys, 'argv', [script.__file__, identifier])
    run = Mock()
    monkeypatch.setattr(script.subprocess, 'run', run)
    with pytest.raises(SystemExit) as error:
        script.main()
    assert error.value.code == 1
    run.assert_not_called()


@pytest.mark.parametrize('ranges, expected', [
    (['192.0.2.1/24', '2001:db8::/32'], ['192.0.2.0/24', '2001:db8::/32']),
    (['192.0.2.1,ports:all'], None),
    (['192.0.2.1;echo injected'], None),
])
def test_api_ranges_are_validated(script, ranges, expected, monkeypatch):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = json.dumps({'actions': ranges}).encode()
    monkeypatch.setattr(script.urllib.request, 'urlopen', Mock(return_value=response))
    assert script.fetch_github_ips() == expected


def test_command_result_contract(script, monkeypatch):
    monkeypatch.setattr(script.subprocess, 'run', Mock(return_value=SimpleNamespace(returncode=1, stdout='out', stderr='err')))
    result = script.run_command(['doctl', 'version'])
    assert result == ((False, 'err') if script.__file__.endswith('add-github-actions-to-firewall.py') else (False, 'out', 'err'))


def test_create_rejects_invalid_returned_firewall_id(monkeypatch):
    spec = importlib.util.spec_from_file_location('create_firewall', ROOT / 'scripts/create-github-actions-firewall.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run = Mock(return_value=(True, '--help', ''))
    monkeypatch.setattr(module, 'run_command', run)
    assert module.create_firewall_with_rules('123', ['192.0.2.0/24'] * 51) is None
    assert run.call_count == 1


def test_valid_ids_reach_doctl(script, monkeypatch):
    identifier = FIREWALL_ID if script.__file__.endswith('add-github-actions-to-firewall.py') else '123'
    monkeypatch.setattr(script.sys, 'argv', [script.__file__, identifier])
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout='', stderr=''))
    monkeypatch.setattr(script.subprocess, 'run', run)
    monkeypatch.setattr(script, 'fetch_github_ips', lambda: None)
    with pytest.raises(SystemExit):
        script.main()
    assert run.call_args_list[1].args[0][-1] == identifier


def test_uncaptured_spawn_error_returns_failure(monkeypatch):
    spec = importlib.util.spec_from_file_location('create_firewall', ROOT / 'scripts/create-github-actions-firewall.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.subprocess, 'run', Mock(side_effect=FileNotFoundError('doctl')))
    success, output, error = module.run_command(['doctl', 'version'], capture=False)
    assert success is False and output == '' and 'doctl' in error

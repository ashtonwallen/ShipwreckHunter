import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
from mcp import Client
from mcp.client.stdio import StdioServerParameters
import pytest

from backend import assistant, connectors, db, jobs
from backend.mcp_server import create_server
from mcp_stdio import local_url


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DATA', tmp_path)
    for name in ('raw', 'derived', 'sources', 'media', 'exports'):
        (tmp_path / name).mkdir()
    db.init()
    db.put('site', {'name': 'Test site', 'conclusion': 'Unidentified',
                   'next_steps': ['Inspect original scans']}, 'mystery-collier')
    text = 'x' * 500100 + '\nACTOR original evidence'
    digest = hashlib.sha256(text.encode()).hexdigest()
    (tmp_path / 'sources' / (digest + '.txt')).write_text(text, encoding='utf8')
    db.put('source', {'title': 'Register', 'url': 'https://archive.org/test',
                      'sha256': digest, 'status': 'retrieved', 'text': text[:500000]}, 's')


@pytest.mark.anyio
async def test_research_loop_and_audit(isolated, monkeypatch):
    monkeypatch.setattr(assistant, 'complete', lambda *a: pytest.fail('MCP must not invoke a provider'))
    async with Client(create_server()) as client:
        catalogue = await client.list_tools()
        names = {t.name for t in catalogue.tools}
        assert {t['function']['name'] for t in assistant.TOOLS} <= names
        assert not names & {'configure', 'settings', 'execute', 'shell'}
        tool = next(t for t in catalogue.tools if t.name == 'save_research_note')
        assert tool.annotations.read_only_hint is False
        result = await client.call_tool('get_investigation', {})
        assert result.structured_content['site']['name'] == 'Test site'
        sources = (await client.call_tool('list_sources', {'limit': 1})).structured_content
        assert sources['total'] == 1 and 'text' not in sources['items'][0]
        source = await client.call_tool('get_saved_source', {'source_id': 's', 'offset': 500100})
        assert 'ACTOR' in source.structured_content['text']
        assert source.structured_content['next_offset'] is None
        search = await client.call_tool('search_source', {'source_id': 's', 'query': 'ACTOR'})
        assert search.structured_content['matches'][0]['character_offset'] == 500101
        note = await client.call_tool('save_research_note', {
            'subject': 'Actor', 'text': 'Tentative lead, register offset 500101.',
            'source_ids': ['s'], 'contradictions': ['Identity is unverified'],
        })
        assert note.structured_content['status'] == 'AI hypothesis; unreviewed'
        notes = await client.call_tool('list_research_notes')
        assert notes.structured_content['items'][0]['id'] == note.structured_content['id']
        report = await client.call_tool('get_report')
        assert 'Tentative lead' in report.structured_content['text']
        assert db.claims('mystery-collier') == []
        audit = db.all_records('job')
        assert all(j['kind'] == 'mcp' and j['status'] == 'complete' for j in audit)
        events = [e for e in db.events() if e['kind'] == 'tool']
        assert any(e['data']['name'] == 'save_research_note' for e in events)


@pytest.mark.anyio
async def test_invalid_tools_and_inputs_do_not_execute(isolated):
    async with Client(create_server()) as client:
        for name, args in [
            ('configure', {'key': 'DO-NOT-ECHO'}),
            ('read_source', {'url': 123}),
            ('get_saved_source', {'source_id': 's', 'limit': 18001}),
            ('list_sources', {'offset': -1}),
            ('start_analysis', {'dataset_id': 'x', 'method': 'shell'}),
            ('get_investigation', {'key': 'DO-NOT-ECHO'}),
        ]:
            result = await client.call_tool(name, args)
            assert result.is_error
            assert 'DO-NOT-ECHO' not in result.model_dump_json()
        assert db.all_records('job') == []
        for name, args in [
            ('read_source', {'url': 'http://127.0.0.1/secret'}),
            ('start_analysis', {'dataset_id': 'missing', 'method': 'residual'}),
            ('save_research_note', {'subject': 'X', 'text': 'Unsupported', 'source_ids': ['missing'], 'contradictions': []}),
        ]:
            assert (await client.call_tool(name, args)).is_error
        assert not db.all_records('research_note')
        assert all(j['status'] == 'failed' for j in db.all_records('job'))


@pytest.mark.anyio
async def test_archives_and_jobs_use_existing_services(isolated, monkeypatch):
    calls = []
    monkeypatch.setattr(connectors, 'search_archive', lambda **args: calls.append(args) or {'status': 'complete', 'results': []})
    monkeypatch.setattr(jobs.POOL, 'submit', lambda *a: None)
    db.put('dataset', {'name': 'Test grid'}, 'grid')
    async with Client(create_server()) as client:
        result = await client.call_tool('search_archive', {'query': 'coal schooner', 'archive': 'loc', 'from_year': 1880, 'to_year': 1900})
        assert not result.is_error and calls[0]['from_year'] == 1880
        queued = (await client.call_tool('start_analysis', {'dataset_id': 'grid', 'method': 'residual'})).structured_content
        assert queued['kind'] == 'analysis' and queued['status'] == 'queued'
        status = await client.call_tool('job_status', {'job_id': queued['id']})
        assert status.structured_content['args']['dataset_id'] == 'grid'
        cancelled = await client.call_tool('cancel_job', {'job_id': queued['id']})
        assert cancelled.structured_content['cancel_requested'] is True
        jobs.update(queued['id'], status='cancelled')
        resumed = await client.call_tool('resume_job', {'job_id': queued['id']})
        assert resumed.structured_content['status'] == 'queued'
        ai = db.put('job', {'kind': 'assistant', 'status': 'limited'}, 'ai')
        assert (await client.call_tool('resume_job', {'job_id': ai['id']})).is_error
        audit = await client.call_tool('start_evidence_audit', {'query': 'vessel register'})
        assert audit.structured_content['kind'] == 'research'
        mcp_job = next(j for j in db.all_records('job') if j['kind'] == 'mcp')
        with pytest.raises(ValueError, match='Retry MCP'):
            jobs.resume(mcp_job['id'])


@pytest.mark.anyio
async def test_unexpected_failures_are_redacted(isolated, monkeypatch):
    def fail(*args):
        raise RuntimeError('secret-provider-token')
    monkeypatch.setattr(assistant, 'execute', fail)
    async with Client(create_server()) as client:
        result = await client.call_tool('get_investigation')
        assert result.is_error and 'RuntimeError' in result.content[0].text
        assert 'secret-provider-token' not in json.dumps(db.events())


def test_mcp_audit_records_do_not_consume_worker_queue(isolated, monkeypatch):
    monkeypatch.setattr(jobs.POOL, 'submit', lambda *a: None)
    for i in range(12):
        db.put('job', {'kind': 'mcp', 'status': 'running'}, f'mcp-{i}')
    assert jobs.submit('research', {})['status'] == 'queued'
    jobs.recover()
    assert db.get('job', 'mcp-0')['status'] == 'interrupted'
    assert 'MCP client' in db.get('job', 'mcp-0')['message']


@pytest.fixture(scope='module')
def live_server(tmp_path_factory):
    root = Path(__file__).resolve().parents[1]
    temp = tmp_path_factory.mktemp('mcp-live')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'GHOSTFLEET_DATA': str(temp / 'data')}
    with (temp / 'server.log').open('w') as log:
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.main:app',
                                    '--host', '127.0.0.1', '--port', str(port)],
                                   cwd=root, env=env, stdout=log, stderr=log,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            url = f'http://127.0.0.1:{port}'
            for _ in range(100):
                try:
                    if httpx.get(url + '/api/health', timeout=.5, trust_env=False).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                if process.poll() is not None:
                    pytest.fail('Server exited: ' + (temp / 'server.log').read_text())
                time.sleep(.1)
            else:
                pytest.fail('Server failed to start')
            yield url, root
        finally:
            process.terminate()
            process.wait(timeout=15)


@pytest.mark.anyio
async def test_http_and_stdio_transports_share_app(live_server):
    url, root = live_server
    async with Client(url + '/mcp') as direct:
        http_tools = await direct.list_tools()
        assert len(http_tools.tools) >= 20
        assert not (await direct.call_tool('list_sources')).is_error
    # Absolute script path works even when a desktop host launches elsewhere.
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(root / 'mcp_stdio.py'), '--url', url + '/mcp'],
                                   cwd=root.parent)
    async with Client(params, read_timeout_seconds=30) as stdio:
        assert 'site_id' in stdio.instructions and 'list_investigations' in stdio.instructions
        tools = await stdio.list_tools()
        assert {t.name for t in tools.tools} == {t.name for t in http_tools.tools}
        assert not (await stdio.call_tool('list_sources')).is_error
        assert (await stdio.call_tool('get_saved_source', {'source_id': 'missing'})).is_error
    saved = httpx.get(url + '/api/jobs', trust_env=False).json()
    assert len(saved) == 3 and all(j['kind'] == 'mcp' for j in saved)
    assert sorted(j['status'] for j in saved) == ['complete', 'complete', 'failed']
    assert httpx.get(url + '/api/health', trust_env=False).json()['status'] == 'ok'


def test_http_rejects_foreign_hosts_and_origins(live_server):
    url, _ = live_server
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}
    headers = {'Accept': 'application/json, text/event-stream'}
    assert httpx.post(url + '/mcp', json=request, headers={**headers, 'Host': 'evil.example'}, trust_env=False).status_code == 400
    assert httpx.post(url + '/mcp', json=request, headers={**headers, 'Origin': 'https://evil.example'}, trust_env=False).status_code == 403


def test_legacy_protocol_initialization(live_server):
    url, _ = live_server
    headers = {'Accept': 'application/json, text/event-stream'}
    response = httpx.post(url + '/mcp', headers=headers, trust_env=False, json={
        'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2025-03-26', 'capabilities': {},
            'clientInfo': {'name': 'legacy-host', 'version': '1'},
        },
    })
    assert response.status_code == 200
    assert response.json()['result']['protocolVersion'] == '2025-03-26'
    headers['MCP-Protocol-Version'] = '2025-03-26'
    response = httpx.post(url + '/mcp', headers=headers, trust_env=False,
                          json={'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
    assert response.status_code == 200
    tools = response.json()['result']['tools']
    assert any(t['name'] == 'search_archive' and 'inputSchema' in t for t in tools)


def test_stdio_configuration_and_loopback_only():
    import argparse
    for url in ('https://remote.example/mcp', 'http://user:pass@localhost/mcp',
                'http://127.0.0.1:8787/mcp?key=secret', 'http://localhost:bad/mcp'):
        with pytest.raises(argparse.ArgumentTypeError):
            local_url(url)
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / 'mcp_stdio.py'), '--print-config'],
                            capture_output=True, text=True, check=True)
    config = json.loads(result.stdout)['mcpServers']['shipwreck-hunter']
    assert Path(config['command']).is_absolute()
    assert Path(config['args'][0]).is_absolute()

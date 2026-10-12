import httpx
import pytest

from backend import connectors, db


def test_current_noaa_discovery_empty_coverage_is_success(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DATA', tmp_path)
    db.init()
    seen = []

    def handler(request):
        seen.append(request)
        assert request.url.host == 'services2.arcgis.com'
        assert request.url.path.endswith('/NOS_Hydrographic_Survey_Data_view/FeatureServer/0/query')
        assert request.url.params['geometry'] == '-72.0,44.0,-71.5,44.5'
        return httpx.Response(200, json={'type': 'FeatureCollection', 'features': []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(connectors.httpx, 'Client', lambda **kwargs: client)
    result = connectors.discover_surveys([-72.0, 44.0, -71.5, 44.5])
    assert result['count'] == 0 and not result['truncated']
    assert len(seen) == 1 and db.all_records('survey') == []


@pytest.mark.parametrize('host', ['www.maine.gov', 'www1.maine.gov', 'www.mainememory.net', 'www.mooseheadhistory.org', 'www.katahdincruises.com'])
def test_maine_research_sources_are_supported_without_lookalikes(host):
    assert connectors.validate_url('https://' + host + '/document')
    with pytest.raises(ValueError):
        connectors.validate_url('https://' + host + '.example.org/document')
    with pytest.raises(ValueError):
        connectors.validate_url('http://' + host + '/document')

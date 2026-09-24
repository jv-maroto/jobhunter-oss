import socket

import pytest

from app.career import analysis, sources
from app.models.career_source import CareerSource
from tests.test_career_analysis import factory  # noqa: F401


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fd00::1", "224.0.0.1"])
def test_private_dns_blocked(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, (address, 443))])
    with pytest.raises(ValueError, match="públicas"):
        sources.public_addresses("example.com")


@pytest.mark.parametrize("url", ["http://example.com", "https://user:pass@example.com", "https://example.com:8000"])
def test_unsafe_urls_rejected(url):
    with pytest.raises(ValueError, match="HTTPS"):
        sources.fetch_public(url)


def test_redirect_not_followed(monkeypatch):
    calls = []
    class Response:
        status = 302
        def getheader(self, name, default=None):
            return None
    class Connection:
        def __init__(self, host, address):
            calls.append((host, address))
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            return Response()
        def close(self):
            pass
    monkeypatch.setattr(sources, "public_addresses", lambda host: ["8.8.8.8"])
    monkeypatch.setattr(sources, "PinnedHTTPSConnection", Connection)
    with pytest.raises(ValueError, match="redirecciones"):
        sources.fetch_public("https://example.com")
    assert calls == [("example.com", "8.8.8.8")]


def test_cached_source_content_changes_hash_not_fetch_date(factory):  # noqa: F811
    profile = {"personal": {"portfolio": "https://example.com/"}}
    with factory() as db:
        sources.store_source(db, "https://example.com/", "https://example.com/", "portfolio_html", "original")
        original = analysis.fingerprint(analysis.snapshot(profile, sources.cached_sources(db, profile)))
        sources.store_source(db, "https://example.com/", "https://example.com/", "portfolio_html", "original")
        assert original == analysis.fingerprint(analysis.snapshot(profile, sources.cached_sources(db, profile)))
        sources.store_source(db, "https://example.com/", "https://example.com/", "portfolio_html", "changed")
        assert original != analysis.fingerprint(analysis.snapshot(profile, sources.cached_sources(db, profile)))
        assert sources.cached_sources(db, {"personal": {"portfolio": "https://other.com"}}) == []


def test_portfolio_extracts_text_not_script_execution(factory, monkeypatch):  # noqa: F811
    monkeypatch.setattr(sources, "fetch_public_document", lambda url: ("<html><body>My Python projects " + "details " * 60 + "<script>evil()</script></body></html>", "text/html", url))
    with factory() as db:
        sources.refresh_portfolio(db, "https://example.com/")
        row = db.query(CareerSource).one()
        assert "My Python projects" in row.content_text
        assert "evil" not in row.content_text


def test_evidence_reports_truncation_and_source():
    source = analysis.snapshot({}, [{"url": "https://example.com/", "kind": "portfolio_html",
                                    "text": "x" * 4000, "content_hash": "x", "truncated": False}])
    evidence = analysis.evidence_inventory(source)
    assert evidence[0]["source"] == "https://example.com/"
    assert evidence[0]["truncated"] is True
    assert len(evidence[0]["value"]) == 3000



def test_portfolio_trailing_slash_preserved_and_script_join(factory, monkeypatch):  # noqa: F811
    owner = "https://jv-maroto.github.io/portafolio/"
    assert sources.owner_urls({"personal": {"portfolio": owner}}) == [owner]
    requested = []
    def fake_fetch(url):
        requested.append(url)
        if url == owner:
            return '<html><body><script src="assets/main.js"></script></body></html>', 'text/html'
        return 'const x="Portfolio project with a very long readable description";', 'text/javascript'
    monkeypatch.setattr(sources, "fetch_public", fake_fetch)
    monkeypatch.setattr(sources, "fetch_public_document", lambda url: (*fake_fetch(url), url))
    with factory() as db:
        sources.refresh_portfolio(db, owner)
    assert requested == [owner, "https://jv-maroto.github.io/portafolio/assets/main.js"]


def test_refresh_failure_retains_cached_evidence(factory, monkeypatch):  # noqa: F811
    profile = {"personal": {"portfolio": "https://example.com/"}}
    monkeypatch.setattr(sources, "SessionLocal", factory)
    def fail(url):
        raise ValueError("temporary network failure")
    monkeypatch.setattr(sources, "fetch_public_document", fail)
    with factory() as db:
        sources.store_source(db, "https://example.com/", "https://example.com/", "portfolio_html", "last good")
        original_hash = analysis.fingerprint(analysis.snapshot(profile, sources.cached_sources(db, profile)))
        sources.request_refresh(db)
    sources.run_refresh(profile)
    with factory() as db:
        cached = sources.cached_sources(db, profile)
        assert cached[0]["text"] == "last good"
        assert original_hash == analysis.fingerprint(analysis.snapshot(profile, cached))
        row = db.query(CareerSource).one()
        assert row.status == "failed" and row.active


def redirect_connection(monkeypatch, location):
    calls = []
    class Response:
        status = 301
        def getheader(self, name, default=None):
            return location if name == "Location" else default
    class Connection:
        def __init__(self, host, address):
            calls.append(host)
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            return Response()
        def close(self):
            pass
    monkeypatch.setattr(sources, "PinnedHTTPSConnection", Connection)
    return calls


def test_redirect_to_private_network_blocked(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, *a, **kw: [(None, None, None, None,
                        ("8.8.8.8" if host == "example.com" else "127.0.0.1", 443))])
    calls = redirect_connection(monkeypatch, "https://localhost/internal")
    with pytest.raises(ValueError, match="públicas"):
        sources.fetch_public("https://example.com/")
    assert calls == ["example.com"]


def test_redirect_loop_capped(monkeypatch):
    monkeypatch.setattr(sources, "public_addresses", lambda host: ["8.8.8.8"])
    calls = redirect_connection(monkeypatch, "/loop")
    with pytest.raises(ValueError, match="límite de redirecciones"):
        sources.fetch_public("https://example.com/")
    assert len(calls) == 4


def test_landing_url_resolves_spa_assets(factory, monkeypatch):  # noqa: F811
    owner = "https://jv-maroto.github.io/portafolio"
    requested = []
    monkeypatch.setattr(sources, "fetch_public_document", lambda url: (
        '<html><body><script src="assets/main.js"></script></body></html>', 'text/html', owner + '/'))
    def script(url):
        requested.append(url)
        return 'const x="Portfolio project with a very long readable description";', 'text/javascript'
    monkeypatch.setattr(sources, "fetch_public", script)
    with factory() as db:
        sources.refresh_portfolio(db, owner)
    assert requested == [owner + '/assets/main.js']


def test_directory_redirect_returns_canonical_landing(monkeypatch):
    paths = []
    validated = []
    class Response:
        def __init__(self, status):
            self.status = status
        def getheader(self, name, default=None):
            return {"Location": "/portafolio/", "Content-Type": "text/html"}.get(name, default)
        def read(self, limit):
            return b"<html>Portfolio</html>"
    class Connection:
        def __init__(self, host, address):
            pass
        def request(self, method, path, **kwargs):
            paths.append(path)
        def getresponse(self):
            return Response(301 if len(paths) == 1 else 200)
        def close(self):
            pass
    monkeypatch.setattr(sources, "PinnedHTTPSConnection", Connection)
    monkeypatch.setattr(sources, "public_addresses", lambda host: validated.append(host) or ["8.8.8.8"])
    result = sources.fetch_public_document("https://example.com/portafolio")
    assert result[2] == "https://example.com/portafolio/"
    assert paths == ["/portafolio", "/portafolio/"]
    assert validated == ["example.com", "example.com"]

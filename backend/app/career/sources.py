"""Explicit bounded public-source refresh; no URL execution or private network access."""
from __future__ import annotations

import base64
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
from datetime import datetime
from urllib.parse import quote, urljoin, urlsplit

from selectolax.parser import HTMLParser
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.career_source import CareerSource, CareerSourceRefresh

MAX_BYTES = 512_000
MAX_TEXT = 12_000


def public_addresses(host: str) -> list[str]:
    addresses = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(address).is_global
                            or ipaddress.ip_address(address).is_multicast
                            or ipaddress.ip_address(address).is_reserved for address in addresses):
        raise ValueError("La fuente no resuelve exclusivamente a direcciones públicas")
    return addresses


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str):
        super().__init__(host, timeout=12, context=ssl.create_default_context())
        self.address = address

    def connect(self) -> None:
        # Connect to the numeric address already checked; TLS still validates the
        # original hostname. No second DNS lookup and no DNS rebinding window.
        sock = socket.create_connection((self.address, 443), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def fetch_public_document(url: str) -> tuple[str, str, str]:
    """Follow at most three redirects, independently validating and pinning each hop."""
    for hop in range(4):
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.port not in (None, 443)):
            raise ValueError("Solo se admiten fuentes HTTPS públicas sin credenciales")
        addresses = public_addresses(parsed.hostname)
        connection = PinnedHTTPSConnection(parsed.hostname, addresses[0])
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        try:
            connection.request("GET", path, headers={"User-Agent": "Jobslave-Career/1.0",
                                                     "Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if hop == 3 or not location:
                    raise ValueError("La fuente supera el límite de redirecciones o no indica destino")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ValueError(f"Fuente no disponible (HTTP {response.status})")
            if response.getheader("Content-Encoding", "identity") != "identity":
                raise ValueError("Respuesta comprimida no admitida")
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("La fuente supera el límite de 512 KB")
            return data.decode("utf-8", errors="replace"), response.getheader("Content-Type", ""), url
        finally:
            connection.close()
    raise ValueError("Demasiadas redirecciones")


def fetch_public(url: str) -> tuple[str, str]:
    text, content_type, _ = fetch_public_document(url)
    return text, content_type


def owner_urls(profile: dict) -> list[str]:
    personal = profile.get("personal") or {}
    return list(dict.fromkeys(str(personal.get(key) or "").strip()
                             for key in ("github", "portfolio") if personal.get(key)))


def store_source(db: Session, owner: str, url: str, kind: str, text: str | None,
                 error: str | None = None) -> None:
    row = db.scalar(select(CareerSource).where(CareerSource.url == url))
    if row is None:
        row = CareerSource(url=url, owner_url=owner, kind=kind, status="failed")
        db.add(row)
    row.owner_url = owner
    row.active = True
    if not error or not row.content_text:
        row.kind = kind
    row.fetched_at = datetime.utcnow()
    row.error = error
    row.status = "failed" if error else "ready"
    if text is not None:
        row.truncated = len(text) > MAX_TEXT
        row.content_text = text[:MAX_TEXT]
        row.content_hash = hashlib.sha256(text.encode()).hexdigest()
    db.commit()


def refresh_portfolio(db: Session, owner: str) -> None:
    html, content_type, landing_url = fetch_public_document(owner)
    if "html" not in content_type:
        raise ValueError("El portafolio no devolvió HTML")
    tree = HTMLParser(html)
    scripts = [node.attributes.get("src", "") for node in tree.css("script[src]")]
    for node in tree.css("script, style, nav, footer"):
        node.decompose()
    text = tree.body.text(separator=" ", strip=True) if tree.body else tree.text()
    store_source(db, owner, owner, "portfolio_html", text)
    # SPAs often put portfolio copy in the entry bundle. Read a bounded same-origin
    # entry as inert strings, never evaluate JavaScript or fetch its dependencies.
    if len(text) < 300:
        for script in scripts[:2]:
            url = urljoin(landing_url, script)
            if urlsplit(url).netloc != urlsplit(landing_url).netloc:
                continue
            try:
                code, _ = fetch_public(url)
                literals = re.findall(r'["\']([^"\'\n]{35,500})["\']', code)
                text = "\n".join(dict.fromkeys(literals))
                if not text.strip():
                    raise ValueError("No se pudo extraer texto del script; requiere revisión manual")
                store_source(db, owner, url, "portfolio_script_strings", text)
            except Exception:
                store_source(db, owner, url, "portfolio_script_strings", None,
                             "No se pudo leer este recurso público dentro de los límites de seguridad y tamaño.")


def refresh_github(db: Session, owner: str) -> None:
    parsed = urlsplit(owner)
    parts = parsed.path.strip("/").split("/")
    if parsed.scheme != "https" or parsed.hostname != "github.com" or not re.fullmatch(r"[A-Za-z0-9-]{1,39}", parts[0]):
        raise ValueError("Guarda una URL de perfil https://github.com/usuario válida")
    username = parts[0]
    raw, _ = fetch_public(f"https://api.github.com/users/{username}/repos?per_page=30&sort=pushed&type=owner")
    repos = json.loads(raw)
    if not isinstance(repos, list):
        raise ValueError("Respuesta de repositorios no válida")
    repos = [r for r in repos if not r.get("fork") and not r.get("archived")][:4]
    for repo in repos:
        full_name = str(repo.get("full_name", ""))
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", full_name):
            continue
        repo_url = "https://github.com/" + full_name
        store_source(db, owner, repo_url, "github_metadata", json.dumps({key: repo.get(key) for key in
                     ("full_name", "description", "language", "topics", "pushed_at", "html_url")}, ensure_ascii=False))
        # README plus repository tree tells us which small manifests exist,
        # avoiding a request per guessed filename and a large crawler.
        for path, kind in (("readme", "github_readme"), ("contents/", "github_tree")):
            url = f"https://api.github.com/repos/{full_name}/{path}"
            try:
                body, _ = fetch_public(url)
                data = json.loads(body)
                if kind == "github_readme":
                    if data.get("encoding") != "base64":
                        raise ValueError("README no disponible como texto")
                    text = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
                    store_source(db, owner, url, kind, text)
                else:
                    if not isinstance(data, list):
                        raise ValueError("Árbol no disponible")
                    store_source(db, owner, url, kind, json.dumps([{"name": d.get("name"), "type": d.get("type")} for d in data]))
                    manifests = [d for d in data if d.get("name") in {"pyproject.toml", "package.json", "requirements.txt", "Cargo.toml", "go.mod"}][:2]
                    for manifest in manifests:
                        manifest_url = f"https://api.github.com/repos/{full_name}/contents/{quote(manifest['name'])}"
                        try:
                            content, _ = fetch_public(manifest_url)
                            encoded = json.loads(content)
                            text = base64.b64decode(encoded["content"]).decode("utf-8", errors="replace")
                            store_source(db, owner, manifest_url, "github_manifest", text)
                        except Exception:
                            store_source(db, owner, manifest_url, "github_manifest", None, "Manifiesto no disponible.")
            except Exception:
                store_source(db, owner, url, kind, None, "Recurso de GitHub no disponible o demasiado grande.")


def request_refresh(db: Session) -> bool:
    row = db.get(CareerSourceRefresh, 1)
    if row is None:
        db.add(CareerSourceRefresh(id=1, status="running", started_at=datetime.utcnow()))
        try:
            db.commit()
            return False
        except IntegrityError:
            db.rollback()
            return True
    changed = db.execute(update(CareerSourceRefresh).where(CareerSourceRefresh.id == 1,
                         CareerSourceRefresh.status != "running").values(status="running",
                         started_at=datetime.utcnow(), finished_at=None, error=None))
    db.commit()
    return not bool(changed.rowcount)


def run_refresh(profile: dict) -> None:
    with SessionLocal() as db:
        run = db.get(CareerSourceRefresh, 1)
        failed = False
        try:
            owners = owner_urls(profile)
            if not owners:
                raise ValueError("Añade las URLs de GitHub o portafolio a tu perfil")
            for owner in owners:
                try:
                    if urlsplit(owner).hostname == "github.com":
                        refresh_github(db, owner)
                    else:
                        refresh_portfolio(db, owner)
                    db.execute(update(CareerSource).where(CareerSource.owner_url == owner,
                               CareerSource.fetched_at < run.started_at).values(active=False))
                    db.commit()
                except Exception:
                    failed = True
                    db.execute(update(CareerSource).where(CareerSource.owner_url == owner).values(
                        active=True, status="failed", error="Actualización fallida; se conserva la última lectura disponible."))
                    db.commit()
                    store_source(db, owner, owner, "source", None,
                                 "No se pudo actualizar la fuente. Comprueba que sea una URL HTTPS pública, accesible y con redirecciones a destinos públicos.")
            failed = failed or bool(db.scalar(select(CareerSource.id).where(
                CareerSource.owner_url.in_(owners), CareerSource.active.is_(True),
                CareerSource.status == "failed").limit(1)))
            run.status = "completed"
            run.error = "Algunas fuentes no se pudieron actualizar; revisa su estado." if failed else None
        except Exception:
            run.status = "failed"
            run.error = "No se pudieron actualizar las fuentes. Añade URLs públicas válidas en el perfil."
        run.finished_at = datetime.utcnow()
        db.commit()


def cached_sources(db: Session, profile: dict) -> list[dict]:
    owners = owner_urls(profile)
    rows = db.scalars(select(CareerSource).where(CareerSource.owner_url.in_(owners),
                      CareerSource.active.is_(True), CareerSource.content_text.is_not(None)).order_by(CareerSource.url)).all()
    return [{"url": row.url, "kind": row.kind, "content_hash": row.content_hash,
             "text": row.content_text, "truncated": row.truncated} for row in rows]


def recover_source_refresh() -> None:
    with SessionLocal() as db:
        db.execute(update(CareerSourceRefresh).where(CareerSourceRefresh.status == "running")
                   .values(status="interrupted", finished_at=datetime.utcnow(),
                           error="Actualización interrumpida por reinicio. Puedes reintentarla."))
        db.commit()

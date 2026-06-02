#!/usr/bin/env python3
"""
_agent_tools_auth.py — Unified cookie/auth loading for Agent Tools MCP plugins.

This file is self-contained (no imports from other project files) and is
distributed to each plugin directory by scripts/sync-auth.sh.

Public API:
  get_cookies(service)        -> dict[str, str]
  refresh_cookies(service)    -> dict[str, str]
  get_devctl_password()       -> str
  refresh_all_cookies()       -> dict[str, dict[str, str]]
"""

import asyncio
import json
import logging
import os
import socket
import subprocess
import tempfile
import time
import urllib.request
from typing import Optional

log = logging.getLogger("agent-tools-auth")

# ── Service registry ─────────────────────────────────────────────────────────

SERVICE_DOMAINS: dict[str, str] = {
    "kconf":      "kconf.corp.kuaishou.com",
    "abtest":     "abtest-sgp.corp.kuaishou.com",
    "graytool":   "ad-env.corp.kuaishou.com",
    "kaiworks":   "kaiworks.corp.kuaishou.com",
    "kaiserving": "kaiserving.corp.kuaishou.com",
    "kwaibi":     "kwaibi.corp.kuaishou.com",
    "docs":       "docs.corp.kuaishou.com",
    "webshell":   "kaiworks.corp.kuaishou.com",
}

CACHE_TTL = 24 * 3600  # seconds


def _find_project_root(start: str) -> Optional[str]:
    """Walk up from `start` looking for a Agent Tools project root marker.

    Project root is identified by the presence of any of: .agent-tools/,
    .claude-plugin/, CLAUDE.md, or .git. Used as a fallback when neither
    AGENT_TOOLS_PROJECT_DIR nor CLAUDE_PROJECT_DIR is set (e.g. under Gemini CLI
    or Codex CLI, which don't export CLAUDE_PROJECT_DIR).
    """
    d = os.path.abspath(start)
    for _ in range(10):
        if any(os.path.exists(os.path.join(d, m)) for m in (".agent-tools", ".claude-plugin", "CLAUDE.md", ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    return None


_PROJECT_ROOT = (
    os.environ.get("AGENT_TOOLS_PROJECT_DIR")
    or os.environ.get("CLAUDE_PROJECT_DIR")
    or _find_project_root(os.path.dirname(os.path.abspath(__file__)))
    or ""
)

# Probe order for the cookie cache. Writes go to the first viable path; reads
# try all in order. The canonical location is .agent-tools/cookies_cache.json inside
# the project (CLI-neutral). .claude/cookies_cache.json is kept as a read
# fallback for backward compatibility with pre-migration caches.
_CACHE_PATHS = [p for p in (
    os.path.join(_PROJECT_ROOT, ".agent-tools", "cookies_cache.json") if _PROJECT_ROOT else None,
    os.path.join(_PROJECT_ROOT, ".claude", "cookies_cache.json") if _PROJECT_ROOT else None,
    os.path.expanduser("~/.claude/cookies_cache.json"),
) if p]

_DEVCTL_PASSWORD_CACHE = "/tmp/webshell_devctl_pw.json"
_DEVCTL_PASSWORD_TTL = 3600
_DEVCTL_PASSWORD_URL = "https://halo.corp.kuaishou.com/api/dev/v2/user/password/"

# CDP connects to 127.0.0.1; skip any localhost proxy.
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


# ── Cache helpers ────────────────────────────────────────────────────────────

def _read_cache() -> dict:
    for path in _CACHE_PATHS:
        if path and os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def _write_cache(data: dict) -> None:
    for path in _CACHE_PATHS:
        if not path:
            continue
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f)
            return
        except Exception:
            continue


def _cache_lookup(service: str) -> Optional[dict[str, str]]:
    """Return cached cookies if present and within TTL, else None."""
    cache = _read_cache()
    entry = cache.get(service)
    if not entry or not isinstance(entry, dict):
        return None
    # New format: {"cookies": {...}, "ts": float}
    # Old format (no "ts"): treat as expired
    ts = entry.get("ts")
    if ts is None:
        return None
    if time.time() - ts > CACHE_TTL:
        return None
    cookies = entry.get("cookies")
    if not cookies or not isinstance(cookies, dict):
        return None
    return cookies


def _cache_write(service: str, cookies: dict[str, str]) -> None:
    cache = _read_cache()
    cache[service] = {"cookies": cookies, "ts": time.time()}
    _write_cache(cache)


# ── Env var helpers ──────────────────────────────────────────────────────────

def _parse_raw_cookie_string(raw: str) -> dict[str, str]:
    """Parse 'k=v; k2=v2' cookie string into a dict."""
    result = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            result[k.strip()] = v.strip()
    return result


def _env_lookup(service: str) -> Optional[dict[str, str]]:
    """Return cookies from env var, or None if not set."""
    env_key = f"{service.upper()}_COOKIES"
    raw = os.environ.get(env_key, "")
    if raw:
        return json.loads(raw)
    # docs also supports DOCS_COOKIE (raw cookie string)
    if service == "docs":
        raw_str = os.environ.get("DOCS_COOKIE", "")
        if raw_str:
            return _parse_raw_cookie_string(raw_str)
    return None


# ── browser_cookie3 helpers ──────────────────────────────────────────────────

def _browser_cookie3_lookup(service: str) -> dict[str, str]:
    """Extract cookies from Chrome via browser_cookie3 with 3 retries.

    Queries exact service domain first, then merges parent .kuaishou.com
    domain without overwriting (parent carries SSO tokens).
    """
    import browser_cookie3

    domain = SERVICE_DOMAINS[service]
    parent_domain = ".kuaishou.com"

    last_exc: Optional[Exception] = None
    for attempt in range(3):
        try:
            cookies: dict[str, str] = {}
            for c in browser_cookie3.chrome(domain_name=domain):
                cookies[c.name] = c.value
            # Merge parent domain (SSO) without overwriting service-specific cookies
            try:
                for c in browser_cookie3.chrome(domain_name=parent_domain):
                    cookies.setdefault(c.name, c.value)
            except Exception:
                pass
            if cookies:
                return cookies
            log.warning("browser_cookie3 returned 0 cookies (attempt %d)", attempt + 1)
        except Exception as exc:
            last_exc = exc
            log.warning("browser_cookie3 failed (attempt %d): %s", attempt + 1, exc)
        if attempt < 2:
            time.sleep(1)

    raise RuntimeError(
        f"browser_cookie3 failed for {service} after 3 attempts: {last_exc}"
    )


# ── Public API ───────────────────────────────────────────────────────────────

def get_cookies(service: str) -> dict[str, str]:
    """Return cookies for a service, trying cache → env var → browser_cookie3."""
    if service not in SERVICE_DOMAINS:
        raise ValueError(f"Unknown service: {service!r}. Known: {list(SERVICE_DOMAINS)}")

    # 1. Cache
    cached = _cache_lookup(service)
    if cached is not None:
        return cached

    # 2. Env var
    env = _env_lookup(service)
    if env is not None:
        return env

    # 3. browser_cookie3 — write back to cache on success
    cookies = _browser_cookie3_lookup(service)
    _cache_write(service, cookies)
    return cookies


def refresh_cookies(service: str) -> dict[str, str]:
    """Force-fetch fresh cookies from browser_cookie3, update cache, and return."""
    if service not in SERVICE_DOMAINS:
        raise ValueError(f"Unknown service: {service!r}. Known: {list(SERVICE_DOMAINS)}")

    # Env var takes precedence even on refresh (CI/non-desktop environments)
    env = _env_lookup(service)
    if env is not None:
        return env

    cookies = _browser_cookie3_lookup(service)
    _cache_write(service, cookies)
    return cookies


def refresh_all_cookies() -> dict[str, dict[str, str]]:
    """Refresh cookies for all known services. Returns {service: cookies} map."""
    results: dict[str, dict[str, str]] = {}
    for service in SERVICE_DOMAINS:
        try:
            results[service] = refresh_cookies(service)
        except Exception as exc:
            log.warning("refresh_cookies(%s) failed: %s", service, exc)
    return results


# ── devctl password ──────────────────────────────────────────────────────────

def _detect_chrome() -> str:
    import shutil, sys
    mac_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    linux_names = ["google-chrome-stable", "google-chrome", "chromium", "chromium-browser"]
    candidates = (mac_paths + linux_names) if sys.platform == "darwin" else (linux_names + mac_paths)
    for c in candidates:
        p = shutil.which(c)
        if p:
            return p
        if os.path.isfile(c):
            return c
    raise RuntimeError(
        f"Chrome/Chromium not found. Set CHROME_PATH env var. Tried: {candidates}"
    )


CHROME_PATH = os.environ.get("CHROME_PATH") or _detect_chrome()


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _launch_chrome_headless(port: int):
    user_data_dir = tempfile.mkdtemp(prefix="agent-tools-auth-chrome-")
    args = [
        CHROME_PATH,
        "--headless=new",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "--ignore-certificate-errors",
        "--no-proxy-server",
        "about:blank",
    ]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        time.sleep(0.3)
        try:
            _NO_PROXY_OPENER.open(f"http://127.0.0.1:{port}/json/version", timeout=2)
            return proc
        except Exception:
            if proc.poll() is not None:
                raise RuntimeError(f"Chrome exited with code {proc.returncode}")
    proc.kill()
    raise RuntimeError("Chrome headless failed to start within 30 seconds")


async def _cdp_send(ws, method: str, params: Optional[dict] = None, timeout: int = 30):
    if not hasattr(_cdp_send, "_id"):
        _cdp_send._id = 0
    _cdp_send._id += 1
    msg_id = _cdp_send._id

    msg: dict = {"id": msg_id, "method": method}
    if params:
        msg["params"] = params
    await ws.send(json.dumps(msg))

    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            raise TimeoutError(f"CDP command {method} timed out")
        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        resp = json.loads(raw)
        if resp.get("id") == msg_id:
            if "error" in resp:
                raise RuntimeError(f"CDP error: {resp['error']}")
            return resp.get("result", {})


async def _fetch_devctl_password_direct() -> Optional[str]:
    """Try direct HTTP with browser SSO cookies (no CDP). Fast path."""
    import requests

    try:
        import browser_cookie3
        cookies: dict[str, str] = {}
        for domain in ["sso.corp.kuaishou.com", "halo.corp.kuaishou.com", ".kuaishou.com"]:
            try:
                for c in browser_cookie3.chrome(domain_name=domain):
                    cookies.setdefault(c.name, c.value)
            except Exception:
                pass

        session = requests.Session()
        session.cookies.update(cookies)
        resp = session.get(
            _DEVCTL_PASSWORD_URL,
            allow_redirects=True,
            timeout=10,
            verify=False,
        )
        if resp.status_code == 200:
            data = resp.json()
            pw = data.get("data", {}).get("password")
            if pw:
                return pw
    except Exception as exc:
        log.debug("Direct HTTP devctl password fetch failed: %s", exc)
    return None


async def _fetch_devctl_password_cdp() -> str:
    """Chrome CDP fallback: inject cookies, navigate to password API, read response."""
    import websockets

    port = _find_free_port()
    chrome_proc = _launch_chrome_headless(port)
    try:
        with _NO_PROXY_OPENER.open(f"http://127.0.0.1:{port}/json", timeout=5) as resp:
            tabs = json.loads(resp.read().decode())
        ws_url = [t for t in tabs if t.get("type") == "page"][0]["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=10 * 1024 * 1024, proxy=None) as ws:
            await _cdp_send(ws, "Network.enable")

            import browser_cookie3
            for cdomain, curl in [
                ("sso.corp.kuaishou.com", "https://sso.corp.kuaishou.com/cas/"),
                ("halo.corp.kuaishou.com", "https://halo.corp.kuaishou.com/"),
                (".kuaishou.com", "https://halo.corp.kuaishou.com/"),
            ]:
                try:
                    for c in browser_cookie3.chrome(domain_name=cdomain):
                        await _cdp_send(ws, "Network.setCookie", {
                            "name": c.name, "value": c.value, "url": curl,
                        })
                except Exception:
                    pass

            await _cdp_send(ws, "Page.navigate", {"url": _DEVCTL_PASSWORD_URL})
            for _ in range(30):
                await asyncio.sleep(0.5)
                try:
                    result = await _cdp_send(ws, "Runtime.evaluate", {
                        "expression": "document.body.innerText",
                        "returnByValue": True,
                    }, timeout=5)
                    body = result.get("result", {}).get("value", "")
                    if "password" in body:
                        data = json.loads(body)
                        return data["data"]["password"]
                except Exception:
                    continue
            raise RuntimeError("Failed to get devctl password from halo via CDP")
    finally:
        chrome_proc.kill()
        chrome_proc.wait()


def get_devctl_password() -> str:
    """Get devctl password. Checks cache (1h TTL), tries direct HTTP, falls back to CDP."""
    if os.path.exists(_DEVCTL_PASSWORD_CACHE):
        try:
            with open(_DEVCTL_PASSWORD_CACHE) as f:
                cached = json.load(f)
            if time.time() - cached["ts"] < _DEVCTL_PASSWORD_TTL:
                return cached["password"]
        except Exception:
            pass

    async def _fetch():
        pw = await _fetch_devctl_password_direct()
        if pw:
            return pw
        return await _fetch_devctl_password_cdp()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            password = pool.submit(asyncio.run, _fetch()).result()
    else:
        password = asyncio.run(_fetch())

    with open(_DEVCTL_PASSWORD_CACHE, "w") as f:
        json.dump({"password": password, "ts": time.time()}, f)

    return password

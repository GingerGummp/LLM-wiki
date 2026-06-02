#!/usr/bin/env python3
"""
Docs MCP Server
===============
Read/write/search Kuaishou internal Docs pages.

Tools:
  - docs_read   : fetch a doc URL, return clean text content (via Chrome headless + CDP)
  - docs_write  : create or update a doc from a local Markdown file (via REST API)
  - docs_search : search docs by keyword with filters (type, owner, interaction, etc.)

Cookie resolution (priority order):
  1. DOCS_COOKIES env var  — JSON dict  e.g. '{"ks_fid":"abc","kpf":"PC_WEB"}'
  2. DOCS_COOKIE  env var  — raw cookie string
  3. browser_cookie3       — auto-extract from Chrome (zero-config if logged in)

Chrome:
  Uses Chrome headless (launched automatically) for docs_read.
  Set CHROME_PATH env var if Chrome is not at the default macOS location.

Setup:
  pip install mcp websockets browser-cookie3 requests

Run:
  python docs_mcp_server.py
"""

import asyncio
import base64
import json
import logging
import os
import re
import ssl
import subprocess
import sys
import tempfile
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

import requests as _requests
import websockets
from markdownify import markdownify as md
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format="%(asctime)s [docs-mcp] %(levelname)s %(message)s")
log = logging.getLogger("docs-mcp")

BASE_URL = "https://docs.corp.kuaishou.com"
CHROME_DEBUG_PORT = int(os.environ.get("CHROME_DEBUG_PORT", "0"))  # 0 = auto-pick free port
def _detect_chrome() -> str:
    """Auto-detect Chrome/Chromium binary path across platforms."""
    import shutil
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

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


# ── Cookie resolution ──────────────────────────────────────────────────────────

def _load_cookie() -> str:
    """Return a cookie string for docs.corp.kuaishou.com."""
    from _agent_tools_auth import get_cookies
    cookies = get_cookies("docs")
    if cookies:
        return "; ".join(f"{k}={v}" for k, v in cookies.items())
    return ""


# ── HTTP helpers (for meta/title API) ─────────────────────────────────────────

def _request(url: str, cookie: str, method: str = "GET",
             data: Optional[dict] = None) -> dict:
    import gzip
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Cookie": cookie,
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/home",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "locale": "zh-CN",
    }
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
            raw = resp.read()
            if raw[:2] == b'\x1f\x8b':
                raw = gzip.decompress(raw)
            return json.loads(raw.decode())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise RuntimeError("Authentication failed — cookie may be expired")
        raise RuntimeError(f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


def _parse_doc_id(url: str) -> Optional[str]:
    patterns = [
        r'/(?:d|k|s)/home/(?:[^/]+/)?(fc[A-Za-z0-9_-]+)',
        r'docId=(fc[A-Za-z0-9_-]+)',
        r'/(fc[A-Za-z0-9_-]+)(?:\?|#|$)',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def _get_meta(doc_id: str, cookie: str) -> dict:
    r = _request(f"{BASE_URL}/merlot/api/docs/cosmo/meta/{doc_id}?um=false",
                 cookie, "POST", {})
    if r.get("code") != 0:
        raise RuntimeError(f"Meta API error: {r.get('message')}")
    return r.get("result", {})


# ── CDP-based reader ──────────────────────────────────────────────────────────

# JS: trigger select-all, then read text/html (with links) from clipboardContentProvider
# Falls back to text/plain if text/html is not available.
_EXTRACT_JS = """
(function() {
    var app = window.vodkaapp;
    if (!app) return { error: 'vodkaapp not found' };

    // Trigger select-all via the editor action API
    var ea = window.Docs && window.Docs.Word && window.Docs.Word.editorAction;
    if (ea && ea.selectAll) {
        ea.focusEditor();
        ea.selectAll();
    } else {
        return { error: 'editorAction.selectAll not found' };
    }

    // Read the formatted text from clipboardContentProvider
    var ccp = app.clipboardContentProvider;
    if (!ccp) return { error: 'clipboardContentProvider not found' };
    var clips = ccp.getClips();
    if (!clips) return { error: 'getClips returned null' };

    // Vodka editor uses 'text/x-+h' (not 'text/html') for its HTML clip.
    // Fall back to text/plain if neither HTML format is available.
    var htmlClip = null;
    var textClip = null;
    for (var i = 0; i < clips.length; i++) {
        var mime = clips[i].mimeType_;
        if (mime === 'text/x-+h' || mime === 'text/html') {
            htmlClip = clips[i].data_;
        } else if (mime === 'text/plain') {
            textClip = clips[i].data_;
        }
    }
    if (htmlClip) {
        return { html: htmlClip, length: htmlClip.length };
    }
    if (textClip) {
        return { text: textClip, length: textClip.length };
    }
    return { error: 'no HTML or text/plain clip found' };
})()
"""


def _html_to_markdown(html: str) -> str:
    """Convert HTML from Vodka editor clipboard to markdown, preserving links."""
    text = md(html, heading_style="ATX", bullets="-", strip=["script", "style"])
    # Clean up excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


_IMG_URL_RE = re.compile(r'!\[[^\]]*\]\((https?://[^)]+)\)')


def _extract_image_urls(md_text: str) -> list[str]:
    """Extract image URLs from markdown ![alt](url) syntax."""
    return _IMG_URL_RE.findall(md_text)


def _download_image(
    url: str, cookie: str, max_bytes: int = 5 * 1024 * 1024
) -> tuple[bytes, str] | None:
    """Download an image, return (raw_bytes, mime_type) or None on failure."""
    try:
        req = urllib.request.Request(url, headers={
            "Cookie": cookie,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        })
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
            urllib.request.ProxyHandler({}),
        )
        with opener.open(req, timeout=15) as resp:
            ctype = resp.headers.get("Content-Type", "image/png").split(";")[0].strip()
            data = resp.read(max_bytes + 1)
            if len(data) > max_bytes:
                log.warning(f"Image too large ({len(data)} bytes), skip: {url[:80]}")
                return None
            if not ctype.startswith("image/"):
                ctype = "image/png"
            return data, ctype
    except Exception as e:
        log.warning(f"Image download failed ({url[:80]}): {e}")
        return None


def _find_free_port() -> int:
    """Find a free TCP port."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _launch_chrome_headless(port: int) -> subprocess.Popen:
    """Launch Chrome in headless mode with a debug port."""
    user_data_dir = tempfile.mkdtemp(prefix="docs-mcp-chrome-")
    args = [
        CHROME_PATH,
        "--headless=new",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "--no-sandbox",
        "--ignore-certificate-errors",
        "about:blank",
    ]
    stderr_file = tempfile.NamedTemporaryFile(prefix="chrome-stderr-", suffix=".log", delete=False)
    proc = subprocess.Popen(
        args, stdout=subprocess.DEVNULL, stderr=stderr_file
    )
    # Bypass proxy for localhost connections to Chrome debug port
    no_proxy_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(30):
        time.sleep(0.3)
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/json/version")
            no_proxy_opener.open(req, timeout=2)
            log.info(f"Chrome headless started on port {port}, pid={proc.pid}")
            stderr_file.close()
            os.unlink(stderr_file.name)
            return proc
        except Exception:
            if proc.poll() is not None:
                stderr_file.close()
                with open(stderr_file.name, errors="replace") as f:
                    stderr = f.read()[:500]
                os.unlink(stderr_file.name)
                raise RuntimeError(f"Chrome exited with code {proc.returncode}: {stderr}")
    proc.kill()
    stderr_file.close()
    with open(stderr_file.name, errors="replace") as f:
        stderr = f.read()[:500]
    os.unlink(stderr_file.name)
    raise RuntimeError(f"Chrome headless failed to start within 9 seconds: {stderr}")


async def _cdp_send(ws, method: str, params: dict = None, timeout: float = 30) -> dict:
    """Send a CDP command and wait for the response."""
    if not hasattr(_cdp_send, '_id'):
        _cdp_send._id = 0
    _cdp_send._id += 1
    msg_id = _cdp_send._id

    msg = {"id": msg_id, "method": method}
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


async def _read_via_cdp(url: str, cookie_str: str) -> str:
    """Launch Chrome headless, open doc via CDP, extract formatted text."""
    port = CHROME_DEBUG_PORT or _find_free_port()
    chrome_proc = _launch_chrome_headless(port)

    try:
        # Get the initial blank page tab's websocket URL (skip extension targets)
        no_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(f"http://127.0.0.1:{port}/json")
        with no_proxy.open(req, timeout=5) as resp:
            tabs = json.loads(resp.read().decode())
        pages = [t for t in tabs if t.get("type") == "page"]
        if not pages:
            raise RuntimeError("No page target found in Chrome")
        ws_url = pages[0]["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024, proxy=None) as ws:
            await _cdp_send(ws, "Page.enable")
            await _cdp_send(ws, "Network.enable")
            await _cdp_send(ws, "Runtime.enable")

            # Set cookies before navigation
            if cookie_str:
                for pair in cookie_str.split("; "):
                    if "=" in pair:
                        name, value = pair.split("=", 1)
                        await _cdp_send(ws, "Network.setCookie", {
                            "name": name.strip(),
                            "value": value.strip(),
                            "domain": ".corp.kuaishou.com",
                            "path": "/",
                        })

            # Set a large viewport so the editor renders more content
            await _cdp_send(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 1920,
                "height": 10000,
                "deviceScaleFactor": 1,
                "mobile": False,
            })

            # Navigate to the doc URL
            await _cdp_send(ws, "Page.navigate", {"url": url})

            # Wait for Vodka editor to initialize
            for _ in range(60):
                await asyncio.sleep(0.5)
                try:
                    check = await _cdp_send(ws, "Runtime.evaluate", {
                        "expression": "!!(window.vodkaapp && window.vodkaapp.currentModelState_)",
                        "returnByValue": True,
                    }, timeout=5)
                    if check.get("result", {}).get("value") is True:
                        break
                except Exception:
                    continue
            else:
                raise RuntimeError("Timed out waiting for Vodka editor to initialize")

            # Wait for content to fully load (word count stabilizes)
            last_count = 0
            for _ in range(20):
                await asyncio.sleep(0.5)
                try:
                    wc = await _cdp_send(ws, "Runtime.evaluate", {
                        "expression": "window.Docs.Word.editorAction.getWordCount().documentCharCount",
                        "returnByValue": True,
                    }, timeout=5)
                    count = wc.get("result", {}).get("value", 0)
                    if count > 0 and count == last_count:
                        break
                    last_count = count
                except Exception:
                    continue

            # Select all + extract content via clipboardContentProvider
            result = await _cdp_send(ws, "Runtime.evaluate", {
                "expression": _EXTRACT_JS,
                "returnByValue": True,
            })
            data = result.get("result", {}).get("value", {})
            if not isinstance(data, dict):
                raise RuntimeError(f"Unexpected result type: {type(data)}")
            if "error" in data:
                raise RuntimeError(f"Extraction failed: {data['error']}")

            # Prefer HTML (preserves links) → convert to markdown
            if "html" in data:
                return _html_to_markdown(data["html"])
            return data["text"].strip()
    finally:
        chrome_proc.kill()
        chrome_proc.wait()


# ── Public API ─────────────────────────────────────────────────────────────────

def read_doc(url: str) -> str:
    """Fetch a Kuaishou Docs page and return its content as formatted text."""
    cookie = _load_cookie()
    if not cookie:
        raise RuntimeError(
            "No cookie available. Options:\n"
            "  1. Set DOCS_COOKIES env var (JSON dict)\n"
            "  2. Set DOCS_COOKIE env var (raw string)\n"
            "  3. Log in to docs.corp.kuaishou.com in Chrome (auto-extracted)"
        )

    doc_id = _parse_doc_id(url)
    if not doc_id:
        raise ValueError(f"Cannot parse doc ID from URL: {url}")

    # Get title via meta API
    meta = _get_meta(doc_id, cookie)
    title = meta.get("docName", "Untitled")

    # Read content via Chrome headless + CDP
    log.info(f"Reading doc via Chrome headless: {doc_id}")
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            text = pool.submit(
                asyncio.run, _read_via_cdp(url, cookie)
            ).result()
    else:
        text = asyncio.run(_read_via_cdp(url, cookie))
    if not text or len(text) < 50:
        raise RuntimeError("CDP returned insufficient content — page may require login or failed to load")

    log.info(f"Got {len(text)} chars for '{title}'")
    return f"# {title}\n\n> Source: {url}\n\n{text}"


# ── Session-based API client (for write operations) ─────────────────────────

def _get_session() -> "_requests.Session":
    """Create a requests.Session with browser cookies (like kwaibi approach)."""
    session = _requests.Session()
    session.verify = False
    session.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/home",
        "locale": "zh-CN",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    })

    # Cookie resolution (same priority as _load_cookie)
    raw = os.environ.get("DOCS_COOKIES", "")
    if raw:
        session.cookies.update(json.loads(raw))
        return session
    raw = os.environ.get("DOCS_COOKIE", "")
    if raw:
        for pair in raw.split("; "):
            if "=" in pair:
                k, v = pair.split("=", 1)
                session.cookies.set(k.strip(), v.strip())
        return session
    try:
        import browser_cookie3
        cj = browser_cookie3.chrome(domain_name="docs.corp.kuaishou.com")
        session.cookies.update({c.name: c.value for c in cj})
        log.info(f"Session: auto-extracted {len(session.cookies)} cookies from Chrome")
    except Exception as e:
        log.warning(f"browser_cookie3 failed: {e}")

    return session


def _session_post(session: "_requests.Session", path: str, data: dict = None,
                  add_um: bool = True) -> dict:
    url = f"{BASE_URL}{path}"
    if add_um:
        sep = "&" if "?" in url else "?"
        if "um=" not in url:
            url += f"{sep}um=false"
    resp = session.post(url, json=data or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _session_get(session: "_requests.Session", path: str) -> dict:
    url = f"{BASE_URL}{path}"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def write_doc(file_path: str, doc_url: str = "", update: bool = False) -> str:
    """Create or update a Kuaishou Docs page from a local Markdown file.

    Args:
        file_path: path to the local .md file
        doc_url: if updating, the existing doc URL; if empty, creates a new doc
        update: if True and doc_url is set, delete the old doc first

    Returns:
        A summary string with the resulting doc URL.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not path.suffix.lower() == ".md":
        raise ValueError("Only .md files are supported")

    session = _get_session()

    # Strip YAML front-matter
    content_text = path.read_text(encoding="utf-8")
    if content_text.startswith("---\n"):
        end = content_text.find("\n---\n", 4)
        if end != -1:
            content_text = content_text[end + 5:].lstrip('\n')

    filename = path.name
    content = content_text.encode("utf-8")

    # If updating, delete old doc first
    parent_id = ""
    if update and doc_url:
        old_id = _parse_doc_id(doc_url)
        if old_id:
            try:
                meta = _session_post(session, f"/merlot/api/docs/cosmo/meta/{old_id}?um=false", {})
                if meta.get("code") == 0:
                    shortcut_id = meta.get("result", {}).get("shortcutId")
                    if shortcut_id:
                        _session_post(session, "/merlot/api/recycle-bins/delete-shortcuts",
                                      {"shortcutIds": [shortcut_id], "strategy": "recursive"})
                        log.info(f"Deleted old doc: {old_id}")
            except Exception as e:
                log.warning(f"Failed to delete old doc {old_id}: {e}")

    # 1. Get upload token
    token_resp = _session_post(session, "/merlot/api/docs/yfile/v2/upload", {
        "fileName": filename,
        "fileType": "text/markdown",
        "fileSize": len(content),
        "uploadType": "upload",
    })
    if token_resp.get("code") != 0 or not token_resp.get("result"):
        raise RuntimeError(f"Failed to get upload token: {token_resp.get('message')}")
    res = token_resp["result"]
    token_vo = res.get("tokenVo", {})
    upload_token = token_vo.get("token") or res.get("uploadToken")
    cosmo_yid = res.get("id") or res.get("cosmoYId")
    if not upload_token or not cosmo_yid:
        raise RuntimeError("Upload token missing from response")

    # 2. Upload file content
    upload_url = f"https://upload.kuaishouzt.com/api/upload?upload_token={upload_token}"
    upload_resp = session.post(upload_url, data=content,
                               headers={"Content-Type": "text/markdown"},
                               timeout=60)
    if upload_resp.status_code != 200:
        raise RuntimeError(f"File upload failed: HTTP {upload_resp.status_code}")

    # 3. Confirm import
    confirm_resp = _session_post(session, "/convert/api/v3/uploadFeedback?um=true", {
        "parentId": parent_id,
        "parentShortcutId": "",
        "fileName": filename,
        "docTypeEn": "doc",
        "cosmoYId": cosmo_yid,
    }, add_um=False)
    if confirm_resp.get("code") != 0 or not confirm_resp.get("result"):
        raise RuntimeError(f"Import confirmation failed: {confirm_resp.get('message')}")
    r = confirm_resp["result"]
    new_doc_id = r.get("cosmoId") or r.get("docId")
    new_url = r.get("cosmoUrl") or r.get("openDocUrl") or f"{BASE_URL}/d/home/{new_doc_id}"

    log.info(f"Wrote doc '{filename}' → {new_url}")
    return f"Doc created: {new_url}\nDoc ID: {new_doc_id}"


def _resolve_owner_ids(session: "_requests.Session", logins: list[str]) -> list[str]:
    """Resolve login IDs to entity IDs. Accepts loginId or numeric entity ID."""
    entity_ids = []
    for login in logins:
        if login.isdigit() and len(login) > 10:
            entity_ids.append(login)
            continue
        try:
            resp = session.get(
                f"{BASE_URL}/merlot/api/users/search?um=false&containsLeave=true&keywords={login}",
                timeout=10,
            )
            body = resp.json()
            for user in body.get("result", []):
                if user.get("loginId") == login:
                    entity_ids.append(user["id"])
                    break
            else:
                log.warning(f"Could not resolve owner loginId: {login}")
        except Exception as e:
            log.warning(f"Owner lookup failed for {login}: {e}")
    return entity_ids


def search_docs(keywords: str = "", doc_type: str = "all",
                ranges: list[str] | None = None,
                owner_ids: list[str] | None = None,
                last_view_time: str = "",
                page_num: int = 1, page_size: int = 20) -> str:
    """Search docs with keyword and filters. Returns JSON with results."""
    session = _get_session()

    # Resolve login IDs to entity IDs
    resolved_ids = _resolve_owner_ids(session, owner_ids) if owner_ids else []

    payload = {
        "pageNum": page_num,
        "pageSize": page_size,
        "keywords": keywords,
        "type": doc_type,
        "orderBy": "viewTime",
        "ranges": ranges or [],
        "lastViewTypeEn": last_view_time,
        "ownerIds": resolved_ids,
        "scrollId": None,
    }
    try:
        body = _session_post(session, "/merlot/api/searchs/search", payload)
    except Exception as exc:
        return json.dumps({"error": str(exc)})

    if body.get("code") != 0:
        return json.dumps({"error": body.get("message", "Search API error"), "code": body.get("code")})

    result = body.get("result", {})
    docs = []
    for doc in result.get("list", []):
        owner = doc.get("owner") or {}
        entry = {
            "docId": doc.get("docId", ""),
            "docName": doc.get("docName", ""),
            "url": doc.get("cosmoUrl", ""),
            "docType": doc.get("docTypeEn", ""),
            "owner": owner.get("name", ""),
            "ownerLoginId": owner.get("loginId", ""),
            "lastViewTime": doc.get("lastViewTime"),
            "lastModifyTime": doc.get("lastModifyTime"),
        }
        if doc.get("highlightContent"):
            entry["snippet"] = doc["highlightContent"][0][:200]
        docs.append(entry)

    return json.dumps({
        "total": result.get("total", 0),
        "pageNum": result.get("pageNum", page_num),
        "hasNext": result.get("hasNext", False),
        "docs": docs,
    }, ensure_ascii=False)


# ── Knowledge Base tree ───────────────────────────────────────────────────────

def _parse_shortcut_id(url: str) -> Optional[str]:
    """Extract the shortcutId from a kBase or doc URL.

    Examples:
        https://docs.corp.kuaishou.com/k/home/VDVkqGE_-uqQ          -> VDVkqGE_-uqQ
        https://docs.corp.kuaishou.com/k/home/VKkXtgo3f0Mw/fcAC...   -> VKkXtgo3f0Mw
    """
    m = re.search(r'/k/home/([A-Za-z0-9_-]+)', url)
    return m.group(1) if m else None


def _kbase_api(session: _requests.Session, endpoint: str, shortcut_id: str) -> dict:
    """Call a kBase API endpoint and return the result."""
    url = f"{BASE_URL}/merlot/api/knowledge-base/{endpoint}/{shortcut_id}?um=false"
    resp = session.post(url, json={"shortcutIds": []}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"kBase API error: {data.get('message', 'unknown')}")
    return data.get("result", {})


def _build_tree(session: _requests.Session, node: dict, depth: int = 0, max_depth: int = 5) -> list:
    """Recursively build the tree structure from a kBase node."""
    cosmo = node.get("cosmo", {})
    entry = {
        "name": cosmo.get("docName", ""),
        "type": cosmo.get("docTypeEn", ""),
        "url": cosmo.get("cosmoUrl", ""),
        "depth": depth,
    }
    result = [entry]

    # Process already-loaded children
    sub = node.get("subCosmos", [])
    if sub:
        for child in sub:
            result.extend(_build_tree(session, child, depth + 1, max_depth))
    elif cosmo.get("hasSubCosmos") and depth < max_depth:
        # Lazy-load children
        shortcut_id = cosmo.get("shortcutId", "")
        if shortcut_id:
            try:
                child_data = _kbase_api(session, "first-level-sub-nodes", shortcut_id)
                for child in child_data.get("root", {}).get("subCosmos", []):
                    result.extend(_build_tree(session, child, depth + 1, max_depth))
            except Exception as e:
                log.warning(f"Failed to expand {cosmo.get('docName')}: {e}")

    return result


def _format_tree(entries: list) -> str:
    """Format tree entries as indented text with links."""
    lines = []
    for e in entries:
        indent = "  " * e["depth"]
        type_label = f" ({e['type']})" if e["type"] else ""
        lines.append(f"{indent}{e['name']}{type_label}")
        if e["url"]:
            lines.append(f"{indent}  {e['url']}")
    return "\n".join(lines)


def list_tree(url: str) -> str:
    """List the file tree of a kBase with links."""
    shortcut_id = _parse_shortcut_id(url)
    if not shortcut_id:
        raise ValueError(f"Cannot parse shortcutId from URL: {url}")

    session = _get_session()
    root_data = _kbase_api(session, "sub-nodes", shortcut_id)
    root_node = root_data.get("root", {})
    if not root_node:
        raise RuntimeError("No root node returned from kBase API")

    entries = _build_tree(session, root_node)
    return _format_tree(entries)


# ── MCP server ─────────────────────────────────────────────────────────────────

server = Server("docs")

@server.list_tools()
async def list_tools():
    return [
        types.Tool(
            name="docs_read",
            description=(
                "Read a Kuaishou internal Docs page and return it as text. "
                "Preserves headings, lists, tables, math symbols, code blocks. "
                "Set include_images=true to also download and return embedded images. "
                "Requires access to docs.corp.kuaishou.com (internal network)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": (
                            "Full URL of the Docs page, e.g. "
                            "https://docs.corp.kuaishou.com/k/home/VPI5EbwYre-M/fcAD..."
                        ),
                    },
                    "include_images": {
                        "type": "boolean",
                        "description": (
                            "Download and return embedded images as base64 "
                            "(default false, max 20 images, 5MB each)."
                        ),
                    },
                },
                "required": ["url"],
            },
        ),
        types.Tool(
            name="docs_write",
            description=(
                "Create or update a Kuaishou internal Docs page from a local Markdown file. "
                "Uploads the .md file, strips YAML front-matter, and imports it as a new doc. "
                "Optionally deletes an existing doc before importing (update mode). "
                "Returns the new doc URL."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the local .md file to upload.",
                    },
                    "doc_url": {
                        "type": "string",
                        "description": (
                            "URL of an existing doc to update (delete & re-create). "
                            "Leave empty to create a new doc."
                        ),
                        "default": "",
                    },
                    "update": {
                        "type": "boolean",
                        "description": "If true and doc_url is set, delete the old doc first.",
                        "default": False,
                    },
                },
                "required": ["file_path"],
            },
        ),
        types.Tool(
            name="docs_search",
            description=(
                "Search Kuaishou internal Docs by keyword with filters. "
                "Supports filtering by doc type, interaction (我的收藏/我赞过的/我评论的/@我的), "
                "and owner. Returns doc titles, URLs, owners, and content snippets."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Search query. Empty string returns recent docs.",
                        "default": "",
                    },
                    "doc_type": {
                        "type": "string",
                        "description": (
                            "Doc type filter: 'all', 'doc' (在线文档), 'sheet' (在线表格), "
                            "'slide' (在线演示), 'folder', 'kBase' (知识库), 'board' (在线白板)."
                        ),
                        "default": "all",
                    },
                    "ranges": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Scope/interaction filter. Values: "
                            "'collect' (我的收藏), 'like' (我赞过的), 'comment' (我评论的), "
                            "'at' (@我的), 'recentEdit' (最近编辑), 'related' (与我相关), "
                            "'common' (通用), 'sameDept' (与我同部门), 'sameFunc' (与我同职能), "
                            "'kim' (Kim分享给我的). Can combine multiple."
                        ),
                    },
                    "owner_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by owner login IDs (e.g. ['xiaowentao']). Resolved to entity IDs automatically.",
                    },
                    "last_view_time": {
                        "type": "string",
                        "description": (
                            "最近浏览 time range filter: '' (任何时间, default), "
                            "'one' (最近1天), 'seven' (最近7天), 'thirty' (最近30天)."
                        ),
                        "default": "",
                    },
                    "page_num": {
                        "type": "integer",
                        "description": "Page number (1-based). Default: 1.",
                        "default": 1,
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "Results per page. Default: 20.",
                        "default": 20,
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="docs_list_tree",
            description=(
                "List the file tree of a Kuaishou internal Docs knowledge base (知识库) with links. "
                "Given a kBase URL or any doc URL within a kBase, returns the full tree structure "
                "with document names, types, and URLs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": (
                            "URL of a kBase or a doc within a kBase. e.g. "
                            "https://docs.corp.kuaishou.com/k/home/VDVkqGE_-uqQ"
                        ),
                    }
                },
                "required": ["url"],
            },
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "docs_read":
        url = arguments.get("url", "")
        include_images = arguments.get("include_images", False)
        try:
            markdown = read_doc(url)
            contents: list = [types.TextContent(type="text", text=markdown)]
            if include_images:
                img_urls = _extract_image_urls(markdown)
                if img_urls:
                    cookie = _load_cookie()
                    for i, img_url in enumerate(img_urls[:20]):
                        result = _download_image(img_url, cookie)
                        if result:
                            raw, mime = result
                            contents.append(types.ImageContent(
                                type="image",
                                data=base64.b64encode(raw).decode("ascii"),
                                mimeType=mime,
                            ))
                            log.info(f"Image {i+1}/{len(img_urls)}: {len(raw)} bytes")
            return contents
        except Exception as e:
            log.error(f"docs_read failed: {e}")
            return [types.TextContent(type="text", text=f"Error: {e}")]
    elif name == "docs_write":
        file_path = arguments.get("file_path", "")
        doc_url = arguments.get("doc_url", "")
        update = arguments.get("update", False)
        try:
            result = write_doc(file_path, doc_url, update)
            return [types.TextContent(type="text", text=result)]
        except Exception as e:
            log.error(f"docs_write failed: {e}")
            return [types.TextContent(type="text", text=f"Error: {e}")]
    elif name == "docs_search":
        try:
            result = await asyncio.to_thread(
                search_docs,
                arguments.get("keywords", ""),
                arguments.get("doc_type", "all"),
                arguments.get("ranges"),
                arguments.get("owner_ids"),
                arguments.get("last_view_time", ""),
                arguments.get("page_num", 1),
                arguments.get("page_size", 20),
            )
            return [types.TextContent(type="text", text=result)]
        except Exception as e:
            log.error(f"docs_search failed: {e}")
            return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]
    elif name == "docs_list_tree":
        url = arguments.get("url", "")
        try:
            result = await asyncio.to_thread(list_tree, url)
            return [types.TextContent(type="text", text=result)]
        except Exception as e:
            log.error(f"docs_list_tree failed: {e}")
            return [types.TextContent(type="text", text=f"Error: {e}")]
    else:
        raise ValueError(f"Unknown tool: {name}")

async def _serve():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(_serve())

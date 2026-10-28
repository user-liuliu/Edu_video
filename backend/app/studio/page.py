"""Open a studio film document in headless Chromium, fully offline.

Shared by the browser checks and the render service. The page lives at
``http://studio.local/film.html`` so ``'self'`` in the CSP and relative URLs resolve to one
origin; ``/studio-runtime/<current digest>/<name>`` is served from the runtime assets and
every other request is aborted and WebSockets are closed. The film CSP is also sent as a
response header, so it applies even when the caller's HTML lacks the ``<meta>`` copy.

Every page step is bounded: opening (until ``window.studioReady``) by ``READY_TIMEOUT``, and
each later step passed through ``bounded(page, ...)`` by ``STEP_TIMEOUT``. On a timeout the
page's JavaScript is stopped with CDP ``Runtime.terminateExecution`` and ``StudioTimeout`` is
raised with the segment and phase the runtime marked in ``window.__studioBusy``.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from urllib.parse import unquote, urlsplit

from app.studio.film import CSP
from app.studio.runtime.assets import read_runtime_file, runtime_digest

ORIGIN = 'http://studio.local'
PAGE_URL = f'{ORIGIN}/film.html'
CONTENT_TYPES = {
    '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.woff2': 'font/woff2',
}
WEBGL_ARGS = ('--use-angle=swiftshader', '--enable-unsafe-swiftshader')
READY_TIMEOUT = 30  # s: opening the page, building every segment, loading fonts
STEP_TIMEOUT = 5  # s: each later step (one renderFrame, evaluate or screenshot)
TERMINATE_TIMEOUT = 5  # s: stopping the stuck script and reading what it was doing

_sessions: dict = {}  # page -> (CDP session, page errors)


class StudioTimeout(Exception):
    """The page did not answer in time; its scripts were stopped."""

    def __init__(self, seconds: float, segment: str | None, phase: str | None,
                 diagnostics: list[dict], errors: list[str]):
        super().__init__(f'页面 {seconds:g} 秒没有响应')
        self.seconds, self.segment, self.phase = seconds, segment, phase
        self.diagnostics, self.errors = diagnostics, errors
        self.t: float | None = None  # film time being drawn, when the caller knows it


async def _stop(page, seconds: float) -> StudioTimeout:
    cdp, errors = _sessions.get(page, (None, []))
    busy, diagnostics = None, []
    try:
        if cdp is not None:
            await asyncio.wait_for(cdp.send('Runtime.terminateExecution'), TERMINATE_TIMEOUT)
        for _ in range(2):  # a pending termination may stop the first read itself
            try:
                busy, diagnostics = await asyncio.wait_for(page.evaluate(
                    '[window.__studioBusy || null, (window.studioDiagnostics || []).slice()]'),
                    TERMINATE_TIMEOUT)
                break
            except Exception:  # noqa: BLE001 - terminated or still stuck: report what we know
                continue
    except Exception:  # noqa: BLE001
        pass
    busy = busy if isinstance(busy, dict) else {}
    return StudioTimeout(seconds, busy.get('segment'), busy.get('phase'), diagnostics or [], list(errors))


async def bounded(page, awaitable, timeout: float = STEP_TIMEOUT):
    """Await one page step; on timeout stop the page's scripts and raise StudioTimeout."""
    from playwright.async_api import TimeoutError as PlaywrightTimeout
    try:
        return await asyncio.wait_for(awaitable, timeout)
    except (asyncio.TimeoutError, PlaywrightTimeout):
        raise await _stop(page, timeout) from None


def _content_type(name: str) -> str | None:
    for suffix, value in CONTENT_TYPES.items():
        if name.endswith(suffix):
            return value
    return None


@asynccontextmanager
async def studio_page(html: str, *, width: int = 1280, height: int = 720, webgl: bool = False):
    """Yield ``(page, errors)`` once ``window.studioReady`` has resolved.

    ``errors`` collects ``pageerror`` messages for the whole life of the page.
    """
    from playwright.async_api import async_playwright

    digest = runtime_digest()  # computed per page: it changes whenever a runtime file changes
    prefix = f'/studio-runtime/{digest}/'

    async def handle(route):
        url = urlsplit(route.request.url)
        if f'{url.scheme}://{url.netloc}' != ORIGIN:
            return await route.abort()
        if url.path == '/film.html':
            return await route.fulfill(status=200, body=html.encode('utf-8'),
                                       content_type='text/html; charset=utf-8',
                                       headers={'Content-Security-Policy': CSP})
        if url.path.startswith(prefix):
            name = unquote(url.path[len(prefix):])
            kind = _content_type(name)
            if kind is not None:
                try:
                    body = read_runtime_file(name)
                except KeyError:
                    pass
                else:
                    return await route.fulfill(status=200, body=body, content_type=kind)
        return await route.abort()

    async def no_websocket(ws):
        await ws.close()

    page = None
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            channel=os.environ.get('EV_RENDER_BROWSER', 'msedge') if os.name == 'nt' else None,
            executable_path=os.environ.get('EV_RENDER_EXECUTABLE') or None,
            args=list(WEBGL_ARGS) if webgl else [])
        try:
            context = await browser.new_context(viewport={'width': width, 'height': height},
                                                service_workers='block')
            await context.route('**/*', handle)
            await context.route_web_socket('**/*', no_websocket)
            page = await context.new_page()
            errors: list[str] = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.set_default_timeout(15000)
            _sessions[page] = (await context.new_cdp_session(page), errors)

            async def ready():
                await page.goto(PAGE_URL, wait_until='load', timeout=READY_TIMEOUT * 1000)
                if not await page.evaluate('typeof window.studioReady === "object" && !!window.studioReady'):
                    raise RuntimeError('动效运行时没有加载：' + '；'.join(errors or ['window.studioReady 不存在']))
                await page.evaluate('window.studioReady.then(() => true)')
            await bounded(page, ready(), READY_TIMEOUT)
            yield page, errors
        finally:
            _sessions.pop(page, None)
            await browser.close()

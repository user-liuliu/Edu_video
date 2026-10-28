"""Open a studio film document in headless Chromium, fully offline.

Shared by the browser checks and the render service. The page lives at
``http://studio.local/film.html`` so ``'self'`` in the CSP and relative URLs resolve to one
origin; ``/studio-runtime/<current digest>/<name>`` is served from the runtime assets and
every other request is aborted.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from urllib.parse import unquote, urlsplit

from app.studio.runtime.assets import read_runtime_file, runtime_digest

ORIGIN = 'http://studio.local'
PAGE_URL = f'{ORIGIN}/film.html'
CONTENT_TYPES = {
    '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.woff2': 'font/woff2',
}
WEBGL_ARGS = ('--use-angle=swiftshader', '--enable-unsafe-swiftshader')
READY_TIMEOUT = 30  # seconds


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
                                       content_type='text/html; charset=utf-8')
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
            page = await context.new_page()
            errors: list[str] = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.set_default_timeout(15000)
            await page.goto(PAGE_URL, wait_until='load')
            if not await page.evaluate('typeof window.studioReady === "object" && !!window.studioReady'):
                raise RuntimeError('动效运行时没有加载：' + '；'.join(errors or ['window.studioReady 不存在']))
            await asyncio.wait_for(page.evaluate('window.studioReady.then(() => true)'), READY_TIMEOUT)
            yield page, errors
        finally:
            await browser.close()

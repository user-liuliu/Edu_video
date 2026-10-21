"""Refresh Chromium SVG filter paint caches before offline frame capture.

Installed only inside a dedicated renderer subprocess. Original SVG nodes and
JavaScript references are preserved; renderFrame is never called a second time.
The accepted HTML, clock and strict pixel comparisons remain unchanged.
"""
from contextlib import asynccontextmanager

PAINT = '''() => new Promise(resolve =>
    requestAnimationFrame(() => requestAnimationFrame(resolve)))'''


@asynccontextmanager
async def stable_svg_capture():
    from playwright.async_api import Page
    original = Page.screenshot

    async def screenshot(page, *args, **kwargs):
        # The sealed film has a host page and an isolated generated iframe.
        for frame in page.frames[1:]:
            if not await frame.evaluate("!!document.querySelector('svg filter')"):
                continue
            saved = await frame.evaluate_handle('''() => {
                const roots = [...document.querySelectorAll('svg')]
                    .filter(svg => !svg.ownerSVGElement);
                const saved = roots.map(svg => {
                    const marker = document.createComment('capture');
                    svg.parentNode.insertBefore(marker, svg);
                    return [svg, marker];
                });
                for (const [svg] of saved) svg.remove();
                void document.documentElement.offsetHeight;
                return saved;
            }''')
            try:
                # A committed empty paint discards stale SVG filter surfaces.
                await frame.evaluate(PAINT)
            finally:
                await saved.evaluate('''saved => {
                    for (const [svg, marker] of saved) marker.replaceWith(svg);
                    void document.documentElement.offsetHeight;
                }''')
                await saved.dispose()
            await frame.evaluate(PAINT)
        return await original(page, *args, **kwargs)

    Page.screenshot = screenshot
    try:
        yield
    finally:
        Page.screenshot = original
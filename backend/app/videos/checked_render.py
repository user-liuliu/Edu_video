"""Compile generated classic scripts before executing the sealed film.

Kept outside the sealed runtime digest: validation does not alter a film or
invalidate previously accepted previews. Chromium compiles without executing.
"""
import os
from html.parser import HTMLParser
from .direct_render import validate_direct as _validate_direct, render_direct as _render_direct
from .render_contract import DirectHtmlRuntimeError


class Scripts(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=False)
        self.scripts=[]
        self.current=None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag!='script':return
        attrs=dict(attrs)
        kind=(attrs.get('type') or '').strip().lower().split(';')[0]
        if kind and kind not in ('text/javascript','application/javascript','text/ecmascript','application/ecmascript'):
            return
        self.current={'parts':[], 'line':self.getpos()[0]+self.get_starttag_text().count('\n')}

    def handle_data(self, data):
        if self.current is not None:self.current['parts'].append(data)

    def handle_endtag(self, tag):
        if tag=='script' and self.current is not None:
            self.scripts.append(self.current)
            self.current=None


async def check_syntax(html):
    from playwright.async_api import async_playwright
    scripts=Scripts(html).scripts
    if not scripts:return
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(headless=True,
            channel=os.environ.get('EV_RENDER_BROWSER','msedge') if os.name=='nt' else None,
            executable_path=os.environ.get('EV_RENDER_EXECUTABLE') or None)
        try:
            context=await browser.new_context(service_workers='block')
            await context.route('**/*',lambda route:route.abort())
            page=await context.new_page()
            session=await context.new_cdp_session(page)
            await session.send('Runtime.enable')
            for index,script in enumerate(scripts,1):
                source=''.join(script['parts'])
                result=await session.send('Runtime.compileScript',{'expression':source,
                    'sourceURL':f'animation-script-{index}.js','persistScript':False})
                error=result.get('exceptionDetails')
                if error:
                    description=error.get('exception',{}).get('description') or error.get('text','SyntaxError')
                    description=description.split('\n')[0][:180]
                    line=error.get('lineNumber',0);column=error.get('columnNumber',0)
                    lines=source.split('\n')
                    excerpt=lines[min(line,len(lines)-1)][max(0,column-70):column+100]
                    raise DirectHtmlRuntimeError(
                        f'动画脚本语法错误：JavaScript {description} (script {index}, line {line+1}, column {column+1}; '
                        f'HTML line {script["line"]+line}). Context: {excerpt}'[:500])
        finally:await browser.close()


async def validate_direct(request):
    await check_syntax(request.html)
    return await _validate_direct(request)


async def render_direct(request, output):
    await check_syntax(request.html)
    return await _render_direct(request,output)

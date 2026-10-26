"""One bounded request per child process, reaped by the renderer service."""
import asyncio,base64,json,sys
from pathlib import Path
from app.presentations.graphic_contract import VERSION
from .ppt_graphics import render_graphic

async def main(folder):
    root=Path(folder);source=json.loads((root/'request.json').read_text())
    version=source['version'];data,labels=await render_graphic(source['source'],version=version)
    (root/'output.json').write_text(json.dumps({'version':version,'png_base64':base64.b64encode(data).decode(),'labels':labels}),encoding='utf-8')

if __name__=='__main__':asyncio.run(main(sys.argv[1]))

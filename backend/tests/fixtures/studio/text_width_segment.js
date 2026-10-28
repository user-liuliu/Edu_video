// Measures a LXGW WenKai label while the segment is being built.
ctx.svg.innerHTML = '<text data-edu-id="label" x="10" y="100" font-family="LXGW WenKai" font-size="40">Wide Mmm iii 抛物线</text>';
ctx.root.dataset.builtWidth = String(ctx.$('[data-edu-id="label"]')[0].getComputedTextLength());

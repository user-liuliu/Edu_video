// Paints a full-stage red rect, then its painter throws from 1 s on.
ctx.svg.innerHTML = '<rect x="0" y="0" width="1280" height="720" fill="#ff0000"/>';
ctx.paint(function (t) { if (t >= 1) throw new Error('boom'); });

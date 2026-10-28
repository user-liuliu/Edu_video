// Draws a full-stage red rect, then fails while building.
ctx.svg.innerHTML = '<rect x="0" y="0" width="1280" height="720" fill="#ff0000"/>';
throw new Error('boom');

// Segment "a" (2 s) of the two-segment seam films: a blue square sliding right the whole
// segment, a red dot tagged for match cuts, a word highlighted from 1.5 s and held to the
// end of the segment, and a canvas bar drawn only by a ctx.paint painter.
ctx.svg.innerHTML =
  '<rect data-edu-id="square" x="100" y="150" width="160" height="160" fill="#2b6cb0"/>' +
  '<circle data-edu-id="dot" data-edu-match="dot" cx="300" cy="480" r="40" fill="#c53030"/>' +
  '<text data-edu-id="word" x="900" y="250" text-anchor="middle" font-size="80" fill="#000000">强调</text>';
ctx.tl.to(ctx.$('[data-edu-id="square"]'), {x: 300, duration: 2, ease: 'none'}, 0);
ctx.tl.to(ctx.$('[data-edu-id="dot"]'), {x: 200, duration: 1, ease: 'none'}, 0.5);
ctx.motion.highlight('[data-edu-id="word"]', 1.5, {dur: 1, style: 'color', color: '#00aa00'});
const canvas = document.createElement('canvas');
canvas.width = 200; canvas.height = 100;
canvas.setAttribute('data-edu-id', 'bar');
ctx.root.appendChild(canvas);
const g = canvas.getContext('2d');
const bar = {p: 0};
ctx.tl.to(bar, {p: 1, duration: 1, ease: 'none'}, 0.5);
ctx.paint(function () {
  g.fillStyle = '#ffffff'; g.fillRect(0, 0, 200, 100);
  g.fillStyle = '#000000'; g.fillRect(0, 0, 10 + 190 * bar.p, 100);
});

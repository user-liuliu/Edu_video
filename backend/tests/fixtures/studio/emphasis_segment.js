// Emphases shorter than their own fade, and a highlight on text the segment had already
// recoloured: the frame at any time must not depend on the seek direction, and the
// highlight must hand back the colour the text had just before it (blue), not black.
ctx.svg.innerHTML =
  '<text data-edu-id="short" x="200" y="200" font-size="60" fill="#000000">短</text>' +
  '<text data-edu-id="blue" x="600" y="200" font-size="60" fill="#000000">蓝</text>' +
  '<rect data-edu-id="box" x="900" y="150" width="100" height="100" fill="#2f855a"/>';
ctx.motion.highlight('[data-edu-id="short"]', 1.0, {dur: 0.05, style: 'glow'});
ctx.tl.to(ctx.$('[data-edu-id="blue"]'), {fill: '#0000ff', duration: 0.3}, 0.2);
ctx.motion.highlight('[data-edu-id="blue"]', 1.0, {dur: 0.5, style: 'color'});
ctx.motion.spotlight('[data-edu-id="box"]', 1.0, 0.1);

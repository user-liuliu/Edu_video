// Two emphases overlapping on one element: red at 1.0 and green at 1.1 (0.6 s each), on text
// the segment had tweened to blue before. The later one wins while both are on, the result
// never depends on the seek direction, and the text is blue again afterwards. The same for
// two glows on a second element.
ctx.svg.innerHTML =
  '<text data-edu-id="word" x="300" y="300" font-size="80" fill="#000000">词</text>' +
  '<text data-edu-id="glow" x="700" y="300" font-size="80" fill="#000000">光</text>';
ctx.tl.to(ctx.$('[data-edu-id="word"]'), {fill: '#0000ff', duration: 0.3}, 0.2);
ctx.motion.highlight('[data-edu-id="word"]', 1.0, {dur: 0.6, style: 'color', color: '#ff0000'});
ctx.motion.highlight('[data-edu-id="word"]', 1.1, {dur: 0.6, style: 'color', color: '#00ff00'});
ctx.motion.highlight('[data-edu-id="glow"]', 1.0, {dur: 0.6, color: '#ff0000'});
ctx.motion.highlight('[data-edu-id="glow"]', 1.1, {dur: 0.6, color: '#00ff00'});

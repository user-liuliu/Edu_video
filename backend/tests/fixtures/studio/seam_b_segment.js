// Segment "b" (2 s) of the two-segment seam films: a green bar, and the match-cut dot at a
// different place and size from where segment "a" leaves it, moving only from 1 s on.
ctx.svg.innerHTML =
  '<rect data-edu-id="block" x="700" y="380" width="400" height="120" fill="#2f855a"/>' +
  '<circle data-edu-id="dot" data-edu-match="dot" cx="900" cy="250" r="70" fill="#c53030"/>';
ctx.tl.to(ctx.$('[data-edu-id="dot"]'), {x: -300, duration: 0.8, ease: 'none'}, 1);

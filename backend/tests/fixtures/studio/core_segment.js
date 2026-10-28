// Segment "a": a parabola, a vertex label, the kr character walking right and a camera push-in.
ctx.svg.innerHTML =
  '<path id="curve" d="M240,160 Q640,760 1040,160" stroke="#c53030" stroke-width="6" fill="none"/>' +
  '<text data-edu-id="vertex" x="640" y="500" text-anchor="middle" font-size="44" opacity="0">顶点</text>';
const kr = ctx.actor('kr', {color: '#2b6cb0'});
const label = ctx.$('[data-edu-id="vertex"]');
ctx.tl.from(ctx.$('#curve'), {drawSVG: '0%', duration: 1.2, ease: 'none'}, 0.1);
kr.moveTo({x: 500, y: 600}, 1, 1);
kr.pose({arm_r: -60}, 1.2, 0.6);
kr.expression('sad', 2.0);
ctx.tl.to(label, {opacity: 1, duration: 0.3}, ctx.cue('顶点'));
ctx.camera.shot({x: 640, y: 450, zoom: 1.4}, ctx.cue('顶点'), 0.8);
ctx.endState({keep: ['vertex']});

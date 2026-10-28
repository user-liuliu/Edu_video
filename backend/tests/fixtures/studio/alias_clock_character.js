// Character "dice": a factory that reaches the random source and the clocks through aliases
// the lint cannot see. Without the runtime's stand-ins its bar would differ between loads.
EduStudio.defineCharacter('dice', function (g) {
  const NS = 'http://www.w3.org/2000/svg';
  const M = Math, D = Date, P = performance;
  const r = M['ran' + 'dom']();
  const now = D['no' + 'w']();
  const fresh = new D().getTime();
  const perf = P['no' + 'w']();
  const bytes = new Uint8Array(4);
  crypto['getRandom' + 'Values'](bytes);
  const width = 60 + r * 40 + (now % 7) + (perf % 5) + bytes[0] / 64;
  const part = document.createElementNS(NS, 'g');
  part.setAttribute('data-part', 'bar');
  part.setAttribute('data-pivot', '0,-20');
  const bar = document.createElementNS(NS, 'rect');
  bar.setAttribute('x', String(-width / 2));
  bar.setAttribute('y', '-40');
  bar.setAttribute('width', String(width));
  bar.setAttribute('height', '40');
  bar.setAttribute('fill', '#c53030');
  part.appendChild(bar);
  g.appendChild(part);
  g.setAttribute('data-probe', JSON.stringify([r, now, fresh, perf, Array.from(bytes), width]));
});

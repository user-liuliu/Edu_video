// Test character "kr": a stick figure whose feet sit at (0,0). Parts rotate about their pivot.
EduStudio.defineCharacter('kr', function (g, params) {
  const NS = 'http://www.w3.org/2000/svg';
  const color = (params && params.color) || '#2b6cb0';
  function part(name, pivot) {
    const p = document.createElementNS(NS, 'g');
    p.setAttribute('data-part', name);
    p.setAttribute('data-pivot', pivot);
    g.appendChild(p);
    return p;
  }
  function shape(parent, tag, attrs) {
    const el = document.createElementNS(NS, tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    parent.appendChild(el);
    return el;
  }
  const body = part('body', '0,-60');
  shape(body, 'path', {d: 'M0,-120 L0,-40 M0,-40 L-20,0 M0,-40 L20,0', stroke: color, 'stroke-width': 8, fill: 'none', 'stroke-linecap': 'round'});
  const head = part('head', '0,-120');
  shape(head, 'circle', {cx: 0, cy: -145, r: 25, fill: '#fff', stroke: color, 'stroke-width': 6});
  const smile = shape(head, 'g', {'data-expression': 'smile'});
  shape(smile, 'path', {d: 'M-10,-140 Q0,-130 10,-140', stroke: color, 'stroke-width': 4, fill: 'none'});
  const sad = shape(head, 'g', {'data-expression': 'sad'});
  sad.style.visibility = 'hidden';
  shape(sad, 'path', {d: 'M-10,-133 Q0,-143 10,-133', stroke: color, 'stroke-width': 4, fill: 'none'});
  const arm = part('arm_r', '0,-105');
  shape(arm, 'path', {d: 'M0,-105 L45,-80', stroke: color, 'stroke-width': 8, fill: 'none', 'stroke-linecap': 'round'});
});

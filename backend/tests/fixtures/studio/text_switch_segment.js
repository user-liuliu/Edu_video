// Two labels that both say A. One switches to B at 2 s with tl.set (seek-safe). The other
// tries to switch with tl.call, which the runtime never fires, so it must stay A.
ctx.svg.innerHTML =
  '<text data-edu-id="label" x="640" y="300" font-size="80">A</text>' +
  '<text data-edu-id="called" x="640" y="450" font-size="80">A</text>';
ctx.tl.set(ctx.$('[data-edu-id="label"]'), {textContent: 'B'}, 2);
const called = ctx.$('[data-edu-id="called"]')[0];
ctx.tl.call(function () { called.textContent = 'B'; }, null, 2);

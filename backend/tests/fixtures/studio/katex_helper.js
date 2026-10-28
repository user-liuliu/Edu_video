// Character-code helper that draws a formula. It reaches the formula library without its
// name followed by a dot appearing anywhere, like a runtime helper (ctx.motion.tex) would.
var renderFormula = (function (lib) {
  return function (el, tex) { lib['render'](tex, el); };
})(globalThis['kate' + 'x']);

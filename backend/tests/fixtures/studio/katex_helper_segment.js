// Measures a formula drawn through the helper from the character code, at build time.
const box = document.createElement('div');
box.style.cssText = 'position:absolute;left:100px;top:100px;font-size:40px';
ctx.root.appendChild(box);
renderFormula(box, '\\int_0^1 x^2\\,dx = \\frac{1}{3}');
ctx.root.dataset.builtWidth = String(box.getBoundingClientRect().width);

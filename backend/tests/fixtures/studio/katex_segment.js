// Measures a KaTeX formula while the segment is being built.
const box = document.createElement('div');
box.style.cssText = 'position:absolute;left:100px;top:100px;font-size:40px';
ctx.root.appendChild(box);
katex.render('\\int_0^1 x^2\\,dx = \\frac{1}{3}', box);
ctx.root.dataset.builtWidth = String(box.getBoundingClientRect().width);

// A canvas drawn only by a ctx.paint painter from a tweened plain object:
// white background plus a black progress bar.
const canvas = document.createElement('canvas');
canvas.width = 200; canvas.height = 100;
canvas.setAttribute('data-edu-id', 'bar');
ctx.root.appendChild(canvas);
const g = canvas.getContext('2d');
const progress = {p: 0};
ctx.tl.to(progress, {p: 1, duration: 1, ease: 'none'}, 1);
ctx.paint(function () {
  g.fillStyle = '#ffffff'; g.fillRect(0, 0, 200, 100);
  g.fillStyle = '#000000'; g.fillRect(0, 0, 10 + 190 * progress.p, 100);
});

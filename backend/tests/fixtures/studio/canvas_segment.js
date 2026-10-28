// A canvas painted only by one tween's onUpdate: white background plus a black progress bar.
const canvas = document.createElement('canvas');
canvas.width = 200; canvas.height = 100;
canvas.setAttribute('data-edu-id', 'bar');
ctx.root.appendChild(canvas);
const g = canvas.getContext('2d');
const progress = {p: 0};
ctx.tl.to(progress, {p: 1, duration: 1, ease: 'none', onUpdate: function () {
  g.fillStyle = '#ffffff'; g.fillRect(0, 0, 200, 100);
  g.fillStyle = '#000000'; g.fillRect(0, 0, 10 + 190 * progress.p, 100);
}}, 1);

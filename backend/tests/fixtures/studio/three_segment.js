// three.js through the runtime's shared renderer (ctx.three()): a cube and a rotating function
// surface z = 0.6 sin(1.5x) cos(1.5y), MeshStandardMaterial lit by a directional light. Every
// frame is drawn only by the ctx.paint painter from tweened plain objects. Segments keep the
// renderer's transparent clear (the stage colour shows) and a blue cube, except segment "b",
// which clears to light blue and has a red cube, so two segments' pictures can be told apart.
const {renderer} = ctx.three();
const W = ctx.width, H = ctx.height;
const own = ctx.id === 'b';

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, W / H, 0.1, 100);
camera.position.set(0, 3, 9);
camera.lookAt(0, 0, 0);
scene.add(new THREE.AmbientLight(0xffffff, 0.4));
const sun = new THREE.DirectionalLight(0xffffff, 2.2);
sun.position.set(4, 6, 5);
scene.add(sun);

const cube = new THREE.Mesh(new THREE.BoxGeometry(1.6, 1.6, 1.6),
  new THREE.MeshStandardMaterial({color: own ? 0xc53030 : 0x2b6cb0, roughness: 0.5, metalness: 0.1}));
cube.position.set(-2.6, 0, 0);
scene.add(cube);

const surfaceGeometry = new THREE.PlaneGeometry(4, 4, 48, 48);
const position = surfaceGeometry.attributes.position;
for (let i = 0; i < position.count; i++) {
  const x = position.getX(i), y = position.getY(i);
  position.setZ(i, 0.6 * Math.sin(1.5 * x) * Math.cos(1.5 * y));
}
surfaceGeometry.computeVertexNormals();
const surface = new THREE.Mesh(surfaceGeometry,
  new THREE.MeshStandardMaterial({color: 0xd69e2e, roughness: 0.6, side: THREE.DoubleSide}));
surface.rotation.x = -Math.PI / 2.6;
surface.position.set(1.8, 0, 0);
scene.add(surface);

const s = {rot: 0, spin: 0};
ctx.tl.to(s, {rot: Math.PI * 2, duration: ctx.duration, ease: 'none'}, 0);
ctx.tl.to(s, {spin: Math.PI, duration: ctx.duration, ease: 'power1.inOut'}, 0);
ctx.paint(function () {
  if (own) renderer.setClearColor(0xbee3f8, 1);  // renderer settings last one painter call
  surface.rotation.z = s.rot;
  cube.rotation.set(s.spin * 0.5, s.spin, 0);
  renderer.render(scene, camera);
});

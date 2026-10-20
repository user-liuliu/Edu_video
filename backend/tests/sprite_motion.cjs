const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../app/videos/sprite_motion.js'),'utf8');
const scope={window:{}};vm.createContext(scope);vm.runInContext(code,scope);const S=scope.window.EduSprites;
const bundle=JSON.parse(fs.readFileSync(path.join(__dirname,'../app/videos/sprite_assets/manifest.json'),'utf8'));
S.configure({...bundle,images:{}});
if(process.argv.includes('--contacts')){
 const output=[];
 for(const variant of Object.keys(bundle.characters))for(const direction of ['up','left','down','right'])for(const [action,spec] of Object.entries(bundle.actions))for(let frame=0;frame<spec.frames;frame++)for(const name of ['leftHand','rightHand']){
  const actor=S.actor({variant,direction,action,frame,x:32,y:60}),p=S.anchor(actor,name);
  output.push({variant,direction,action,frame:actor.frame,x:p.x,y:p.y});
 }
 console.log(JSON.stringify(output));process.exit(0);
}
const sample=t=>S.travel({points:[{x:0,y:0},{x:40,y:0},{x:40,y:40}],start:2,end:6,stride:40},t);
assert.equal(sample(0).action,'idle');assert.equal(sample(7).action,'idle');
assert.equal(sample(3).direction,'right');assert.equal(sample(5).direction,'down');
assert(Math.abs(sample(4).distance-40)<1e-9);
assert(Math.hypot(sample(4.01).x-sample(3.99).x,sample(4.01).y-sample(3.99).y)>.25,'No stop at internal waypoint');
assert.equal(S.pose('neutral').frame,0);assert.equal(S.pose('hands_front').frame,1);
assert.throws(()=>S.pose('emotes'),/姿态/);
const a=S.actor({variant:'ochre',x:20,y:50,direction:'right',scale:1,pose:'hands_front'});
const b=S.actor({variant:'teal',x:45,y:50,direction:'left',scale:1,pose:'hands_front'});
const p=S.transfer(a,b,1,{start:1,end:2}),q=S.anchor(a,'hand');assert.equal(p.x,q.x);assert.equal(p.y,q.y);
const finish=S.transfer(a,b,2,{start:1,end:2}),hand=S.anchor(b,'hand');assert.equal(finish.x,hand.x);assert.equal(finish.y,hand.y);
const before=S.transfer(a,b,1.499,{start:1,end:2}),after=S.transfer(a,b,1.501,{start:1,end:2});assert(Math.hypot(after.x-before.x,after.y-before.y)<.2,'Continuous handover');
const moved=S.actor({...a,x:a.x+10,y:a.y+5});assert.equal(S.anchor(moved,'hand').x-q.x,10);assert.equal(S.anchor(moved,'hand').y-q.y,5);
const scaled=S.actor({...a,scale:2});assert.equal(S.anchor(scaled,'hand').x-scaled.x,2*(q.x-a.x));
const one=sample(3.25);sample(6);sample(0);assert.equal(JSON.stringify(sample(3.25)),JSON.stringify(one),'Reverse seek determinism');
assert.throws(()=>S.travel({points:[{x:0,y:0}],start:0,end:0},1),/路径/);
const repeated={points:[{x:0,y:0},{x:0,y:0},{x:40,y:0},{x:40,y:0}],start:0,end:2};
assert.equal(S.travel(repeated,2).x,40);assert.equal(S.travel(repeated,0).x,0);
for(const direction of ['up','left','down','right']){
 for(const name of ['neutral','hands_front','raised_arms']){
  const actor=S.actor({x:100,y:100,scale:2,direction,pose:name});
  const first=S.anchor(actor,'hand');assert(Number.isFinite(first.x)&&Number.isFinite(first.y));
  assert.equal(S.actor(actor).frame,actor.frame,'Static poses must never auto-cycle');
 }
}
console.log('sprite motion behavior checks passed');
assert.equal(S.animate('pickup',-1).frame,0);
assert.equal(S.animate('pickup',100).frame,5);
assert.equal(S.animate('sit',100).frame,3);
assert.equal(S.animate('wave',1).frame,1);
assert.equal(S.actor({action:'sit',frame:100}).frame,3);
assert.equal(S.travel({points:[{x:0,y:0},{x:50,y:0}],start:0,end:4,action:'carry'},2).action,'carry');
assert.equal(S.actor({variant:'missing'}).variant,'farmer_m');
for(const variant of Object.keys(bundle.characters))for(const action of Object.keys(bundle.actions)){
 const actor=S.actor({variant,action,frame:1});
 const before=S.anchor(actor,'hand');
 const moved=S.anchor({...actor,x:40,y:50,scale:2},'hand');
 assert.equal(moved.x,40+before.x*2);
 assert.equal(moved.y,50+before.y*2);
 if(action!=='pose'){
  const sample=JSON.stringify(S.animate(action,.45));S.animate(action,7);S.animate(action,0);
  assert.equal(JSON.stringify(S.animate(action,.45)),sample);
 }
}
console.log('original cast actions, anchors and reverse seeking passed');

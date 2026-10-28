// 第 story 段（push 转场进来）：孔融让梨。孔融从桌上拿起最大的梨，走到哥哥身边，
// 抬手把梨递过去，哥哥伸手来接，笑着点头。
// 梨的交接不改零件形状：桌上的梨是场景里单独的图形，孔融手里的梨是 arm_back 零件里
// 一直存在的图形（data-prop="pear"），拿起的那一刻用 tl.set 切换两者的 visibility。
// 桌上的梨和手里的梨用同一个变换，所以切换时画面上看不出跳动。
const tl = ctx.tl;
const KR = {x0: 270, x1: 610, y: 600, scale: 1.15};
const REACH = -60, HOLD = -35, GIVE = -95;  // arm_back angles: pick up, carry, hand over

// Where the held pear is on stage when Kong Rong stands at (KR.x0, KR.y) with arm_back at REACH:
// outer translate, then scale, then the part's rotation about its pivot (32,-162), then the
// pear's own offset in the arm (shoulder at (32,-162), pear at (1,104) from the shoulder).
const pearOnTable = 'translate(' + KR.x0 + ',' + KR.y + ') scale(' + KR.scale + ') rotate(' + REACH + ' 32 -162) translate(33,-58)';

ctx.svg.insertAdjacentHTML('beforeend',
  // Room: wall, floor, beam and posts (the reference stage, scaled to the canvas).
  '<rect x="0" y="0" width="1280" height="720" fill="#fbf3e4"/>' +
  '<rect x="0" y="540" width="1280" height="180" fill="#ecdcc0"/>' +
  '<rect x="0" y="536" width="1280" height="6" fill="#e0caa4"/>' +
  '<rect x="160" y="40" width="960" height="22" rx="11" fill="#b98a5a"/>' +
  '<rect x="186" y="62" width="16" height="478" fill="#a77a4c"/>' +
  '<rect x="1078" y="62" width="16" height="478" fill="#a77a4c"/>' +
  '<text data-edu-id="title" x="640" y="138" text-anchor="middle" font-family="LXGW WenKai" font-size="60" fill="#6b4a2b">孔融让梨</text>' +
  // Low table with a plate: the big pear lies on its side, two small ones stand beside it.
  '<g data-edu-id="table">' +
  '<rect x="318" y="512" width="12" height="74" rx="3" fill="#8c6239"/>' +
  '<rect x="478" y="512" width="12" height="74" rx="3" fill="#8c6239"/>' +
  '<rect x="300" y="504" width="208" height="14" rx="5" fill="#a5774a"/>' +
  '<rect x="300" y="516" width="208" height="5" rx="2" fill="#8c6239"/>' +
  '<ellipse cx="400" cy="503" rx="66" ry="9" fill="#f4ede0" stroke="#d9cbb2" stroke-width="2"/></g>' +
  '<g data-edu-id="small-pears">' +
  '<g transform="translate(436,483)"><path d="M0,-11.9 C7.65,-11.9 6.8,-2.55 10.2,5.1 C13.6,13.6 6.8,18.7 0,18.7 C-6.8,18.7 -13.6,13.6 -10.2,5.1 C-6.8,-2.55 -7.65,-11.9 0,-11.9Z" fill="#e8c547" stroke="#c9a22e" stroke-width="1.5"/>' +
  '<path d="M0,-11.9 q2,-6 4,-9" stroke="#6b4a2b" stroke-width="2.2" fill="none" stroke-linecap="round"/><path d="M3,-16.15 q8,-6 12,0 q-7,4 -12,0Z" fill="#6aa14a"/></g>' +
  '<g transform="translate(462,485) rotate(8)"><path d="M0,-11.9 C7.65,-11.9 6.8,-2.55 10.2,5.1 C13.6,13.6 6.8,18.7 0,18.7 C-6.8,18.7 -13.6,13.6 -10.2,5.1 C-6.8,-2.55 -7.65,-11.9 0,-11.9Z" fill="#e8c547" stroke="#c9a22e" stroke-width="1.5"/>' +
  '<path d="M0,-11.9 q2,-6 4,-9" stroke="#6b4a2b" stroke-width="2.2" fill="none" stroke-linecap="round"/><path d="M3,-16.15 q8,-6 12,0 q-7,4 -12,0Z" fill="#6aa14a"/></g></g>' +
  '<g data-edu-id="table-pear" transform="' + pearOnTable + '">' +
  '<path d="M0,-17.5 C11.25,-17.5 10,-3.75 15,7.5 C20,20 10,27.5 0,27.5 C-10,27.5 -20,20 -15,7.5 C-10,-3.75 -11.25,-17.5 0,-17.5Z" fill="#e8c547" stroke="#c9a22e" stroke-width="1.5"/>' +
  '<path d="M-6.25,5 q-3.75,7.5 0,15" stroke="#f6e08c" stroke-width="3" fill="none" stroke-linecap="round"/>' +
  '<path d="M0,-17.5 q2,-6 4,-9" stroke="#6b4a2b" stroke-width="2.2" fill="none" stroke-linecap="round"/>' +
  '<path d="M3,-23.75 q8,-6 12,0 q-7,4 -12,0Z" fill="#6aa14a"/></g>');

// The brother is created first: Kong Rong's arm and the pear are drawn over the brother's
// reaching hand, so the pear rests in that hand instead of being covered by his sleeve.
const brother = ctx.actor('brother');
const kr = ctx.actor('kongrong');
const heldPear = ctx.$('[data-actor="kongrong"] [data-prop="pear"]')[0];
const tablePear = ctx.$('[data-edu-id="table-pear"]')[0];

// "再来讲个孔融让梨的故事": the title.
tl.from(ctx.$('[data-edu-id="title"]'), {opacity: 0, y: 10, duration: 0.5, ease: 'power2.out'}, 0.15);
ctx.motion.highlight('[data-edu-id="title"]', ctx.cue('孔融让梨'), {style: 'underline', color: '#d0603f',
  dur: ctx.cueEnd('故事') - ctx.cue('孔融让梨')});
kr.expression('blink', 1.3); kr.expression('calm', 1.42);
brother.expression('blink', 1.9); brother.expression('calm', 2.02);

// "孔融拿起最大的梨": reach to the table, take the big pear, lift it to the chest.
const pick = ctx.cue('拿');
kr.pose({arm_back: REACH, head: 6}, pick - 0.35, 0.45, 'power2.out');
tl.set(tablePear, {visibility: 'hidden'}, pick + 0.12);
tl.set(heldPear, {visibility: 'visible'}, pick + 0.12);
kr.pose({arm_back: HOLD, head: 0}, pick + 0.25, 0.5, 'power1.inOut');
kr.expression('smile', ctx.cue('最大'));

// "走到哥哥身边": three steps to the right with a small bob and an arm swing.
const walk = ctx.cue('走到'), steps = ctx.cueEnd('身边') - walk;
kr.moveTo({x: KR.x1}, walk, steps, 'power1.inOut');
for (let i = 0; i < 3; i++) {
  const t0 = walk + steps * i / 3, half = steps / 6;
  kr.moveTo({y: KR.y - 6}, t0, half, 'sine.out');
  kr.moveTo({y: KR.y}, t0 + half, half, 'sine.in');
  kr.pose({arm_front: i % 2 ? -4 : 20}, t0, steps / 3, 'sine.inOut');
}
kr.pose({arm_front: 8}, walk + steps, 0.25);

// "把梨递给哥哥": hold the pear out; the brother reaches for it.
kr.pose({arm_back: GIVE, head: -4}, ctx.cue('把'), 0.5, 'power2.out');
brother.pose({arm_back: -70}, ctx.cue('给'), 0.5, 'power2.out');
brother.expression('smile', ctx.cue('给'));

// "哥哥笑着点了点头": a happy squint and two nods.
brother.expression('joy', ctx.cue('笑'));
kr.expression('joy', ctx.cue('笑') + 0.2);
const nod = ctx.cue('点', 1);
brother.pose({head: 12}, nod, 0.22, 'power2.out');
brother.pose({head: 0}, nod + 0.22, 0.22, 'power2.in');
brother.pose({head: 12}, nod + 0.48, 0.22, 'power2.out');
brother.pose({head: 0}, nod + 0.7, 0.25, 'power2.inOut');

ctx.endState({keep: ['title']});

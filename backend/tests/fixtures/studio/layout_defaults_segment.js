// The scene helpers with their default layout (mapRoute has no default position, so it uses
// the API.md example's points). Every label must stay above the subtitle zone (y > 625).
ctx.motion.timeline([{time: '1637', label: '笛卡尔'}, {time: '1687', label: '牛顿'}, '今天'], 0, 1);
ctx.motion.mapRoute([{x: 900, y: 300, label: '北京'}, [1000, 380], {x: 1150, y: 330, label: '上海'}], 0, 1);
ctx.motion.scaleCompare([{label: '地球', value: 1}, {label: '木星', value: 11}], 1, 1);

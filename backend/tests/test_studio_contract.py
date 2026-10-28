import pytest
from pydantic import ValidationError

from app.studio.contract import (ActorState, Camera, Highlight, Seam, Segment, StageState,
                                 state_diff)
from app.studio.lint import lint_segment
from app.studio.words import Word


def test_lint_rejects_clock_random_network_and_global_dom():
    for bad in ('setTimeout(f,1)', 'Date.now()', 'Math.random()', 'fetch("/x")',
                'document.querySelector("a")', 'window.foo=1', 'gsap.ticker.add(f)', 'eval("1")'):
        assert lint_segment(bad), bad
    assert lint_segment('ctx.tl.to(ctx.$("#a"),{x:10,duration:1},ctx.cue("顶点"))') == []


@pytest.mark.parametrize('code,label', [
    ('setTimeout(f,1)', 'setTimeout'),
    ('setInterval(f,1)', 'setInterval'),
    ('requestAnimationFrame(f)', 'requestAnimationFrame'),
    ('Date.now()', 'Date.now'),
    ('Date . now ()', 'Date.now'),
    ('new Date()', 'new Date'),
    ('new   Date(1)', 'new Date'),
    ('performance.now()', 'performance.now'),
    ('Math . random ()', 'Math.random'),
    ('fetch("/x")', 'fetch'),
    ('new XMLHttpRequest()', 'XMLHttpRequest'),
    ('new WebSocket(u)', 'WebSocket'),
    ('new EventSource(u)', 'EventSource'),
    ('import("x")', 'import('),
    ('import ("x")', 'import('),
    ('eval("1")', 'eval'),
    ('new Function("a")', 'new Function'),
    ('localStorage.x', 'localStorage'),
    ('sessionStorage.x', 'sessionStorage'),
    ('indexedDB.open()', 'indexedDB'),
    ('window.x=1', 'window.'),
    ('window .x=1', 'window.'),
    ('parent.postMessage(1)', 'parent.'),
    ('top.location=1', 'top.'),
    ('document.querySelector("a")', 'document.querySelector'),
    ('document.body.append(x)', 'document.body'),
    ('gsap.ticker.add(f)', 'gsap.ticker'),
    ('gsap.globalTimeline.clear()', 'gsap.globalTimeline'),
])
def test_lint_reports_each_banned_token(code, label):
    assert f'{label} 不允许使用' in lint_segment(code)


def test_lint_allows_lookalikes_and_property_access():
    ok = 'const prefetch = 1; ctx.top.y = 2; el.parent.x = 3; ctx.random(); const evaluate = 4;'
    assert lint_segment(ok) == []


def test_lint_reports_every_hit_once():
    issues = lint_segment('setTimeout(a,1); setTimeout(b,2); Math.random()')
    assert issues == ['setTimeout 不允许使用', 'Math.random 不允许使用']


def test_state_diff_tolerances():
    a = StageState(actors={'kr': ActorState(x=100, y=600)})
    assert state_diff(a, StageState(actors={'kr': ActorState(x=101.5, y=600)})) == []
    assert state_diff(a, StageState(actors={'kr': ActorState(x=110, y=600)}))
    assert state_diff(a, StageState(actors={'kr': ActorState(x=100, y=600, flip=True)}))
    assert state_diff(a, StageState())


def test_state_diff_scale_pose_camera_and_keep():
    a = StageState(actors={'kr': ActorState(x=1, y=1, pose={'arm': 10})})
    same = StageState(actors={'kr': ActorState(x=1, y=1, scale=1.005, pose={'arm': 11.5})})
    assert state_diff(a, same) == []
    assert state_diff(a, StageState(actors={'kr': ActorState(x=1, y=1, scale=1.05, pose={'arm': 10})}))
    assert state_diff(a, StageState(actors={'kr': ActorState(x=1, y=1, pose={'arm': 14})}))
    assert state_diff(a, StageState(actors={'kr': ActorState(x=1, y=1, pose={'arm': 10, 'leg': 30})}))
    assert state_diff(StageState(), StageState(camera=Camera(zoom=1.2)))
    assert state_diff(StageState(), StageState(camera=Camera(x=700)))
    assert state_diff(StageState(), StageState(keep=['title']))
    assert state_diff(StageState(keep=['title']), StageState(keep=['title'])) == []


def test_state_diff_pose_angles_wrap_around():
    def pose(deg):
        return StageState(actors={'kr': ActorState(x=1, y=1, pose={'arm': deg})})
    assert state_diff(pose(359), pose(1)) == []  # 2 degrees apart across 0
    assert state_diff(pose(200), pose(-160)) == []  # the runtime reads poses back in -180..180
    assert state_diff(pose(-179), pose(180)) == []
    assert state_diff(pose(720), pose(0)) == []
    assert state_diff(pose(10), pose(20))
    assert state_diff(pose(170), pose(-170))  # 20 degrees apart across 180
    assert state_diff(pose(0), pose(180))


def test_state_diff_messages_are_chinese_and_name_the_actor():
    diffs = state_diff(StageState(actors={'kr': ActorState(x=0, y=0)}),
                       StageState(actors={'kr': ActorState(x=50, y=0)}))
    assert len(diffs) == 1 and 'kr' in diffs[0] and 'x' in diffs[0]


def test_seam_ranges_and_transition_name():
    assert Seam(kind='continue', duration=0.6).transition is None
    assert Seam(kind='transition', transition='push', duration=1.5).duration == 1.5
    for bad in ({'kind': 'continue', 'duration': 0.7},
                {'kind': 'continue', 'duration': -0.1},
                {'kind': 'transition', 'duration': 0.8},
                {'kind': 'transition', 'transition': 'push', 'duration': 0.2},
                {'kind': 'transition', 'transition': 'push', 'duration': 1.6},
                {'kind': 'transition', 'transition': 'spin', 'duration': 0.8},
                {'kind': 'continue', 'duration': 0.1, 'extra': 1}):
        with pytest.raises(ValidationError):
            Seam(**bad)


def _segment(**over):
    base = dict(id='a', code='', duration=2, words=[], narration='', start_state=StageState(),
                end_state=StageState())
    return Segment(**{**base, **over})


def test_segment_validation():
    assert _segment(id='step-1').id == 'step-1'
    for bad in ({'id': 'Bad'}, {'id': ''}, {'id': 'a' * 41}, {'id': 'a_b'},
                {'duration': 0.4}, {'duration': 121}, {'code': 'x' * 200_001}, {'extra': 1}):
        with pytest.raises(ValidationError):
            _segment(**bad)
    assert len(_segment(code='x' * 200_000).code) == 200_000


def test_models_forbid_extra_and_nan():
    with pytest.raises(ValidationError):
        ActorState(x=1, y=1, bogus=1)
    with pytest.raises(ValidationError):
        Camera(x=float('nan'))
    with pytest.raises(ValidationError):
        Highlight(phrase='', target='a')
    with pytest.raises(ValidationError):
        Highlight(phrase='x', occurrence=0, target='a')


def test_defaults_are_not_shared_between_instances():
    a, b = StageState(), StageState()
    a.actors['x'] = ActorState(x=1, y=1)
    a.keep.append('t')
    assert b.actors == {} and b.keep == []


def test_segment_serialises_words_to_plain_dicts():
    seg = _segment(words=[Word('你好', 0.0, 0.5, 0, 2)], highlights=[Highlight(phrase='你好', target='t')])
    dumped = seg.model_dump(mode='json')
    assert dumped['words'][0] == {'text': '你好', 'start': 0.0, 'end': 0.5, 'char_start': 0, 'char_end': 2}
    assert dumped['highlights'][0] == {'phrase': '你好', 'occurrence': 1, 'target': 't'}

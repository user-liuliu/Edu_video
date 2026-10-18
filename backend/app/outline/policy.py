"""将管理员生成参数落实到大纲校验和教师可见提示。"""
def validate_visual_counts(outline, params):
    if not params:return
    low,high=params['segment_visuals_min'],params['segment_visuals_max']
    if any(not low<=len(s['visuals'])<=high for s in outline['segments']):
        raise ValueError(f'每段画面数必须在 {low}—{high} 之间，请调整后重新审核')

def apply_duration_warning(outline, form_values, params):
    prefix='时长偏差：'
    for s in outline['segments']:
        s['review_notes']=[n for n in s['review_notes'] if not n.startswith(prefix)]
    target=form_values.get('duration_seconds')
    if not target or not params:return outline
    actual=sum(s['estimated_duration_seconds'] for s in outline['segments'])
    tolerance=params['duration_tolerance_pct']
    if abs(actual-target)/target*100>tolerance:
        outline['segments'][0]['review_notes'].insert(0,f'{prefix}讲稿预计 {actual} 秒，目标 {target} 秒，超出允许偏差 {tolerance}%；请教师调整讲稿后重新审核。')
    return outline

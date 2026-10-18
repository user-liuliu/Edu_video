import type {Segment} from '../api/outline'

export type ReviewState='pending'|'failed'|'passed'
export function segmentReviewState(segment:Segment,contentChanged=false):ReviewState{
 if(contentChanged||segment.content_revision!==segment.reviewed_revision||typeof segment.review_passed!=='boolean')return 'pending'
 return segment.review_passed?'passed':'failed'
}

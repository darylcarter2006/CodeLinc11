import { AssessmentPanel } from '../components/AssessmentPanel'
import { ChatPanel } from '../components/ChatPanel'
import { useSession } from '../session/context'

export function PlannerPage() {
  const { status, state } = useSession()

  if (status === 'loading') return <p className="muted">Starting your session…</p>
  if (status === 'error' || !state)
    return <p className="error-text">Couldn't connect to the planner. Make sure the backend is running on port 8000.</p>

  return (
    <div className="planner-grid">
      <ChatPanel />
      <AssessmentPanel assessment={state.assessment} />
    </div>
  )
}

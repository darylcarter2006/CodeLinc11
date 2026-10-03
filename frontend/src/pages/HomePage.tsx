import { Link } from 'react-router-dom'

export function HomePage() {
  return (
    <div className="home">
      <h1>How much life insurance might your family need?</h1>
      <p className="lead">
        Answer a few questions about your dependents, income, debts, and existing coverage. We'll estimate your
        coverage gap and show exactly how we got there.
      </p>
      <ul className="feature-list">
        <li>Takes about 5 minutes. No name, SSN, or account numbers needed.</li>
        <li>See every number in the calculation, not just a total.</li>
        <li>Your answers are deleted automatically after 4 hours, or when you choose "Start over".</li>
      </ul>
      <div className="button-row">
        <Link to="/planner" className="button">
          Get started
        </Link>
        <Link to="/learn" className="button secondary">
          Term vs. permanent coverage
        </Link>
      </div>
    </div>
  )
}

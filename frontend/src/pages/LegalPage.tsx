import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

/* Privacy policy and terms of service. Plain pages anyone can open, signed in or not.
   The privacy policy matches docs/data-handling.md; change both together. */

const UPDATED = 'October 4, 2026'
const CONTACT = 'darylcarter2006@gmail.com'

function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className="card pad legal">
      <div className="eyebrow">Coverage Compass</div>
      <h2>{title}</h2>
      <p className="muted small">Last updated {UPDATED}</p>
      {children}
      <p className="muted small">
        Questions? Email <a href={`mailto:${CONTACT}`}>{CONTACT}</a>. See also the{' '}
        {title === 'Privacy policy' ? <Link to="/terms">terms of service</Link> : <Link to="/privacy">privacy policy</Link>}.
      </p>
    </article>
  )
}

export function PrivacyPage() {
  return (
    <LegalPage title="Privacy policy">
      <p>
        Coverage Compass is an educational life insurance needs estimator built by a student team for the codeLinc 11 coding
        challenge. This policy explains what it collects, why, where it goes and for how long. We keep only what the estimate
        needs, and we never sell your information or use it for advertising.
      </p>

      <h3>What we collect</h3>
      <ul>
        <li>
          <strong>Your account:</strong> your first name and email address, and a password stored only as a secure one-way
          hash (never the password itself). If you sign in with Google, we receive your name, email address and profile
          picture link from Google, and nothing else from your Google account.
        </li>
        <li>
          <strong>Your answers:</strong> who depends on your income, the number and age of your children, your income, years
          of support, mortgage and other debts, college plans, coverage you already have, savings you choose to count, a
          comfortable monthly budget, and five coverage preferences. These are used only to compute and explain your estimate.
        </li>
        <li>
          <strong>Callback requests:</strong> if you ask a licensed representative to contact you, your name, the one contact
          method you choose, what you want help with, and, only if you tick the box, a summary of your estimate.
        </li>
      </ul>
      <p>
        We never ask for Social Security, bank, card or policy numbers, medical details or your date of birth, and the callback
        form rejects anything that looks like an account or Social Security number.
      </p>

      <h3>Where it goes and how long we keep it</h3>
      <ul>
        <li>
          <strong>Your browser</strong> keeps only your sign-in token, its expiry, your name and email to show, and your display
          settings. Your answers stay in memory while the page is open and are not left behind when you sign out.
        </li>
        <li>
          <strong>Our database</strong> (encrypted, on Amazon Web Services in the United States) keeps your account and saved
          answers so you can pick up on any device, until you delete your account, or{' '}
          <strong>180 days after you last sign in</strong>, when we delete them automatically. Callback requests are deleted
          after <strong>30 days</strong>. Sign-in tokens last 7 days and password reset links 30 minutes, and both are stored
          only as hashes. Database backups are kept for 7 days, so a deletion is complete within a week.
        </li>
        <li>
          <strong>Our AI assistant</strong> (Claude, provided by Anthropic) receives your answers and recent chat messages when
          you use onboarding or Chat, so it can read your replies and explain your estimate. It never receives your name, email
          or password. The amounts you see are always computed by our own code, and the assistant's answers are checked against
          them.
        </li>
        <li>
          <strong>Google</strong> provides sign-in (if you choose it) and the fonts this site uses, so Google can see your
          browser's address when the page loads.
        </li>
        <li>
          <strong>Email</strong> (Amazon Simple Email Service) is used only to send password reset links you ask for.
        </li>
        <li>
          <strong>Our logs</strong> record only technical details such as the time, page and response status, never your
          answers, email or contact details, and are kept for 30 days.
        </li>
      </ul>
      <p>We do not use cookies or tracking for analytics or advertising.</p>

      <h3>Your choices</h3>
      <ul>
        <li>Change any answer at any time in My info.</li>
        <li>
          Delete your account and everything we keep for it at any time: My info → <em>Delete my account and answers</em>.
          This can't be undone.
        </li>
        <li>Use "Explore with example data" to try the tool without giving us anything.</li>
        <li>Email us to ask what we hold about you, or to have it corrected or deleted.</li>
      </ul>

      <h3>Children</h3>
      <p>Coverage Compass is meant for adults and is not directed to anyone under 18.</p>

      <h3>Changes</h3>
      <p>If we change this policy, we'll update the date above. Significant changes will be shown in the app.</p>
    </LegalPage>
  )
}

export function TermsPage() {
  return (
    <LegalPage title="Terms of service">
      <p>
        Coverage Compass is an educational concept built by a student team for the codeLinc 11 coding challenge. By creating an
        account or using it, you agree to these terms.
      </p>

      <h3>An estimate, not advice or a quote</h3>
      <p>
        Coverage Compass gives a general, educational estimate of how much life insurance might fit, using simple stated
        assumptions and the answers you give. It is not financial, legal, tax or insurance advice, it is not a quote or an offer
        of insurance, and it does not recommend a specific product. Its assistant can make mistakes. Before making a decision,
        talk to a licensed professional who can look at your full situation.
      </p>

      <h3>Your account</h3>
      <ul>
        <li>Give accurate information, and keep your password to yourself. You're responsible for activity on your account.</li>
        <li>You must be 18 or older.</li>
        <li>You can delete your account at any time in My info. We may delete accounts that haven't been used for 180 days.</li>
      </ul>

      <h3>Acceptable use</h3>
      <p>Don't misuse the service: for example, don't try to</p>
      <ul>
        <li>break or overload it;</li>
        <li>get around its limits or security;</li>
        <li>access other people's accounts or information;</li>
        <li>use the assistant for anything other than life insurance planning;</li>
        <li>or enter other people's personal information without permission.</li>
      </ul>
      <p>We may suspend or remove access that breaks these rules.</p>

      <h3>No warranty</h3>
      <p>
        The service is provided as is and as available, without warranties of any kind, as part of a coding challenge. It may
        change, have errors or stop at any time. To the extent the law allows, the team that built it is not liable for any
        loss arising from your use of it or from decisions you make based on its estimates.
      </p>

      <h3>Privacy</h3>
      <p>
        How we handle your information is described in the <Link to="/privacy">privacy policy</Link>.
      </p>

      <h3>Changes</h3>
      <p>We may update these terms. We'll change the date above, and continuing to use the service means you accept them.</p>
    </LegalPage>
  )
}

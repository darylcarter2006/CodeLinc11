import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { HomeRedirect, RouteGuard } from './components/RouteGuard'
import { AuthPage } from './pages/AuthPage'
import { BreakdownPage } from './pages/BreakdownPage'
import { ChatPage } from './pages/ChatPage'
import { DashboardPage } from './pages/DashboardPage'
import { PrivacyPage, TermsPage } from './pages/LegalPage'
import { MyInfoPage } from './pages/MyInfoPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'

/* Routes: auth → onboarding → app tabs. Guards send each user to the area they belong in. */
export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomeRedirect />} />
        <Route path="auth" element={<RouteGuard area="auth"><AuthPage /></RouteGuard>} />
        <Route path="onboarding" element={<RouteGuard area="onboarding"><OnboardingPage /></RouteGuard>} />
        <Route path="dashboard" element={<RouteGuard area="app"><DashboardPage /></RouteGuard>} />
        <Route path="breakdown" element={<RouteGuard area="app"><BreakdownPage /></RouteGuard>} />
        <Route path="info" element={<RouteGuard area="app"><MyInfoPage /></RouteGuard>} />
        <Route path="chat" element={<RouteGuard area="app"><ChatPage /></RouteGuard>} />
        {/* Opened from a reset email, signed in or not. */}
        <Route path="reset-password" element={<ResetPasswordPage />} />
        {/* Open to everyone, signed in or not. */}
        <Route path="privacy" element={<PrivacyPage />} />
        <Route path="terms" element={<TermsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

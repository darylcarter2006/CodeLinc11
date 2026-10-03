import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { HomePage } from './pages/HomePage'
import { LearnPage } from './pages/LearnPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PlannerPage } from './pages/PlannerPage'
import { ProfilePage } from './pages/ProfilePage'
import { SessionProvider } from './session/SessionContext'

export default function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="planner" element={<PlannerPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="learn" element={<LearnPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  )
}

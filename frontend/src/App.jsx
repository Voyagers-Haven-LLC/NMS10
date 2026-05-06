import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Expedition from './pages/Expedition'
import CivsAndBases from './pages/CivsAndBases'
import BaseDetail from './pages/BaseDetail'
import Meetups from './pages/Meetups'
import Socials from './pages/Socials'
import FAQ from './pages/FAQ'
import AdminLogin from './admin/AdminLogin'
import AdminPanel from './admin/AdminPanel'
import { useAuth } from './context/AuthContext'

function AdminRoute() {
  const { isAuthed } = useAuth()
  return isAuthed ? <AdminPanel /> : <AdminLogin />
}

function NotFound() {
  return (
    <div className="container">
      <div className="page-header">
        <h1 className="page-title">404</h1>
        <div className="page-meta">That page doesn't exist.</div>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Expedition />} />
        <Route path="/civs" element={<CivsAndBases />} />
        <Route path="/civs/bases/:id" element={<BaseDetail />} />
        <Route path="/meetups" element={<Meetups />} />
        <Route path="/socials" element={<Socials />} />
        <Route path="/faq" element={<FAQ />} />
        <Route path="/admin" element={<AdminRoute />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  )
}

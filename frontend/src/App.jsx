import { Routes, Route, Link, useParams } from 'react-router-dom'
import './App.css'

function Layout({ children }) {
  return (
    <div className="layout">
      <header className="site-header">
        <Link to="/" className="brand">NMS10</Link>
        <nav>
          <Link to="/">Expedition</Link>
          <Link to="/civs">Civs &amp; Bases</Link>
          <Link to="/meetups">Meetups</Link>
          <Link to="/socials">Socials</Link>
          <Link to="/faq">FAQ</Link>
          <Link to="/admin">Admin</Link>
        </nav>
      </header>
      <main className="site-main">{children}</main>
      <footer className="site-footer">
        <small>NMS10 anniversary site — placeholder build. Live launch ~July 9, 2026.</small>
      </footer>
    </div>
  )
}

function Placeholder({ title, blurb }) {
  return (
    <section className="placeholder">
      <h1>{title}</h1>
      <p>{blurb}</p>
      <p className="muted">Placeholder route — full v9 mockup port lands in a later session.</p>
    </section>
  )
}

function Expedition() {
  return <Placeholder title="Expedition" blurb="Landing page, milestones, countdown, reward card." />
}

function CivsAndBases() {
  return <Placeholder title="Civs & Bases" blurb="Communities directory, bases grid, tab switcher." />
}

function BaseDetail() {
  const { id } = useParams()
  return <Placeholder title={`Base: ${id}`} blurb="Single base detail view — gallery, builder notes, portal address." />
}

function Meetups() {
  return <Placeholder title="Meetups" blurb="Leaflet map + list of IRL meetups, region filter." />
}

function Socials() {
  return <Placeholder title="Socials" blurb="Aggregated post grid from Bluesky, YouTube, Reddit, Twitter, Instagram, TikTok." />
}

function FAQ() {
  return <Placeholder title="FAQ" blurb="Accordion of frequently asked questions + downloads section." />
}

function Admin() {
  return <Placeholder title="Admin" blurb="Login + moderation queue. Auth-gated, JWT." />
}

function NotFound() {
  return <Placeholder title="404" blurb="That page doesn't exist." />
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
        <Route path="/admin" element={<Admin />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  )
}

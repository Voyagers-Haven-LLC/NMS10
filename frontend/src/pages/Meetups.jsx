import { useEffect, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import { api } from '../api/client'
import Modal from '../components/Modal'
import { useToast } from '../context/ToastContext'
import { useIdentity } from '../context/IdentityContext'

const REGIONS = [
  { value: 'all', label: 'Worldwide' },
  { value: 'europe', label: 'Europe' },
  { value: 'north-america', label: 'North America' },
  { value: 'asia-pacific', label: 'Asia-Pacific' },
  { value: 'south-america', label: 'South America' },
]

const goldIcon = L.divIcon({
  className: 'nms-marker',
  html: '<div style="width:20px;height:20px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#f5b849,#d68a2c 70%,#8a4f15 100%);box-shadow:0 0 12px rgba(245,184,73,0.7);border:2px solid #07080d;"></div>',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
})

function formatDate(starts_at) {
  if (!starts_at) return ''
  try {
    const d = new Date(starts_at)
    if (isNaN(d.getTime())) return starts_at
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short',
    })
  } catch {
    return starts_at
  }
}

function SubmitMeetupForm({ onSubmitted, onClose }) {
  const { identity } = useIdentity()
  const [form, setForm] = useState(() => ({
    title: '',
    region: 'europe',
    location: '',
    latitude: '',
    longitude: '',
    starts_at: '',
    description: '',
    organizer_name: identity?.name || '',
    contact_url: '',
  }))
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const mapRef = useRef(null)
  const mapDivRef = useRef(null)
  const markerRef = useRef(null)

  useEffect(() => {
    if (!mapDivRef.current || mapRef.current) return
    const map = L.map(mapDivRef.current, { center: [30, 0], zoom: 1, worldCopyJump: true })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
      maxZoom: 18,
    }).addTo(map)
    map.on('click', (e) => {
      const { lat, lng } = e.latlng
      setForm((f) => ({ ...f, latitude: lat.toFixed(4), longitude: lng.toFixed(4) }))
      if (markerRef.current) {
        markerRef.current.setLatLng([lat, lng])
      } else {
        markerRef.current = L.marker([lat, lng], { icon: goldIcon }).addTo(map)
      }
    })
    mapRef.current = map
    setTimeout(() => map.invalidateSize(), 100)
    return () => {
      map.remove()
      mapRef.current = null
      markerRef.current = null
    }
  }, [])

  const onChange = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      const body = {
        ...form,
        latitude: form.latitude !== '' ? Number(form.latitude) : null,
        longitude: form.longitude !== '' ? Number(form.longitude) : null,
      }
      const res = await api('/submissions/meetups', { method: 'POST', body })
      toast.success(`Submitted! Pending moderation as ${res.id}.`)
      onSubmitted?.(res)
      onClose()
    } catch (err) {
      toast.error(`Submission failed: ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <div className="form-grid">
        <div className="form-field span-2">
          <label>Title *</label>
          <input required value={form.title} onChange={onChange('title')} />
        </div>
        <div className="form-field">
          <label>Region</label>
          <select value={form.region} onChange={onChange('region')}>
            <option value="europe">Europe</option>
            <option value="north-america">North America</option>
            <option value="asia-pacific">Asia-Pacific</option>
            <option value="south-america">South America</option>
          </select>
        </div>
        <div className="form-field">
          <label>Location</label>
          <input value={form.location} onChange={onChange('location')} placeholder="London, UK" />
        </div>
        <div className="form-field">
          <label>Latitude</label>
          <input value={form.latitude} onChange={onChange('latitude')} placeholder="51.5074" />
        </div>
        <div className="form-field">
          <label>Longitude</label>
          <input value={form.longitude} onChange={onChange('longitude')} placeholder="-0.1278" />
        </div>
        <div className="form-field span-2">
          <label>Click on map to set lat/lng</label>
          <div ref={mapDivRef} className="map-pick" />
        </div>
        <div className="form-field span-2">
          <label>Starts at (ISO timestamp)</label>
          <input value={form.starts_at} onChange={onChange('starts_at')} placeholder="2026-08-09T18:00:00Z" />
        </div>
        <div className="form-field span-2">
          <label>Description</label>
          <textarea value={form.description} onChange={onChange('description')} />
        </div>
        <div className="form-field">
          <label>Organizer</label>
          <input value={form.organizer_name} onChange={onChange('organizer_name')} />
        </div>
        <div className="form-field">
          <label>Contact URL</label>
          <input value={form.contact_url} onChange={onChange('contact_url')} />
        </div>
      </div>
      <div className="form-actions">
        <button type="button" className="btn secondary" onClick={onClose} disabled={busy}>Cancel</button>
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? 'Submitting…' : 'Submit meetup'}
        </button>
      </div>
    </form>
  )
}

export default function Meetups() {
  const [meetups, setMeetups] = useState([])
  const [region, setRegion] = useState('all')
  const [focused, setFocused] = useState(null)
  const [open, setOpen] = useState(false)
  const mapRef = useRef(null)
  const mapDivRef = useRef(null)
  const markersRef = useRef([])

  const load = () => {
    api('/meetups').then(setMeetups).catch(() => setMeetups([]))
  }
  useEffect(load, [])

  const filtered = useMemo(
    () => meetups.filter((m) => region === 'all' || m.region === region),
    [meetups, region]
  )

  // Init map once
  useEffect(() => {
    if (mapRef.current || !mapDivRef.current) return
    const map = L.map(mapDivRef.current, {
      center: [30, 0],
      zoom: 2,
      worldCopyJump: true,
      minZoom: 2,
    })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
      maxZoom: 18,
    }).addTo(map)
    mapRef.current = map
    setTimeout(() => map.invalidateSize(), 100)
    return () => {
      map.remove()
      mapRef.current = null
      markersRef.current = []
    }
  }, [])

  // Sync markers to filtered meetups
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    markersRef.current.forEach((m) => map.removeLayer(m.marker))
    markersRef.current = filtered.map((m) => {
      const marker = L.marker([m.latitude, m.longitude], { icon: goldIcon })
        .bindPopup(
          `<strong>${m.title}</strong><br>${m.location || ''}<br><span style="color:#9ba2bd">${formatDate(m.starts_at)}</span>`
        )
        .addTo(map)
      marker.on('click', () => setFocused(m.id))
      return { id: m.id, marker }
    })
  }, [filtered])

  // Fly to focused
  useEffect(() => {
    const map = mapRef.current
    if (!map || !focused) return
    const m = filtered.find((x) => x.id === focused)
    if (!m) return
    map.flyTo([m.latitude, m.longitude], 10, { duration: 1.2 })
    const entry = markersRef.current.find((x) => x.id === focused)
    if (entry) entry.marker.openPopup()
  }, [focused, filtered])

  return (
    <div className="container">
      <div className="page-header">
        <div className="page-eyebrow">// In-Person Gatherings</div>
        <h1 className="page-title">Travelers Worldwide</h1>
        <div className="page-meta">Find IRL meetups near you · Click a pin or a card to focus</div>
      </div>

      <div className="filter-section meetup-region-filter">
        <div className="filter-section-label">Region</div>
        <div className="filter-bar" data-filter-group="region">
          {REGIONS.map((r) => (
            <button
              key={r.value}
              className={`filter-chip${region === r.value ? ' active' : ''}`}
              onClick={() => setRegion(r.value)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div className="inline-form-toggle">
        <button className="btn primary" onClick={() => setOpen(true)}>+ Submit a meetup</button>
      </div>

      <div className="meetups-layout">
        <div ref={mapDivRef} id="meetup-map" />

        <div className="meetup-list">
          {filtered.length === 0 ? (
            <div className="empty-state">No meetups in this region yet.</div>
          ) : (
            filtered.map((m) => (
              <div
                key={m.id}
                className={`meetup-card${focused === m.id ? ' focused' : ''}`}
                onClick={() => setFocused(m.id)}
              >
                <div className="meetup-date">{formatDate(m.starts_at)}</div>
                <div className="meetup-title">{m.title}</div>
                <div className="meetup-loc">📍 {m.location}</div>
                {m.description && <div className="meetup-desc">{m.description}</div>}
              </div>
            ))
          )}
        </div>
      </div>

      <Modal open={open} title="Submit a meetup" onClose={() => setOpen(false)} wide>
        <SubmitMeetupForm onSubmitted={load} onClose={() => setOpen(false)} />
      </Modal>
    </div>
  )
}

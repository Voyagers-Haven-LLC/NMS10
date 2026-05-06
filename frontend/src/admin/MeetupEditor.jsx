import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import { apiAuth } from '../api/client'
import { useToast } from '../context/ToastContext'

const goldIcon = L.divIcon({
  className: 'nms-marker',
  html: '<div style="width:20px;height:20px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#f5b849,#d68a2c 70%,#8a4f15 100%);box-shadow:0 0 12px rgba(245,184,73,0.7);border:2px solid #07080d;"></div>',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
})

export default function MeetupEditor({ id, onClose, onSaved }) {
  const isNew = !id
  const [form, setForm] = useState(null)
  const toast = useToast()
  const mapRef = useRef(null)
  const mapDivRef = useRef(null)
  const markerRef = useRef(null)

  useEffect(() => {
    if (isNew) {
      setForm({
        title: '',
        region: 'europe',
        location: '',
        latitude: '',
        longitude: '',
        starts_at: '',
        description: '',
        organizer_name: '',
        contact_url: '',
        approved: true,
      })
      return
    }
    apiAuth('/admin/meetups')
      .then((all) => {
        const m = all.find((x) => x.id === id)
        if (!m) {
          toast.error('Meetup not found')
          return
        }
        setForm({
          ...m,
          latitude: m.latitude ?? '',
          longitude: m.longitude ?? '',
          starts_at: m.starts_at ?? '',
        })
      })
      .catch((e) => toast.error(e.message))
  }, [id, isNew, toast])

  useEffect(() => {
    if (!form || mapRef.current || !mapDivRef.current) return
    const center =
      form.latitude && form.longitude ? [Number(form.latitude), Number(form.longitude)] : [30, 0]
    const zoom = form.latitude && form.longitude ? 6 : 1
    const map = L.map(mapDivRef.current, { center, zoom, worldCopyJump: true })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
      maxZoom: 18,
    }).addTo(map)
    if (form.latitude && form.longitude) {
      markerRef.current = L.marker([Number(form.latitude), Number(form.longitude)], {
        icon: goldIcon,
      }).addTo(map)
    }
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
  }, [form])

  if (!form) return <div className="empty-state">Loading…</div>

  const onChange = (k) => (e) =>
    setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  const save = async (e) => {
    e.preventDefault()
    const payload = {
      title: form.title,
      region: form.region || null,
      location: form.location || null,
      latitude: form.latitude !== '' ? Number(form.latitude) : null,
      longitude: form.longitude !== '' ? Number(form.longitude) : null,
      starts_at: form.starts_at || null,
      description: form.description || null,
      organizer_name: form.organizer_name || null,
      contact_url: form.contact_url || null,
      approved: !!form.approved,
    }
    try {
      const res = isNew
        ? await apiAuth('/admin/meetups', { method: 'POST', body: payload })
        : await apiAuth(`/admin/meetups/${id}`, { method: 'PUT', body: payload })
      toast.success(`Saved ${res.id}.`)
      onSaved?.(res)
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <form onSubmit={save}>
      <div className="form-grid">
        <div className="form-field span-2">
          <label>Title *</label>
          <input required value={form.title} onChange={onChange('title')} />
        </div>
        <div className="form-field">
          <label>Region</label>
          <select value={form.region || ''} onChange={onChange('region')}>
            <option value="">—</option>
            <option value="europe">Europe</option>
            <option value="north-america">North America</option>
            <option value="asia-pacific">Asia-Pacific</option>
            <option value="south-america">South America</option>
          </select>
        </div>
        <div className="form-field">
          <label>Location</label>
          <input value={form.location || ''} onChange={onChange('location')} />
        </div>
        <div className="form-field">
          <label>Latitude</label>
          <input value={form.latitude} onChange={onChange('latitude')} />
        </div>
        <div className="form-field">
          <label>Longitude</label>
          <input value={form.longitude} onChange={onChange('longitude')} />
        </div>
        <div className="form-field span-2">
          <label>Click on map to set location</label>
          <div ref={mapDivRef} className="map-pick" />
        </div>
        <div className="form-field span-2">
          <label>Starts at (ISO)</label>
          <input value={form.starts_at || ''} onChange={onChange('starts_at')} />
        </div>
        <div className="form-field span-2">
          <label>Description</label>
          <textarea value={form.description || ''} onChange={onChange('description')} />
        </div>
        <div className="form-field">
          <label>Organizer</label>
          <input value={form.organizer_name || ''} onChange={onChange('organizer_name')} />
        </div>
        <div className="form-field">
          <label>Contact URL</label>
          <input value={form.contact_url || ''} onChange={onChange('contact_url')} />
        </div>
        <div className="form-field span-2">
          <label>
            <input type="checkbox" checked={!!form.approved} onChange={onChange('approved')} /> Approved (visible publicly)
          </label>
        </div>
      </div>
      <div className="form-actions">
        <button type="button" className="btn secondary" onClick={onClose}>Cancel</button>
        <button type="submit" className="btn primary">{isNew ? 'Create' : 'Save'}</button>
      </div>
    </form>
  )
}

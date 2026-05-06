import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import './styles/fonts.css'
import './styles/v9.css'
import 'leaflet/dist/leaflet.css'
import './index.css'
import './App.css'

import App from './App.jsx'
import { ToastProvider } from './context/ToastContext.jsx'
import { AuthProvider } from './context/AuthContext.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)

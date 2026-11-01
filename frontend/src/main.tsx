import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/base.css'
import App from './App'
import './styles/nuance.css'

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Elemen root tidak ditemukan')

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

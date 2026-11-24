import { useEffect, useState } from 'react'
import { api } from './api'
import Asistencias from './components/Asistencias'
import RegistroManual from './components/RegistroManual'
import CargarJson from './components/CargarJson'
import ConsultaAuto from './components/ConsultaAuto'

const TABS = [
  ['ver', 'Asistencias'],
  ['manual', 'Registro manual'],
  ['json', 'Cargar JSON'],
  ['auto', 'Consulta automática'],
]

export default function App() {
  const [tab, setTab] = useState('ver')
  const [editando, setEditando] = useState(null)
  const [cfg, setCfg] = useState(null)
  const [version, setVersion] = useState(0) // fuerza recarga tras importar

  useEffect(() => {
    api.config().then(setCfg).catch(() => setCfg(null))
  }, [version])

  const refrescar = () => setVersion((v) => v + 1)

  return (
    <div className="app">
      <header>
        <h1>Asistencia por sedes</h1>
        <nav>
          {TABS.map(([k, t]) => (
            <button key={k} className={tab === k ? 'activo' : ''} onClick={() => { setTab(k); if (k !== 'manual') setEditando(null) }}>
              {t}
            </button>
          ))}
        </nav>
      </header>
      <main>
        {tab === 'ver' && (
          <Asistencias
            version={version}
            fotoBase={cfg?.foto_base_url}
            onEditar={(a) => { setEditando(a); setTab('manual') }}
          />
        )}
        {tab === 'manual' && (
          <RegistroManual
            editando={editando}
            onGuardado={() => { setEditando(null); refrescar(); setTab('ver') }}
            onCancelar={() => { setEditando(null); setTab('ver') }}
          />
        )}
        {tab === 'json' && <CargarJson onImportado={refrescar} />}
        {tab === 'auto' && <ConsultaAuto cfg={cfg} onImportado={refrescar} />}
      </main>
    </div>
  )
}

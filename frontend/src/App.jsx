import { useEffect, useState } from 'react'
import { api, onNoAutorizado } from './api'
import Asistencias from './components/Asistencias'
import RegistroManual from './components/RegistroManual'
import CargarJson from './components/CargarJson'
import ConsultaAuto from './components/ConsultaAuto'
import Login from './components/Login'
import CambiarPassword from './components/CambiarPassword'
import Administracion from './components/Administracion'

const TABS = [
  ['ver', 'Asistencias'],
  ['manual', 'Registro manual'],
  ['json', 'Cargar JSON'],
  ['auto', 'Consulta ERP'],
  ['admin', 'Usuarios y sedes', 'ADMIN'],
]

export default function App() {
  const [yo, setYo] = useState(undefined) // undefined = verificando sesión, null = sin sesión
  const [cambiarPwd, setCambiarPwd] = useState(false)
  const [tab, setTab] = useState('ver')
  const [editando, setEditando] = useState(null)
  const [cfg, setCfg] = useState(null)
  const [version, setVersion] = useState(0) // fuerza recarga tras importar

  useEffect(() => {
    onNoAutorizado(() => setYo(null))
    api.me().then(setYo).catch(() => setYo(null))
  }, [])

  useEffect(() => {
    if (yo) api.config().then(setCfg).catch(() => setCfg(null))
  }, [version, yo])

  const refrescar = () => setVersion((v) => v + 1)
  const salir = async () => {
    await api.logout().catch(() => {})
    setYo(null); setTab('ver'); setEditando(null); setCambiarPwd(false)
  }

  if (yo === undefined) return null
  if (!yo) return <Login onIngreso={(u) => { setYo(u); setTab('ver') }} />
  if (yo.debe_cambiar_password || cambiarPwd) {
    return (
      <CambiarPassword
        obligatorio={yo.debe_cambiar_password}
        onListo={(u) => { setYo(u); setCambiarPwd(false) }}
        onCancelar={yo.debe_cambiar_password ? salir : () => setCambiarPwd(false)}
      />
    )
  }

  const esAdmin = yo.rol === 'ADMIN'

  return (
    <div className="app">
      <header>
        <h1>Asistencia por sedes</h1>
        <nav>
          {TABS.filter(([, , rol]) => !rol || rol === yo.rol).map(([k, t]) => (
            <button key={k} className={tab === k ? 'activo' : ''} onClick={() => { setTab(k); if (k !== 'manual') setEditando(null) }}>
              {t}
            </button>
          ))}
        </nav>
        <div className="usuario">
          <span>
            <b>{yo.nombre} {yo.apellido}</b>
            <small>{esAdmin ? 'Administrador · todas las sedes' : `Sede ${yo.sede?.nombre || '—'}`}</small>
          </span>
          <button onClick={() => setCambiarPwd(true)} title="Cambiar contraseña">🔑</button>
          <button onClick={salir}>Salir</button>
        </div>
      </header>
      <main>
        {tab === 'ver' && (
          <Asistencias
            yo={yo}
            version={version}
            fotoBase={cfg?.foto_base_url}
            onEditar={(a) => { setEditando(a); setTab('manual') }}
            onImportado={refrescar}
          />
        )}
        {tab === 'manual' && (
          <RegistroManual
            yo={yo}
            editando={editando}
            onGuardado={() => { setEditando(null); refrescar(); setTab('ver') }}
            onCancelar={() => { setEditando(null); setTab('ver') }}
          />
        )}
        {tab === 'json' && <CargarJson onImportado={refrescar} />}
        {tab === 'auto' && <ConsultaAuto yo={yo} cfg={cfg} onImportado={refrescar} />}
        {tab === 'admin' && esAdmin && <Administracion yo={yo} />}
      </main>
    </div>
  )
}

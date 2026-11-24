const BASE = import.meta.env.VITE_API_URL || ''

// Se llama cuando la sesión de la web vence (401) para volver al login
let alNoAutorizado = () => {}
export const onNoAutorizado = (fn) => { alNoAutorizado = fn }

async function req(path, opts = {}) {
  const r = await fetch(BASE + path, { credentials: 'include', ...opts })
  if (r.status === 401 && !path.startsWith('/api/auth/login')) alNoAutorizado()
  if (r.status === 204) return null
  const data = await r.json().catch(() => null)
  if (!r.ok) {
    const d = data?.detail
    const msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => `${x.loc?.slice(-1)}: ${x.msg}`).join('; ') : `Error ${r.status}`
    throw new Error(msg)
  }
  return data
}

const qs = (o) => {
  const p = new URLSearchParams()
  Object.entries(o).forEach(([k, v]) => v && p.append(k, v))
  const s = p.toString()
  return s ? `?${s}` : ''
}

const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  asistencias: (f) => req('/api/asistencias' + qs(f)),
  resumen: (f) => req('/api/resumen' + qs(f)),
  sedes: () => req('/api/sedes'),
  estados: () => req('/api/estados'),
  trabajadores: () => req('/api/trabajadores'),
  crear: (d) => req('/api/asistencias', json('POST', d)),
  editar: (id, d) => req(`/api/asistencias/${id}`, json('PUT', d)),
  borrar: (id) => req(`/api/asistencias/${id}`, { method: 'DELETE' }),
  importarJson: (payload) => req('/api/importar/json', json('POST', payload)),
  importarArchivo: (file) => {
    const fd = new FormData()
    fd.append('archivo', file)
    return req('/api/importar/archivo', { method: 'POST', body: fd })
  },
  consultar: (fecha, hasta, sede_id) => req('/api/importar/consulta' + qs({ fecha, hasta, sede_id }), { method: 'POST' }),
  importaciones: () => req('/api/importaciones'),
  config: () => req('/api/config'),

  // Sesión
  login: (usuario, password) => req('/api/auth/login', json('POST', { usuario, password })),
  logout: () => req('/api/auth/logout', { method: 'POST' }),
  me: () => req('/api/auth/me'),
  cambiarPassword: (actual, nueva) => req('/api/auth/cambiar-password', json('POST', { actual, nueva })),

  // Administración (solo ADMIN)
  usuarios: () => req('/api/usuarios'),
  crearUsuario: (d) => req('/api/usuarios', json('POST', d)),
  editarUsuario: (id, d) => req(`/api/usuarios/${id}`, json('PUT', d)),
  borrarUsuario: (id) => req(`/api/usuarios/${id}`, { method: 'DELETE' }),
  crearSede: (d) => req('/api/sedes', json('POST', d)),
  editarSede: (id, d) => req(`/api/sedes/${id}`, json('PUT', d)),
  borrarSede: (id) => req(`/api/sedes/${id}`, { method: 'DELETE' }),
}

export const hoyISO = () => {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 10)
}

export const hhmm = (t) => (t ? t.slice(0, 5) : '')

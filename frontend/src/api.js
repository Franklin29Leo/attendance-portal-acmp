const BASE = import.meta.env.VITE_API_URL || ''

async function req(path, opts = {}) {
  const r = await fetch(BASE + path, opts)
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
  consultar: (fecha, hasta) => req('/api/importar/consulta' + qs({ fecha, hasta }), { method: 'POST' }),
  importaciones: () => req('/api/importaciones'),
  config: () => req('/api/config'),
}

export const hoyISO = () => {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 10)
}

export const hhmm = (t) => (t ? t.slice(0, 5) : '')

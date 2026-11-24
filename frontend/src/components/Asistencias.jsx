import { useEffect, useMemo, useState } from 'react'
import { api, hhmm, hoyISO } from '../api'

const moverDia = (iso, n) => {
  const d = new Date(iso + 'T12:00:00')
  d.setDate(d.getDate() + n)
  return d.toISOString().slice(0, 10)
}

export function Estado({ v }) {
  const c = (v || 'SIN').toLowerCase().split(' ')[0]
  return <span className={`badge b-${c}`}>{v || '—'}</span>
}

export default function Asistencias({ version, fotoBase, onEditar }) {
  const [f, setF] = useState({ fecha: hoyISO(), sede: '', estado: '', q: '' })
  const [filas, setFilas] = useState([])
  const [resumen, setResumen] = useState(null)
  const [sedes, setSedes] = useState([])
  const [estados, setEstados] = useState([])
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [detalle, setDetalle] = useState(null)

  useEffect(() => {
    api.sedes().then(setSedes).catch(() => {})
    api.estados().then(setEstados).catch(() => {})
  }, [version])

  const cargar = () => {
    setCargando(true)
    setError('')
    Promise.all([api.asistencias(f), api.resumen({ fecha: f.fecha, sede: f.sede })])
      .then(([a, r]) => { setFilas(a); setResumen(r) })
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false))
  }

  useEffect(() => {
    const t = setTimeout(cargar, f.q ? 300 : 0)
    return () => clearTimeout(t)
  }, [f, version]) // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const porSede = useMemo(() => {
    const m = {}
    filas.forEach((a) => { const s = a.tienda_nombre || 'SIN SEDE'; m[s] = (m[s] || 0) + 1 })
    return m
  }, [filas])

  const borrar = async (a) => {
    if (!confirm(`¿Eliminar la asistencia de ${a.trabajador_nombre} del ${a.fecha}?`)) return
    try { await api.borrar(a.id); cargar() } catch (e) { alert(e.message) }
  }

  const foto = (p) => (!p ? null : p.startsWith('http') ? p : (fotoBase || '') + p)

  return (
    <section>
      <div className="filtros">
        <div className="dia">
          <button onClick={() => setF({ ...f, fecha: moverDia(f.fecha, -1) })} title="Día anterior">◀</button>
          <input type="date" value={f.fecha} onChange={set('fecha')} />
          <button onClick={() => setF({ ...f, fecha: moverDia(f.fecha, 1) })} title="Día siguiente">▶</button>
          <button onClick={() => setF({ ...f, fecha: hoyISO() })}>Hoy</button>
        </div>
        <select value={f.sede} onChange={set('sede')}>
          <option value="">Todas las sedes</option>
          {sedes.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={f.estado} onChange={set('estado')}>
          <option value="">Todos los estados</option>
          {estados.map((s) => <option key={s}>{s}</option>)}
        </select>
        <input placeholder="Buscar nombre o DNI" value={f.q} onChange={set('q')} />
        <button onClick={cargar}>Actualizar</button>
      </div>

      {resumen && (
        <div className="tarjetas">
          <div className="tarjeta"><span>Total</span><b>{resumen.total}</b></div>
          {Object.entries(resumen.por_estado).map(([e, n]) => (
            <div key={e} className="tarjeta" onClick={() => setF({ ...f, estado: f.estado === e ? '' : e })}>
              <span><Estado v={e} /></span><b>{n}</b>
            </div>
          ))}
        </div>
      )}

      {!f.sede && Object.keys(porSede).length > 1 && (
        <div className="sedes-chips">
          {Object.entries(porSede).map(([s, n]) => (
            <button key={s} className="chip" onClick={() => setF({ ...f, sede: s })}>{s} <b>{n}</b></button>
          ))}
        </div>
      )}

      {error && <div className="alerta error">{error}</div>}

      <div className="tabla-wrap">
        <table>
          <thead>
            <tr>
              <th>Sede</th><th>Trabajador</th><th>DNI</th><th>Estado</th>
              <th>Entrada</th><th>Salida</th><th>Observaciones</th><th>Origen</th><th></th>
            </tr>
          </thead>
          <tbody>
            {filas.map((a) => (
              <tr key={a.id}>
                <td>{a.tienda_nombre}<div className="sub">{a.area}</div></td>
                <td><a href="#" onClick={(e) => { e.preventDefault(); setDetalle(a) }}>{a.trabajador_nombre}</a></td>
                <td>{a.trabajador_dni}</td>
                <td><Estado v={a.estado} /></td>
                <td className="hora">{hhmm(a.hora_entrada)}</td>
                <td className="hora">{hhmm(a.hora_salida)}</td>
                <td className="obs">{a.motivo_ausencia || a.observaciones}</td>
                <td><span className={`origen o-${a.origen.toLowerCase()}`}>{a.origen}</span></td>
                <td className="acciones">
                  <button onClick={() => onEditar(a)} title="Editar">✎</button>
                  <button onClick={() => borrar(a)} title="Eliminar">✕</button>
                </td>
              </tr>
            ))}
            {!filas.length && !cargando && (
              <tr><td colSpan={9} className="vacio">No hay asistencias para estos filtros.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {cargando && <p className="sub">Cargando…</p>}

      {detalle && (
        <div className="modal-fondo" onClick={() => setDetalle(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>{detalle.trabajador_nombre}</h3>
            <p className="sub">DNI {detalle.trabajador_dni} · {detalle.tienda_nombre} · {detalle.fecha}</p>
            <dl>
              <dt>Estado</dt><dd><Estado v={detalle.estado} /></dd>
              <dt>Entrada</dt><dd>{hhmm(detalle.hora_entrada) || '—'}</dd>
              <dt>Salida</dt><dd>{hhmm(detalle.hora_salida) || '—'}</dd>
              {detalle.motivo_ausencia && <><dt>Motivo ausencia</dt><dd>{detalle.motivo_ausencia}</dd></>}
              {detalle.licencia_tipo && <><dt>Licencia</dt><dd>{detalle.licencia_tipo}</dd></>}
              <dt>Observaciones</dt><dd>{detalle.observaciones || '—'}</dd>
              {detalle.lat_entrada && (
                <><dt>Ubicación</dt><dd>
                  <a target="_blank" rel="noreferrer" href={`https://maps.google.com/?q=${detalle.lat_entrada},${detalle.lng_entrada}`}>
                    {detalle.lat_entrada.toFixed(5)}, {detalle.lng_entrada.toFixed(5)}
                  </a>
                </dd></>
              )}
              <dt>Origen</dt><dd>{detalle.origen}{detalle.external_id ? ` (id ${detalle.external_id})` : ''}</dd>
            </dl>
            <div className="fotos">
              {foto(detalle.foto_entrada) && <figure><img src={foto(detalle.foto_entrada)} alt="Entrada" /><figcaption>Entrada</figcaption></figure>}
              {foto(detalle.foto_salida) && <figure><img src={foto(detalle.foto_salida)} alt="Salida" /><figcaption>Salida</figcaption></figure>}
            </div>
            <button onClick={() => setDetalle(null)}>Cerrar</button>
          </div>
        </div>
      )}
    </section>
  )
}

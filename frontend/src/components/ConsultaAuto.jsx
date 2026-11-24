import { useEffect, useState } from 'react'
import { api, hoyISO } from '../api'
import { Resultado } from './CargarJson'

const fmt = (iso) => new Date(iso).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' })

export default function ConsultaAuto({ cfg, onImportado }) {
  const [fecha, setFecha] = useState(hoyISO())
  const [hasta, setHasta] = useState('')
  const [res, setRes] = useState(null)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [hist, setHist] = useState([])

  const cargarHist = () => api.importaciones().then(setHist).catch(() => {})
  useEffect(() => { cargarHist() }, [])

  const consultar = async () => {
    setEnviando(true); setError(''); setRes(null)
    try { setRes(await api.consultar(fecha, hasta)); onImportado() } catch (e) { setError(e.message) } finally { setEnviando(false); cargarHist() }
  }

  return (
    <section className="panel">
      <h2>Consulta al servicio de asistencias</h2>

      <div className="estado-sync">
        {cfg?.api_configurada ? (
          <>
            <p>Servicio: <code>{cfg.api_url}</code></p>
            <p>
              Carga automática: {cfg.sync_activo ? <b className="verde">activa</b> : <b className="rojo">desactivada</b>}
              {cfg.sync_activo && <> · todos los días a las <b>{cfg.sync_horas.join(', ')}</b> ({cfg.zona})</>}
            </p>
            {cfg.proximas?.length > 0 && <p className="sub">Próxima ejecución: {fmt(cfg.proximas[0])}</p>}
          </>
        ) : (
          <div className="alerta aviso">Falta configurar <code>ASISTENCIA_API_URL</code> en <code>backend/.env</code>. Sin eso no se puede consultar ni programar la carga automática.</div>
        )}
      </div>

      <h3>Consultar ahora</h3>
      <div className="fila">
        <label>Fecha<input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></label>
        <label>Hasta (opcional)<input type="date" value={hasta} min={fecha} onChange={(e) => setHasta(e.target.value)} /></label>
        <button className="primario" disabled={enviando || !cfg?.api_configurada} onClick={consultar}>
          {enviando ? 'Consultando…' : 'Consultar y cargar'}
        </button>
      </div>
      {error && <div className="alerta error">{error}</div>}
      <Resultado r={res} />

      <h3>Últimas cargas</h3>
      <div className="tabla-wrap">
        <table>
          <thead><tr><th>Momento</th><th>Origen</th><th>Día</th><th>Leídos</th><th>Nuevos</th><th>Actualizados</th><th>Resultado</th></tr></thead>
          <tbody>
            {hist.map((h) => (
              <tr key={h.id}>
                <td>{fmt(h.momento)}</td><td>{h.origen}</td><td>{h.fecha_consultada || '—'}</td>
                <td>{h.total}</td><td>{h.nuevos}</td><td>{h.actualizados}</td>
                <td className={h.ok ? 'verde' : 'rojo'}>{h.ok ? 'OK' : h.mensaje}</td>
              </tr>
            ))}
            {!hist.length && <tr><td colSpan={7} className="vacio">Aún no hay cargas.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  )
}

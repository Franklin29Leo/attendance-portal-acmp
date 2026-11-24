import { useState } from 'react'
import { api } from '../api'

export function Resultado({ r }) {
  if (!r) return null
  return (
    <div className="alerta ok">
      Registros leídos: <b>{r.total}</b> · nuevos: <b>{r.nuevos}</b> · actualizados: <b>{r.actualizados}</b>
      {r.omitidos > 0 && <> · omitidos: <b>{r.omitidos}</b></>}
      {r.errores?.length > 0 && <ul>{r.errores.map((e, i) => <li key={i}>{e}</li>)}</ul>}
    </div>
  )
}

export default function CargarJson({ onImportado }) {
  const [texto, setTexto] = useState('')
  const [archivo, setArchivo] = useState(null)
  const [res, setRes] = useState(null)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const previa = (() => {
    if (!texto.trim()) return null
    try {
      const p = JSON.parse(texto)
      const lista = Array.isArray(p) ? p : p.asistencias
      return Array.isArray(lista) ? { n: lista.length, fechas: [...new Set(lista.map((x) => x.fecha))].join(', ') } : { err: 'No se encontró la lista "asistencias".' }
    } catch (e) {
      return { err: 'JSON inválido: ' + e.message }
    }
  })()

  const ejecutar = async (fn) => {
    setEnviando(true); setError(''); setRes(null)
    try { setRes(await fn()); onImportado() } catch (e) { setError(e.message) } finally { setEnviando(false) }
  }

  return (
    <section className="panel">
      <h2>Cargar JSON manualmente</h2>
      <p className="sub">Pega la respuesta completa del GET (<code>{'{"ok":true,"asistencias":[...]}'}</code>) o sube el archivo .json/.txt. Si un registro ya existe (mismo <code>id</code>) se actualiza; no se duplica.</p>

      <h3>Subir archivo</h3>
      <div className="fila">
        <input type="file" accept=".json,.txt,application/json,text/plain" onChange={(e) => setArchivo(e.target.files[0])} />
        <button className="primario" disabled={!archivo || enviando} onClick={() => ejecutar(() => api.importarArchivo(archivo))}>Importar archivo</button>
      </div>

      <h3>Pegar JSON</h3>
      <textarea className="json" rows={12} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder='{"ok":true,"asistencias":[ ... ]}' />
      {previa && (previa.err ? <div className="alerta error">{previa.err}</div> : <p className="sub">{previa.n} registros · fechas: {previa.fechas}</p>)}
      <button className="primario" disabled={!previa || previa.err || enviando} onClick={() => ejecutar(() => api.importarJson(JSON.parse(texto)))}>
        {enviando ? 'Importando…' : 'Importar JSON'}
      </button>

      {error && <div className="alerta error">{error}</div>}
      <Resultado r={res} />
    </section>
  )
}

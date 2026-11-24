import { useEffect, useState } from 'react'
import { api, hhmm, hoyISO } from '../api'

const vacio = () => ({
  fecha: hoyISO(), trabajador_nombre: '', trabajador_dni: '', estado: 'PUNTUAL',
  hora_entrada: '', hora_salida: '', tienda_nombre: '', area: '', motivo_ausencia: '', observaciones: '',
})

export default function RegistroManual({ editando, onGuardado, onCancelar }) {
  const [d, setD] = useState(vacio())
  const [trab, setTrab] = useState([])
  const [sedes, setSedes] = useState([])
  const [estados, setEstados] = useState([])
  const [msg, setMsg] = useState(null)
  const [guardando, setGuardando] = useState(false)

  useEffect(() => {
    api.trabajadores().then(setTrab).catch(() => {})
    api.sedes().then(setSedes).catch(() => {})
    api.estados().then(setEstados).catch(() => {})
  }, [])

  useEffect(() => {
    if (editando) {
      const x = { ...vacio() }
      Object.keys(x).forEach((k) => { if (editando[k] != null) x[k] = editando[k] })
      x.hora_entrada = hhmm(editando.hora_entrada)
      x.hora_salida = hhmm(editando.hora_salida)
      setD(x)
    } else setD(vacio())
  }, [editando])

  const set = (k) => (e) => setD({ ...d, [k]: e.target.value })

  // Al escribir el nombre o el DNI de alguien ya registrado, completa el resto
  const elegirTrabajador = (k) => (e) => {
    const v = e.target.value
    const t = trab.find((t) => (k === 'trabajador_nombre' ? t.nombre === v : t.dni === v))
    setD(t ? { ...d, trabajador_nombre: t.nombre, trabajador_dni: t.dni || '', tienda_nombre: d.tienda_nombre || t.sede || '', area: d.area || t.area || '' } : { ...d, [k]: v })
  }

  const enviar = async (e) => {
    e.preventDefault()
    setGuardando(true)
    setMsg(null)
    const body = Object.fromEntries(Object.entries(d).map(([k, v]) => [k, v === '' ? null : v]))
    try {
      if (editando) await api.editar(editando.id, body)
      else await api.crear(body)
      setMsg({ ok: true, t: 'Asistencia guardada.' })
      if (editando) onGuardado()
      else setD({ ...vacio(), fecha: d.fecha, tienda_nombre: d.tienda_nombre })
    } catch (err) {
      setMsg({ ok: false, t: err.message })
    } finally {
      setGuardando(false)
    }
  }

  const sinHora = ['FALTA', 'LICENCIA', 'VACACIONES'].includes(d.estado)

  return (
    <section className="panel">
      <h2>{editando ? `Editar asistencia #${editando.id}` : 'Registrar asistencia manualmente'}</h2>
      {editando?.origen && editando.origen !== 'MANUAL' && (
        <div className="alerta aviso">Este registro vino de {editando.origen}. Si se vuelve a importar el mismo día, la próxima carga sobrescribirá estos cambios.</div>
      )}
      <form onSubmit={enviar} className="form">
        <label>Fecha<input type="date" required value={d.fecha} onChange={set('fecha')} /></label>
        <label className="ancho">Trabajador (apellidos, nombre)
          <input list="lista-trab" required value={d.trabajador_nombre} onChange={elegirTrabajador('trabajador_nombre')} />
        </label>
        <label>DNI<input list="lista-dni" value={d.trabajador_dni} onChange={elegirTrabajador('trabajador_dni')} maxLength={20} /></label>
        <label>Sede
          <input list="lista-sedes" value={d.tienda_nombre} onChange={set('tienda_nombre')} />
        </label>
        <label>Área<input value={d.area} onChange={set('area')} /></label>
        <label>Estado
          <select value={d.estado} onChange={set('estado')}>
            {estados.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label>Hora de entrada<input type="time" value={d.hora_entrada} onChange={set('hora_entrada')} disabled={sinHora} /></label>
        <label>Hora de salida<input type="time" value={d.hora_salida} onChange={set('hora_salida')} disabled={sinHora} /></label>
        {sinHora && <label className="ancho">Motivo<input value={d.motivo_ausencia} onChange={set('motivo_ausencia')} /></label>}
        <label className="ancho">Observaciones<textarea rows={2} value={d.observaciones} onChange={set('observaciones')} /></label>
        <div className="ancho botones">
          <button type="submit" className="primario" disabled={guardando}>{guardando ? 'Guardando…' : 'Guardar'}</button>
          {editando && <button type="button" onClick={onCancelar}>Cancelar</button>}
        </div>
      </form>
      {msg && <div className={`alerta ${msg.ok ? 'ok' : 'error'}`}>{msg.t}</div>}

      <datalist id="lista-trab">{trab.map((t) => <option key={t.dni || t.nombre} value={t.nombre}>{t.dni} · {t.sede}</option>)}</datalist>
      <datalist id="lista-dni">{trab.filter((t) => t.dni).map((t) => <option key={t.dni} value={t.dni}>{t.nombre}</option>)}</datalist>
      <datalist id="lista-sedes">{sedes.map((s) => <option key={s} value={s} />)}</datalist>
    </section>
  )
}

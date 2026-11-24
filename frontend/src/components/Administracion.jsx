import { useEffect, useState } from 'react'
import { api } from '../api'

const usuarioVacio = { usuario: '', password: '', nombre: '', apellido: '', dni: '', rol: 'USUARIO', sede_id: '', activo: true }
const sedeVacia = { nombre: '', area_erp: '', activo: true }
const fmt = (iso) => (iso ? new Date(iso).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' }) : '—')

export default function Administracion({ yo }) {
  const [usuarios, setUsuarios] = useState([])
  const [sedes, setSedes] = useState([])
  const [u, setU] = useState(null) // usuario en edición (id null = nuevo)
  const [s, setS] = useState(null) // sede en edición
  const [msg, setMsg] = useState(null)

  const cargar = () => {
    api.usuarios().then(setUsuarios).catch((e) => setMsg({ ok: false, t: e.message }))
    api.sedes().then(setSedes).catch(() => {})
  }
  useEffect(cargar, [])

  const accion = async (fn, ok) => {
    setMsg(null)
    try { await fn(); setMsg({ ok: true, t: ok }); setU(null); setS(null); cargar() } catch (e) { setMsg({ ok: false, t: e.message }) }
  }

  const guardarUsuario = (e) => {
    e.preventDefault()
    const body = { ...u, sede_id: u.sede_id ? Number(u.sede_id) : null, dni: u.dni || null }
    if (u.id && !body.password) delete body.password
    accion(() => (u.id ? api.editarUsuario(u.id, body) : api.crearUsuario(body)), 'Usuario guardado.')
  }
  const guardarSede = (e) => {
    e.preventDefault()
    accion(() => (s.id ? api.editarSede(s.id, s) : api.crearSede(s)), 'Sede guardada.')
  }
  const setCampo = (obj, fn) => (k) => (e) => fn({ ...obj, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const cu = setCampo(u, setU)
  const cs = setCampo(s, setS)

  return (
    <section className="panel">
      {msg && <div className={`alerta ${msg.ok ? 'ok' : 'error'}`}>{msg.t}</div>}

      <div className="fila-titulo">
        <h2>Usuarios</h2>
        <button className="primario" onClick={() => setU({ ...usuarioVacio })}>+ Nuevo usuario</button>
      </div>

      {u && (
        <form className="form recuadro" onSubmit={guardarUsuario}>
          <label>Usuario<input required value={u.usuario} onChange={cu('usuario')} pattern="[A-Za-z0-9._\-]{3,50}" title="3 a 50 caracteres: letras, números, punto, guion" /></label>
          <label>{u.id ? 'Nueva contraseña (vacío = no cambiar)' : 'Contraseña temporal'}
            <input type="password" autoComplete="new-password" required={!u.id} minLength={8} value={u.password || ''} onChange={cu('password')} />
          </label>
          <label>Nombre<input required value={u.nombre} onChange={cu('nombre')} /></label>
          <label>Apellido<input required value={u.apellido} onChange={cu('apellido')} /></label>
          <label>DNI<input value={u.dni || ''} onChange={cu('dni')} pattern="\d{8}" maxLength={8} title="8 dígitos" /></label>
          <label>Rol
            <select value={u.rol} onChange={cu('rol')}>
              <option value="USUARIO">Usuario de sede</option>
              <option value="ADMIN">Administrador (todas las sedes)</option>
            </select>
          </label>
          <label>Sede
            <select value={u.sede_id || ''} onChange={cu('sede_id')} required={u.rol === 'USUARIO'}>
              <option value="">{u.rol === 'ADMIN' ? '— Todas —' : 'Elegir…'}</option>
              {sedes.map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
            </select>
          </label>
          <label className="check"><input type="checkbox" checked={u.activo} onChange={cu('activo')} /> Activo</label>
          <p className="sub ancho">{u.id ? 'Si cambias la contraseña, se cierran sus sesiones abiertas.' : 'Al ingresar por primera vez se le pedirá cambiar la contraseña.'}</p>
          <div className="ancho botones">
            <button type="submit" className="primario">Guardar</button>
            <button type="button" onClick={() => setU(null)}>Cancelar</button>
          </div>
        </form>
      )}

      <div className="tabla-wrap">
        <table>
          <thead><tr><th>Usuario</th><th>Nombre</th><th>DNI</th><th>Rol</th><th>Sede</th><th>Estado</th><th>Último acceso</th><th></th></tr></thead>
          <tbody>
            {usuarios.map((x) => (
              <tr key={x.id}>
                <td>{x.usuario}</td>
                <td>{x.apellido}, {x.nombre}</td>
                <td>{x.dni}</td>
                <td>{x.rol === 'ADMIN' ? 'Administrador' : 'Usuario'}</td>
                <td>{x.sede?.nombre || (x.rol === 'ADMIN' ? 'Todas' : '—')}</td>
                <td className={x.activo ? 'verde' : 'rojo'}>{x.activo ? 'Activo' : 'Inactivo'}</td>
                <td>{fmt(x.ultimo_acceso)}</td>
                <td className="acciones">
                  <button title="Editar" onClick={() => setU({ ...x, password: '', sede_id: x.sede_id || '', dni: x.dni || '' })}>✎</button>
                  {x.id !== yo.id && (
                    <button title="Eliminar" onClick={() => confirm(`¿Eliminar al usuario ${x.usuario}?`) && accion(() => api.borrarUsuario(x.id), 'Usuario eliminado.')}>✕</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="fila-titulo">
        <h2>Sedes</h2>
        <button className="primario" onClick={() => setS({ ...sedeVacia })}>+ Nueva sede</button>
      </div>
      <p className="sub">El <b>área en el ERP</b> debe escribirse igual que en IGEA (campo <code>area</code>, por ejemplo <code>SEDE CHORRILLOS</code>). Con ese valor se filtran los registros y se consulta el ERP.</p>

      {s && (
        <form className="form recuadro" onSubmit={guardarSede}>
          <label>Nombre<input required value={s.nombre} onChange={cs('nombre')} placeholder="CHORRILLOS" /></label>
          <label>Área en el ERP<input required value={s.area_erp} onChange={cs('area_erp')} placeholder="SEDE CHORRILLOS" /></label>
          <label className="check"><input type="checkbox" checked={s.activo} onChange={cs('activo')} /> Activa (se consulta en la carga automática)</label>
          <div className="ancho botones">
            <button type="submit" className="primario">Guardar</button>
            <button type="button" onClick={() => setS(null)}>Cancelar</button>
          </div>
        </form>
      )}

      <div className="tabla-wrap">
        <table>
          <thead><tr><th>Sede</th><th>Área en el ERP</th><th>Estado</th><th>Usuarios</th><th></th></tr></thead>
          <tbody>
            {sedes.map((x) => (
              <tr key={x.id}>
                <td>{x.nombre}</td>
                <td><code>{x.area_erp}</code></td>
                <td className={x.activo ? 'verde' : 'rojo'}>{x.activo ? 'Activa' : 'Inactiva'}</td>
                <td>{usuarios.filter((y) => y.sede_id === x.id).length}</td>
                <td className="acciones">
                  <button title="Editar" onClick={() => setS({ ...x })}>✎</button>
                  <button title="Eliminar" onClick={() => confirm(`¿Eliminar la sede ${x.nombre}?`) && accion(() => api.borrarSede(x.id), 'Sede eliminada.')}>✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

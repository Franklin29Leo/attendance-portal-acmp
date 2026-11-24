import { useState } from 'react'
import { api } from '../api'

export default function CambiarPassword({ obligatorio, onListo, onCancelar }) {
  const [d, setD] = useState({ actual: '', nueva: '', repetir: '' })
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const set = (k) => (e) => setD({ ...d, [k]: e.target.value })

  const enviar = async (e) => {
    e.preventDefault()
    if (d.nueva !== d.repetir) return setError('Las contraseñas nuevas no coinciden')
    setEnviando(true)
    setError('')
    try {
      onListo(await api.cambiarPassword(d.actual, d.nueva))
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="login-fondo">
      <form className="login" onSubmit={enviar}>
        <h1>Cambiar contraseña</h1>
        {obligatorio && <div className="alerta aviso">Por seguridad, cambia la contraseña temporal antes de continuar.</div>}
        <label>Contraseña actual<input type="password" required autoComplete="current-password" value={d.actual} onChange={set('actual')} /></label>
        <label>Nueva contraseña<input type="password" required autoComplete="new-password" minLength={8} value={d.nueva} onChange={set('nueva')} /></label>
        <label>Repetir nueva<input type="password" required autoComplete="new-password" value={d.repetir} onChange={set('repetir')} /></label>
        <p className="sub">Mínimo 8 caracteres, con letras y números.</p>
        {error && <div className="alerta error">{error}</div>}
        <div className="botones">
          <button type="submit" className="primario" disabled={enviando}>Guardar</button>
          <button type="button" onClick={onCancelar}>{obligatorio ? 'Salir' : 'Cancelar'}</button>
        </div>
      </form>
    </div>
  )
}

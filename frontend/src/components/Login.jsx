import { useState } from 'react'
import { api } from '../api'

export default function Login({ onIngreso }) {
  const [usuario, setUsuario] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    setError('')
    try {
      onIngreso(await api.login(usuario, password))
    } catch (err) {
      setError(err.message)
      setPassword('')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="login-fondo">
      <form className="login" onSubmit={enviar}>
        <h1>Asistencia por sedes</h1>
        <p className="sub">Ingresa con tu usuario</p>
        <label>Usuario
          <input autoFocus required autoComplete="username" value={usuario} onChange={(e) => setUsuario(e.target.value)} />
        </label>
        <label>Contraseña
          <input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <div className="alerta error">{error}</div>}
        <button type="submit" className="primario" disabled={enviando}>{enviando ? 'Ingresando…' : 'Ingresar'}</button>
      </form>
    </div>
  )
}

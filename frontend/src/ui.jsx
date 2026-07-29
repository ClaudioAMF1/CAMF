import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { IconCheck, IconLua, IconSol, IconVazio } from './icons'

/* ---------------- Tema claro/escuro ---------------- */

const TemaContext = createContext(null)

export function TemaProvider({ children }) {
  const [tema, setTema] = useState(() => {
    const salvo = localStorage.getItem('camf-tema')
    if (salvo) return salvo
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'escuro' : 'claro'
  })

  useEffect(() => {
    document.documentElement.dataset.tema = tema
    localStorage.setItem('camf-tema', tema)
  }, [tema])

  const valor = useMemo(
    () => ({ tema, alternar: () => setTema((t) => (t === 'claro' ? 'escuro' : 'claro')) }),
    [tema]
  )
  return <TemaContext.Provider value={valor}>{children}</TemaContext.Provider>
}

export const useTema = () => useContext(TemaContext)

export function BotaoTema() {
  const { tema, alternar } = useTema()
  return (
    <button
      className="icone fantasma"
      onClick={alternar}
      title={tema === 'claro' ? 'Mudar para tema escuro' : 'Mudar para tema claro'}
      aria-label="Alternar tema"
    >
      {tema === 'claro' ? <IconLua /> : <IconSol />}
    </button>
  )
}

/* ---------------- Toasts ---------------- */

const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const notificar = useCallback((mensagem, tipo = 'sucesso') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, mensagem, tipo }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200)
  }, [])

  return (
    <ToastContext.Provider value={notificar}>
      {children}
      <div className="toasts">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.tipo}`}>
            <span className="marca-cor" />
            {t.tipo === 'sucesso' && <IconCheck />}
            <span>{t.mensagem}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)

/* ---------------- Estados de carregamento e vazio ---------------- */

export function LinhasEsqueleto({ linhas = 5, colunas = 5 }) {
  return Array.from({ length: linhas }, (_, i) => (
    <tr key={i}>
      {Array.from({ length: colunas }, (_, j) => (
        <td key={j}>
          <div className="esqueleto" style={{ width: j === 0 ? '65%' : '45%' }} />
        </td>
      ))}
    </tr>
  ))
}

export function Vazio({ titulo, descricao, acao }) {
  return (
    <div className="vazio">
      <div className="icone-vazio"><IconVazio /></div>
      <strong>{titulo}</strong>
      {descricao && <div style={{ fontSize: 13 }}>{descricao}</div>}
      {acao && <div style={{ marginTop: 14 }}>{acao}</div>}
    </div>
  )
}

/* ---------------- Modal ---------------- */

export function Modal({ titulo, children, onFechar, largura = 380 }) {
  useEffect(() => {
    const fechar = (e) => e.key === 'Escape' && onFechar()
    window.addEventListener('keydown', fechar)
    return () => window.removeEventListener('keydown', fechar)
  }, [onFechar])

  return (
    <>
      <div className="veu" onClick={onFechar} />
      <div className="painel-lateral" style={{ width: largura }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
          <h3>{titulo}</h3>
          <button className="mini fantasma" onClick={onFechar}>Fechar</button>
        </div>
        {children}
      </div>
    </>
  )
}

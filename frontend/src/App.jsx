import { NavLink, Route, Routes } from 'react-router-dom'
import { FiltrosProvider } from './filtros'
import BoletosPage from './pages/BoletosPage'
import DashboardPage from './pages/DashboardPage'
import PagadoresPage from './pages/PagadoresPage'
import UploadPage from './pages/UploadPage'
import UploadsPage from './pages/UploadsPage'

const links = [
  ['/', 'Dashboard'],
  ['/boletos', 'Boletos'],
  ['/pagadores', 'Pagadores'],
  ['/upload', 'Enviar PDFs'],
  ['/uploads', 'Histórico de uploads'],
]

export default function App() {
  return (
    <FiltrosProvider>
      <div className="layout">
        <nav className="sidebar">
          <h1>
            CAMF Construtora
            <small>Contas a Receber · Sicoob 756</small>
          </h1>
          {links.map(([para, rotulo]) => (
            <NavLink key={para} to={para} end={para === '/'} className={({ isActive }) => (isActive ? 'ativo' : '')}>
              {rotulo}
            </NavLink>
          ))}
        </nav>
        <main className="conteudo">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/boletos" element={<BoletosPage />} />
            <Route path="/pagadores" element={<PagadoresPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/uploads" element={<UploadsPage />} />
          </Routes>
        </main>
      </div>
    </FiltrosProvider>
  )
}

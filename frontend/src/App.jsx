import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { FiltrosProvider } from './filtros'
import {
  IconBoletos, IconDashboard, IconHistorico, IconPagadores, IconUpload, IconVencimentos,
} from './icons'
import BoletosPage from './pages/BoletosPage'
import DashboardPage from './pages/DashboardPage'
import PagadoresPage from './pages/PagadoresPage'
import UploadPage from './pages/UploadPage'
import UploadsPage from './pages/UploadsPage'
import VencimentosPage from './pages/VencimentosPage'
import { BotaoTema } from './ui'

const secoes = [
  ['Visão geral', [
    ['/', 'Dashboard', IconDashboard],
    ['/vencimentos', 'Vencimentos', IconVencimentos],
    ['/boletos', 'Boletos', IconBoletos],
    ['/pagadores', 'Pagadores', IconPagadores],
  ]],
  ['Importação', [
    ['/upload', 'Enviar PDFs', IconUpload],
    ['/uploads', 'Histórico', IconHistorico],
  ]],
]

const CAMINHOS = {
  '/': '~', '/vencimentos': '~/vencimentos', '/boletos': '~/boletos',
  '/pagadores': '~/pagadores', '/upload': '~/upload', '/uploads': '~/historico',
}

/** Linha de terminal acima de cada tela, como o prompt do portfólio. */
function Prompt() {
  const { pathname } = useLocation()
  return (
    <div className="prompt-linha">
      <div className="prompt">
        <b>camf</b><i>@</i>receber <i>{CAMINHOS[pathname] ?? '~'}</i> <i>›</i>
        <span className="cursor" aria-hidden="true" />
      </div>
      <BotaoTema />
    </div>
  )
}

export default function App() {
  return (
    <FiltrosProvider>
      <div className="layout">
        <nav className="lateral">
          <div className="marca">
            <div className="marca-selo" aria-hidden="true">ca</div>
            <div>
              <h1>camf<span>.receber</span></h1>
              <small>CAMF Construtora LTDA</small>
            </div>
          </div>

          {secoes.map(([titulo, itens]) => (
            <div key={titulo}>
              <div className="nav-grupo">{titulo}</div>
              {itens.map(([para, rotulo, Icone]) => (
                <NavLink key={para} to={para} end={para === '/'} className={({ isActive }) => (isActive ? 'ativo' : '')}>
                  <Icone />
                  {rotulo}
                </NavLink>
              ))}
            </div>
          ))}

          <div className="lateral-rodape">
            sicoob · banco 756
            <div>cnpj 42.800.118/0001-44</div>
          </div>
        </nav>

        <main className="conteudo">
          <Prompt />
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/vencimentos" element={<VencimentosPage />} />
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

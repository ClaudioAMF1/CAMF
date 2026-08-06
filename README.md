# CAMF — Contas a Receber (boletos Sicoob)

Aplicação full-stack para gestão e análise de boletos bancários Sicoob
(padrão FEBRABAN, banco 756) em PDF, para controle de contas a receber da
**CAMF Construtora LTDA** (CNPJ 42.800.118/0001-44).

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI (Python 3.11+), SQLAlchemy 2.0, Alembic, PostgreSQL 16 |
| Extração | pdfplumber |
| Agregações | pandas |
| Exportação | openpyxl (XLSX), WeasyPrint (PDF), CSV |
| Frontend | React + Vite, Recharts, TanStack Query |
| Infra | Docker Compose (api, db, web) |

## Subindo tudo com um comando

```bash
docker compose up --build
```

- Frontend: http://localhost:8080
- API (Swagger): http://localhost:8000/docs

As migrations Alembic rodam automaticamente na subida do serviço `api`.

## Onde hospedar (e por que não na Vercel)

O **frontend** roda na Vercel sem problema — é um build estático do Vite.
O **backend não roda**, e não é questão de configuração:

| Impedimento | Detalhe |
|---|---|
| **WeasyPrint** | precisa de bibliotecas de sistema (Pango, Cairo, GDK-PixBuf) que não existem no runtime serverless; sem elas não há relatório em PDF |
| **PDFs guardados** | o disco das funções é efêmero e somente-leitura fora de `/tmp`, então os boletos originais sumiriam a cada invocação (adeus "Ver PDF") |
| **Tamanho da função** | pandas + pdfplumber + pypdf + WeasyPrint estouram o limite de 250 MB descompactados |
| **Upload** | o corpo de uma requisição serverless é limitado (~4,5 MB), e carteiras com muitas páginas passam disso |
| **Tempo de execução** | processar dezenas de páginas costuma ultrapassar o limite de execução dos planos menores |

O projeto já está em Docker, então o caminho natural é uma plataforma que
rode contêineres — **Railway**, **Render**, **Fly.io** ou uma VPS:

```bash
docker compose up --build -d      # api + db + web
```

Nessas plataformas é preciso apontar `DATABASE_URL` para um Postgres
gerenciado e montar um volume persistente em `ARMAZENAMENTO_DIR` (padrão
`/dados/pdfs` no compose) para os PDFs originais.

Um arranjo híbrido também funciona: **frontend na Vercel** + **backend em
Railway/Render**, bastando apontar `VITE_API_URL` para a URL da API e
liberar o CORS.

## Desenvolvimento local (sem Docker)

```bash
# Backend
cd backend
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg2://camf:camf@localhost:5432/camf
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (proxy /api -> localhost:8000)
cd frontend
npm install
npm run dev
```

### Testes

```bash
cd backend
python -m pytest tests/ -v
```

Os testes usam SQLite e não precisam do PostgreSQL. Cobrem: parser da linha
digitável, DVs módulo 10 e 11, conversão do fator de vencimento, validação de
CPF/CNPJ, deduplicação, reprocessamento com `forcar=true`, soft delete,
auditoria e merge de pagadores.

## A regra de validação cruzada — a linha digitável é a fonte da verdade

Cada página de PDF passa por extração de texto (pdfplumber + regex). O texto
impresso no boleto pode sair truncado ou ilegível, mas a **linha digitável**
carrega os dados autoritativos de forma verificável. O fluxo:

1. **Normalização** — remove pontuação e espaços; sobram 47 dígitos.
2. **Conversão para código de barras (44 dígitos)** — rearranjo dos campos:
   `banco+moeda (0:4) + DV geral (32) + fator+valor (33:47) + campo livre
   (4:9 ∪ 10:20 ∪ 21:31)`.
3. **Valor** — os últimos 10 dígitos da linha ÷ 100, comparado com o "Valor do
   Documento" do texto. Diferença ⇒ `valor_divergente`.
4. **Fator de vencimento** — posições 5–8 do código de barras, contado a partir
   da base 07/10/1997. O fator estourou em 9999 no dia 21/02/2025 e **reiniciou
   em 1000 no dia 22/02/2025** (regra FEBRABAN pós-2025): fatores < 1000 usam a
   base nova; fatores ≥ 1000 são desambiguados escolhendo a data mais próxima
   da data atual. Comparado com o "Vencimento" do texto ⇒
   `vencimento_divergente`.
5. **DV geral** — posição 4 do código de barras, módulo 11 (pesos 2–9 cíclicos
   da direita para a esquerda; resultado 0/10/11 vira 1) ⇒ `dv_geral_invalido`.
6. **DVs dos campos** — cada um dos 3 campos da linha digitável tem DV módulo
   10 (pesos 2/1 alternados; produto > 9 soma os algarismos) ⇒
   `dv_campo_invalido`.

Qualquer divergência entra no array `divergencias` do boleto e marca
`qualidade='revisao_manual'` — **o boleto é persistido mesmo assim**, com os
valores da linha digitável como autoritativos e os valores do texto anotados na
observação.

### Layouts de página suportados

O texto que o pdfplumber extrai dos boletos Sicoob vem em dois formatos, e o
parser cobre os dois:

- **Inline**: `Vencimento 10/08/2026` (rótulo e valor na mesma linha);
- **Tabular**: uma linha só de rótulos (`Nome do pagador Número do Documento
  ... Vencimento`) seguida de uma linha com os valores. Linhas compostas
  apenas por rótulos conhecidos são reconhecidas e ignoradas; o nome do
  pagador é cortado no primeiro token de dado (data, valor, CPF/CNPJ, número
  composto); para datas, a posição do rótulo na linha de cabeçalho determina
  qual data da linha de valores é usada.

### Modo diagnóstico

`POST /api/uploads/analisar` (multipart) extrai e valida **sem gravar nada**,
retornando por página o texto bruto e os campos reconhecidos. Na tela "Enviar
PDFs", a opção **"Modo diagnóstico (não grava)"** usa esse endpoint — ideal
para conferir o parser com um PDF novo antes de importar.

### Reparo de importações ruins

Se um lote foi importado com extração errada (ex.: parser antigo), basta
**reenviar o mesmo PDF e confirmar "Reprocessar e atualizar os boletos"**
(`?forcar=true`). Os boletos daquele arquivo são re-extraídos **no lugar**:
mesmo `id`, histórico de auditoria preservado e **situação/pagamento
mantidos** — só os campos vindos da extração (pagador, CPF/CNPJ, valores,
datas) são atualizados. Pagadores provisórios que ficarem órfãos podem ser
removidos em Pagadores → "Remover" (o `DELETE` só é aceito para pagador sem
boletos ativos).

> **Semântica do `forcar=true`** — a especificação original dizia que, no
> reprocessamento, "boletos que já existem continuam sendo deduplicados".
> Na prática isso tornava impossível corrigir registros já importados: a
> correção do parser nunca chegava neles. Aqui, `forcar=true` significa
> *re-extrair e atualizar* (contados em `atualizados`), enquanto o envio
> normal (`forcar=false`) mantém a deduplicação como especificado
> (contados em `duplicados`).

### Página que não é boleto

Página sem linha digitável reconhecível **não vira registro** (sem linha não há
chave única) — é contada em `qtd_ignoradas` e o número da página volta na
resposta do upload. Se a página tem marcadores "SICOOB"/"Ficha de Compensação"
mas a linha não foi reconhecida, o caso é logado como possível falha de parsing.

## Identidade do pagador

- A chave de identidade é o **CPF/CNPJ normalizado** (só dígitos, DVs
  validados). Nunca há match automático por similaridade de nome.
- Nome do PDF diferente do cadastro **não sobrescreve** o cadastro: vira
  registro de auditoria (`origem='extracao'`) e aparece na API como
  `nomes_alternativos`. O nome só muda por `PATCH` manual.
- CPF/CNPJ ausente/ inválido ⇒ pagador **provisório** (sem documento,
  identificado pelo nome normalizado) e boleto com divergência
  `cpf_cnpj_ausente`. Ao corrigir o CPF via `PATCH /api/pagadores/{id}`, se já
  existir pagador com aquele documento, o merge é feito automaticamente
  (boletos migrados, provisório soft-deletado).
- `GET /api/pagadores/sugestoes-merge` lista nomes normalizados iguais com
  documentos diferentes — apenas sugestão; o merge é decisão do usuário via
  `POST /api/pagadores/{id}/merge`.

## Deduplicação e reprocessamento

- **Boleto**: `linha_digitavel` é UNIQUE. Reenvio conta como "duplicado
  ignorado" na resposta — nunca erro HTTP.
- **Arquivo** (hash SHA-256 já processado):
  - `?forcar=false` (default) ⇒ `409` com o upload original e o resumo dele;
  - `?forcar=true` ⇒ novo registro de `upload` com `reprocessado_de_id`
    apontando para o anterior; boletos existentes são **re-extraídos e
    atualizados** no lugar (mesmo `id`, pagamento e auditoria preservados),
    e boletos novos são inseridos. Ver "Reparo de importações ruins".

  > Nota de implementação: por causa do reprocessamento, `hash_sha256` tem
  > índice **não-único** — a unicidade lógica do "mesmo arquivo" é garantida na
  > aplicação, e reprocessamentos legítimos geram novas linhas encadeadas por
  > `reprocessado_de_id`.

## Regras de estado

- `vencido` **não é persistido**: é derivado (`situacao='aberto' AND
  vencimento < hoje`) e exposto como campo calculado na API e como filtro.
- `situacao` (aberto/pago/cancelado) e `qualidade` (ok/revisao_manual) são
  **ortogonais** — um boleto pode estar pago e em revisão ao mesmo tempo.
- **Soft delete em tudo**: `DELETE` preenche `deletado_em`; um listener do
  SQLAlchemy injeta `deletado_em IS NULL` em todo SELECT por padrão
  (`incluir_deletados=true` para ver tudo); endpoints `/restaurar` desfazem.
  Deletar um upload cascateia nos boletos dele; restaurar desfaz apenas a
  mesma cascata.
- **Auditoria append-only** (`auditoria`): criação, cada campo alterado em
  PATCH (valor anterior/novo), soft delete, restauração, pagamento e
  divergência de nome. Autor vem do header `X-Autor` (default `sistema`).

## Endpoints principais

```
POST   /api/uploads?forcar=false       multipart, múltiplos PDFs
GET    /api/uploads · GET/DELETE /api/uploads/{id} · POST /api/uploads/{id}/restaurar

GET    /api/boletos                    filtros: pagador_id, situacao, qualidade,
                                       vencido, vencimento_de/ate, valor_min/max,
                                       incluir_deletados; page/size/sort
GET    /api/boletos/{id} · /auditoria
PATCH  /api/boletos/{id}               revalida contra a linha digitável
POST   /api/boletos/{id}/pagar · DELETE · /restaurar

GET    /api/pagadores · /{id} · PATCH · POST /{id}/merge · /sugestoes-merge

GET    /api/dashboard                  mesmos filtros de /boletos
GET    /api/dashboard/alertas?dias=30

GET    /api/relatorios/pdf | xlsx | csv   respeitando os filtros
```

## Tela de Vencimentos

Lista os boletos em aberto agrupados **por dia de vencimento**, com presets de
período (**Este mês**, Próximo mês, 7/15/30/60 dias) e a opção de incluir os
atrasados. Cada linha mostra o pagador com CPF/CNPJ e permite **ver o PDF** ou
**baixá-lo de novo**; dá para baixar todos os boletos de um dia, do período
inteiro ou só os selecionados num **PDF único** (`GET /api/boletos/pdf-lote`),
e dar baixa em lote.

```
GET /api/dashboard/alertas?de=2026-08-01&ate=2026-08-31   intervalo (ex.: o mês)
GET /api/dashboard/alertas?dias=30&incluir_vencidos=true  próximos N dias
GET /api/boletos/pdf-lote?ids=1,2,3                       um PDF com os boletos
```

## Visualizar o boleto original

O PDF enviado é guardado (por hash SHA-256, então reenviar o mesmo arquivo não
duplica nada) e cada boleto grava a **página** de onde veio. Assim, o botão
**"Ver PDF"** abre exatamente aquele boleto — não o arquivo de 45 páginas:

```
GET /api/boletos/{id}/pdf                → só a página daquele boleto
GET /api/boletos/{id}/pdf?completo=true  → o arquivo inteiro
GET /api/uploads/{id}/pdf                → o arquivo original do upload
```

O recorte da página é feito com pypdf, e o PDF é servido `inline` para abrir no
visualizador do navegador (com opções de baixar e abrir em nova aba).

Os arquivos ficam em `ARMAZENAMENTO_DIR` (padrão `./armazenamento`; no Docker,
o volume `pdfs` montado em `/dados/pdfs`, que persiste entre recriações do
container). Boletos importados **antes** deste recurso não têm o arquivo
guardado: a API responde 404 explicando que basta reenviar o PDF com
"Reprocessar e atualizar" para passar a visualizá-lo.

## Relatórios e exportações

Todas as exportações respeitam os filtros ativos na tela.

**XLSX** (openpyxl), três abas — moeda BRL, cabeçalho congelado, larguras ajustadas:

| Aba | Conteúdo |
|---|---|
| **Resumo** | pagador, **CPF/CNPJ**, qtd, valor unitário, subtotal + total geral |
| **Pagadores** | uma linha por pessoa: nome, **CPF/CNPJ**, endereço, bairro, município, UF, CEP, qtd. de boletos, total, em aberto, pago e vencido |
| **Detalhado** | todos os campos do boleto + **CPF/CNPJ**, município/UF, situação, qualidade e divergências |

**CSV** em duas variantes: `?aba=boletos` (padrão, uma linha por boleto, com o
documento do pagador) e `?aba=pagadores` (cadastro e totais por pessoa).

**PDF** (WeasyPrint), em **A4 paisagem** — com 9 colunas de dados, o retrato
espremia nomes em três linhas e separava o "R$" do número:

- faixa de indicadores (total, aberto, recebido, vencido, médio, revisão);
- **resumo por pagador**: documento, município, quantidade, barra de
  composição (recebido / vencido / a vencer) e totais por situação;
- **por pagador × valor unitário**, com subtotais;
- **boletos detalhados agrupados por pessoa**, com subtotal de cada uma —
  em vez de uma lista corrida de centenas de linhas;
- cabeçalho de tabela repetido a cada página (`display: table-header-group`)
  e `break-inside: avoid` nas linhas, para que nenhuma seja cortada ao meio
  (era o que gerava células vazias no meio da tabela);
- valores e datas com `white-space: nowrap`, numerais tabulares, rodapé
  paginado com CNPJ.

## Baixa de pagamento: manual, em lote — não automática

Não há como o sistema saber sozinho que um boleto foi pago: essa informação
está no banco, não no PDF. Um boleto emitido é apenas uma instrução de
cobrança. As formas de saber da liquidação são:

| Caminho | O que exige | Situação |
|---|---|---|
| **Manual** (aqui) | nada | pronto — botão "Pagar" por boleto |
| **Baixa em lote** (aqui) | nada | pronto — selecionar vários e baixar de uma vez |
| **Arquivo de retorno CNAB** (240/400) | baixar o retorno no Sicoob e importar | não implementado |
| **API de Cobrança Sicoob / Open Finance** | convênio, credenciais e certificado digital | não implementado |

O caminho realista para automatizar sem burocracia é o **arquivo de retorno
CNAB**: o Sicoob gera um arquivo com as liquidações do dia (código de
ocorrência de liquidação, nosso número, valor e data do pagamento), que seria
importado para dar baixa automaticamente. Isso não foi implementado porque o
layout precisa ser validado contra um arquivo de retorno real — a lição da
extração dos PDFs: especificar por suposição gera parser errado.

## Frontend

Formatação brasileira em tudo (`R$ 1.234,56`, `dd/mm/aaaa`):

- **Enviar PDFs**: drag-and-drop múltiplo com resultado por arquivo (novos /
  duplicados / páginas ignoradas / revisão); no `409`, botão "Reprocessar
  mesmo assim".
- **Dashboard**: cards, barras por pagador, linha por mês de vencimento, pizza
  por situação, alertas de vencimento e tabela agrupada pagador × valor.
- **Boletos**: dois modos —
  - **Por pessoa** (padrão): uma linha por pagador, com quantidade, barra de
    composição (aberto/pago/vencido), próximo vencimento e total. Clicar no
    nome expande os boletos daquela pessoa, então o nome nunca se repete.
  - **Lista**: tabela completa paginada e ordenável.
  Em ambos: **"Ver PDF"** abre o boleto original, seleção múltipla com **baixa
  em lote**, edição inline, linhas de revisão manual em amarelo com as
  divergências, histórico de auditoria em drawer, soft delete/restauração.
- **Pagadores**: lista com totais e nomes alternativos, edição, painel de
  sugestões de merge.
- **Filtros globais** (pagador, período, situação, qualidade) aplicados a
  dashboard, tabelas e exportações.

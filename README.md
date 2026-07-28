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

## Frontend

Formatação brasileira em tudo (`R$ 1.234,56`, `dd/mm/aaaa`):

- **Enviar PDFs**: drag-and-drop múltiplo com resultado por arquivo (novos /
  duplicados / páginas ignoradas / revisão); no `409`, botão "Reprocessar
  mesmo assim".
- **Dashboard**: cards, barras por pagador, linha por mês de vencimento, pizza
  por situação, alertas de vencimento e tabela agrupada pagador × valor.
- **Boletos**: tabela paginada/ordenável, linhas de revisão manual destacadas
  em amarelo com as divergências, edição inline, marcar como pago, histórico
  de auditoria em drawer, soft delete/restauração.
- **Pagadores**: lista com totais e nomes alternativos, edição, painel de
  sugestões de merge.
- **Filtros globais** (pagador, período, situação, qualidade) aplicados a
  dashboard, tabelas e exportações.

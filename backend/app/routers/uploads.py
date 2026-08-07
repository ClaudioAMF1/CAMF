from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, schemas
from ..database import get_db
from ..deps import get_autor
from ..models import Boleto, Upload
from ..services import armazenamento, extracao, linha_digitavel
from ..services.processamento import (
    ArquivoJaProcessado,
    ResultadoArquivo,
    processar_arquivo,
    validar_cruzado,
)

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def _resumo(upload: Upload) -> dict:
    return schemas.UploadOut.model_validate(upload).model_dump(mode="json")


@router.post("", response_model=schemas.RespostaUpload)
async def enviar_pdfs(
    arquivos: list[UploadFile] = File(...),
    forcar: bool = Query(default=False),
    db: Session = Depends(get_db),
    autor: str = Depends(get_autor),
):
    """Processa múltiplos PDFs. Erro em um arquivo não derruba o lote."""
    resultados: list[ResultadoArquivo] = []
    duplicados_409: list[dict] = []

    for arquivo in arquivos:
        nome = arquivo.filename or "sem_nome.pdf"
        conteudo = await arquivo.read()
        try:
            if not conteudo.startswith(b"%PDF"):
                raise ValueError("arquivo não é um PDF válido")
            resultado = processar_arquivo(db, nome, conteudo, forcar=forcar, autor=autor)
            db.commit()
            resultados.append(resultado)
        except ArquivoJaProcessado as exc:
            db.rollback()
            duplicados_409.append({"nome": nome, "upload": _resumo(exc.upload)})
            resultados.append(
                ResultadoArquivo(
                    nome=nome,
                    upload_id=exc.upload.id,
                    erro="arquivo_ja_processado",
                )
            )
        except Exception as exc:  # erro por arquivo, não por lote
            db.rollback()
            resultados.append(ResultadoArquivo(nome=nome, erro=str(exc)))

    # Todos os arquivos já processados e sem forcar -> 409 com o resumo original
    if duplicados_409 and len(duplicados_409) == len(arquivos):
        raise HTTPException(
            status_code=409,
            detail={
                "mensagem": "Arquivo(s) já processado(s). Use ?forcar=true para reprocessar.",
                "uploads_originais": duplicados_409,
            },
        )

    return schemas.RespostaUpload(
        arquivos=[schemas.ResultadoArquivoOut(**vars(r)) for r in resultados]
    )


@router.post("/analisar")
async def analisar_sem_gravar(arquivos: list[UploadFile] = File(...)):
    """Modo diagnóstico: extrai e valida sem gravar nada no banco.

    Retorna, por página, o texto bruto extraído e os campos reconhecidos —
    útil para calibrar o parser com PDFs reais.
    """
    saida = []
    for arquivo in arquivos:
        nome = arquivo.filename or "sem_nome.pdf"
        conteudo = await arquivo.read()
        try:
            if not conteudo.startswith(b"%PDF"):
                raise ValueError("arquivo não é um PDF válido")
            paginas = []
            for num, texto in enumerate(extracao.extrair_textos_paginas(conteudo), start=1):
                dados = extracao.extrair_dados_pagina(texto)
                item = {
                    "pagina": num,
                    "tem_linha_digitavel": dados is not None,
                    "parece_boleto": extracao.parece_boleto(texto),
                    "texto": texto[:4000],
                    "campos": None,
                    "divergencias": None,
                }
                if dados is not None:
                    analise = linha_digitavel.analisar(dados.linha_digitavel_bruta)
                    item["campos"] = asdict(dados)
                    if analise is not None:
                        divergencias, _ = validar_cruzado(analise, dados)
                        item["campos"]["valor_linha"] = analise.valor
                        item["campos"]["vencimento_linha"] = analise.vencimento
                        item["divergencias"] = divergencias
                paginas.append(item)
            saida.append({"nome": nome, "paginas": paginas, "erro": None})
        except Exception as exc:
            saida.append({"nome": nome, "paginas": [], "erro": str(exc)})
    return jsonable_encoder({"arquivos": saida})


@router.get("", response_model=list[schemas.UploadOut])
def listar(incluir_deletados: bool = False, db: Session = Depends(get_db)):
    stmt = select(Upload).order_by(Upload.id.desc())
    if incluir_deletados:
        stmt = stmt.execution_options(incluir_deletados=True)
    return db.execute(stmt).scalars().all()


def _obter(db: Session, upload_id: int, incluir_deletados: bool = False) -> Upload:
    stmt = select(Upload).where(Upload.id == upload_id)
    if incluir_deletados:
        stmt = stmt.execution_options(incluir_deletados=True)
    upload = db.execute(stmt).scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload não encontrado")
    return upload


@router.get("/{upload_id}", response_model=schemas.UploadOut)
def detalhar(upload_id: int, db: Session = Depends(get_db)):
    return _obter(db, upload_id)


@router.get("/{upload_id}/pdf")
def pdf_do_upload(upload_id: int, db: Session = Depends(get_db)):
    """Abre o arquivo PDF original completo, como enviado."""
    upload = _obter(db, upload_id, incluir_deletados=True)
    try:
        conteudo = armazenamento.ler(upload.hash_sha256, db)
    except armazenamento.ArquivoIndisponivel:
        raise HTTPException(
            status_code=404,
            detail="PDF original não está guardado para este upload. Reenvie o arquivo.",
        )
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{upload.nome_arquivo}"'},
    )


@router.delete("/{upload_id}", response_model=schemas.UploadOut)
def deletar(upload_id: int, db: Session = Depends(get_db), autor: str = Depends(get_autor)):
    """Soft delete do upload em cascata nos boletos dele."""
    upload = _obter(db, upload_id)
    quando = datetime.now(timezone.utc)
    upload.soft_delete(quando)
    audit.registrar(db, "upload", upload.id, "deletar", autor=autor)

    boletos = db.execute(select(Boleto).where(Boleto.upload_id == upload.id)).scalars().all()
    for boleto in boletos:
        boleto.soft_delete(quando)
        audit.registrar(db, "boleto", boleto.id, "deletar", campo="upload_cascata", autor=autor)
    db.commit()
    return upload


@router.post("/{upload_id}/restaurar", response_model=schemas.UploadOut)
def restaurar(upload_id: int, db: Session = Depends(get_db), autor: str = Depends(get_autor)):
    """Restaura o upload e os boletos deletados na mesma cascata."""
    upload = _obter(db, upload_id, incluir_deletados=True)
    if upload.deletado_em is None:
        raise HTTPException(status_code=400, detail="Upload não está deletado")
    quando = upload.deletado_em
    upload.restaurar()
    audit.registrar(db, "upload", upload.id, "restaurar", autor=autor)

    stmt = (
        select(Boleto)
        .where(Boleto.upload_id == upload.id, Boleto.deletado_em == quando)
        .execution_options(incluir_deletados=True)
    )
    for boleto in db.execute(stmt).scalars().all():
        boleto.restaurar()
        audit.registrar(db, "boleto", boleto.id, "restaurar", campo="upload_cascata", autor=autor)
    db.commit()
    return upload

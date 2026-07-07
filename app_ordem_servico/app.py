"""
Ordem de Serviço Digital — aplicativo Flask independente.
Lê o banco SQLite compartilhado com o Sistema_Oficina (oficina_nautica.db).
"""

from __future__ import annotations

import io
import json
import os
import re
import secrets
import socket
import sqlite3
import sys
import unicodedata
import zipfile
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Generator
from urllib.parse import urlparse

_CODE_DIR = Path(__file__).resolve().parent
if getattr(sys, "frozen", False):
    INSTALL_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", _CODE_DIR))
else:
    INSTALL_DIR = _CODE_DIR
    RESOURCE_DIR = _CODE_DIR
APP_DIR = INSTALL_DIR

if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from config_app_os import preparar_ambiente_instalacao, resolver_caminho_banco

preparar_ambiente_instalacao(INSTALL_DIR)

from dotenv import load_dotenv
from flask import Flask, has_request_context, jsonify, redirect, render_template, request, send_file, session, url_for

load_dotenv(INSTALL_DIR / ".env")

from atividade_log import (
    ATIVIDADE_ORDEM_CATEGORIAS,
    definir_rastreio_controle_terceiro,
    excluir_atividade,
    init_atividade_log,
    limpar_atividades,
    listar_atividades,
    rastreio_controle_terceiro_ativo,
    registrar_atividade,
)

from catalogo_pecas import (
    atualizar_peca_catalogo,
    buscar_pecas_catalogo,
    inserir_peca_catalogo,
    obter_peca_catalogo,
    parse_valor_moeda_br,
)
from catalogo_servicos import (
    atualizar_servico_catalogo,
    buscar_servicos_catalogo,
    inserir_servico_catalogo,
    obter_servico_catalogo,
)
from estoque import (
    adicionar_item_pedido_marcador,
    atualizar_item_pedido_marcador,
    atualizar_marcador_ordem,
    criar_marcador_ordem,
    definir_estoque_minimo,
    definir_fornecedor_peca,
    EstoqueInsuficienteError,
    importar_sugestoes_pedido_marcador,
    init_estoque_schema,
    integrar_catalogo_ao_estoque,
    liberar_itens_requisicao,
    listar_estoque,
    listar_itens_pedido_marcador,
    listar_marcadores_ordens,
    listar_movimentos,
    listar_pecas_baixo_fornecedor,
    listar_pendencias_atualizar_estoque,
    movimentar_estoque,
    obter_peca_estoque,
    obter_saldo_peca,
    parse_quantidade,
    remover_item_pedido_marcador,
    remover_marcador_ordem,
    remover_pendencia_atualizar_estoque,
)
from checklist_revisao import (
    carregar_itens_checklist_os,
    init_checklist_tabelas,
    obter_checklist_leitura,
    obter_ou_rascunho_checklist,
    preparar_campos_diagnostico_os_para_impressao,
    salvar_checklist,
)
from catalogo_precos_kit import atualizar_precos_itens_do_catalogo
from pre_orcamentos import (
    atualizar_pre_orcamento,
    buscar_kits_motor,
    caminho_banco_pre_orcamentos,
    criar_pre_orcamento,
    excluir_kit_motor,
    excluir_pre_orcamento,
    garantir_banco_pre_orcamentos,
    importar_kits_motor_lote,
    init_pre_orcamentos_tabelas,
    listar_todos_kits_motor,
    marcar_pre_orcamento_convertido,
    montar_payload_os_de_pre_orcamento,
    obter_kit_motor,
    obter_pre_orcamento,
    listar_pre_orcamentos,
    salvar_kit_motor,
    itens_para_requisicao_os,
    STATUS_CONVERTIDO_OS,
)
from pdf_pre_orcamento import gerar_pdf_pre_orcamento
from agendamentos import (
    cancelar_agendamento,
    criar_agendamento,
    init_agendamentos_tabelas,
    listar_agendamentos_dia,
    marcar_emergencia,
    marcar_virou_os,
    metadados_mes,
    obter_agendamento,
    reagendar_agendamento,
    remover_emergencia,
    resumo_calendario_mes,
    STATUS_EMERGENCIA,
    STATUS_VIRou_OS,
    validar_agendamento_para_gerar_os,
)
from ambiente_teste import (
    caminho_banco_teste,
    garantir_banco_teste,
    iniciar_schema_banco_app,
    limpar_dados_app,
    resumo_banco_app,
)
from sandbox_treinamento import (
    ativar_sandbox_todos,
    ativar_sandbox_usuarios,
    caminho_banco_sandbox_treinamento,
    desativar_sandbox_todos,
    desativar_sandbox_usuarios,
    garantir_banco_sandbox,
    init_sandbox_treinamento_tabelas,
    ler_liberado_todos,
    limpar_banco_sandbox,
    listar_usuarios_sandbox_admin,
    registrar_sessao_ativa,
    registrar_sessao_inativa,
    resumo_banco_sandbox,
    salvar_liberado_todos,
    sessao_sandbox_usuario,
    usuario_pode_usar_sandbox,
)
from fotos_os_config import (
    carregar_fotos_os_config,
    configurar_banco_principal as configurar_banco_fotos_os_config,
    limites_efetivos_fotos_os,
    salvar_fotos_os_config,
)
from os_fotos_mecanico import (
    contar_os_fotos_pendentes,
    init_os_fotos_tabelas,
    listar_os_fotos_pendentes,
    marcar_fotos_os_enviadas,
    nome_pasta_cliente,
    obter_fotos_pendentes_os,
    salvar_fotos_os,
)
from pdf_os_fotos import fotos_para_zip, gerar_pdf_fotos_os
from req_precondicoes_os import (
    exigir_pode_abrir_requisicao_mecanico,
    registrar_pulo_pre_requisicao,
    status_pre_requisicao,
)
from nav_pos_acao_config import (
    carregar_nav_pos_acao,
    configurar_banco_principal as configurar_banco_nav_pos_acao,
    salvar_nav_pos_acao,
)
from notificacoes_aparelho_config import (
    carregar_notificacoes_aparelho,
    configurar_banco_principal as configurar_banco_notificacoes_aparelho,
    mapa_eventos_ativos,
    salvar_notificacoes_aparelho,
)
from os_lista_personalizacao import (
    aplicar_info_lista_os_payload,
    carregar_marcadores_lista,
    carregar_pausas_tipos,
    configurar_banco_principal,
    extrair_info_lista_os,
    mapa_filtro_pausa,
    mapa_marcadores,
    pausas_status_ativos,
    salvar_personalizacao_lista_os,
    slug_de_status_pausa,
    status_pausa_de_slug,
)
from fluxo_requisicoes import (
    enviar_requisicao_mecanico,
    enviar_resposta_responsavel,
    finalizar_requisicao_interna,
    publicar_requisicao_interna_oficina,
    finalizar_servico_mecanico,
    indicador_sidebar_mecanico,
    init_fluxo_tabelas,
    listar_notificacoes,
    listar_requisicoes,
    devolver_os_ao_mecanico,
    definir_pausa_os,
    marcar_cliente_avisado_os,
    os_status_em_pausa,
    retomar_os_de_pausa,
    marcar_os_entregue_se_assinada,
    marcar_requisicao_aprovada_se_assinada,
    marcar_requisicao_vista,
    obter_requisicao,
    resolver_status_exibicao_lista_os,
    resumo_requisicoes_por_os,
    salvar_requisicao,
    tem_assinatura_entrega_os,
)
from historico_servicos_mecanico import (
    atualizar_servico_realizado_mecanico,
    listar_historico_servicos_mecanico,
)
from perfis_app import (
    atualizar_perfil_app,
    buscar_perfil_app_por_id,
    buscar_perfil_app_por_modelo,
    criar_perfil_app,
    excluir_perfil_app,
    init_perfis_app,
    listar_perfis_app,
    permissoes_do_perfil_app,
)
from permissoes_arvore_os import (
    MAPA_MODULO_PREFIXOS,
    arvore_permissoes_json,
    chaves_explicitas_permissoes,
    modulo_tem_alguma_permissao,
    modulos_visiveis_de_permissoes,
    modulo_pre_orcamentos_apenas_explicito,
    tem_permissao_pre_orcamentos_explicita,
    normalizar_permissoes_granulares,
    permissoes_efetivas_usuario,
    permissoes_granulares_vazias,
    permissoes_padrao_usuario_os,
    permissoes_template_por_modelo,
    serializar_permissoes_granulares,
    usuario_tem_permissao_granular,
)
from presenca_telespectador import (
    atualizar_presenca_usuario,
    init_presenca_tabelas,
    listar_presenca_monitor,
    remover_presenca_usuario,
    listar_usuarios_rastreaveis,
    usuario_deve_ser_rastreado,
)
from sync_oficina_servicos import sincronizar_status_app_para_oficina
from pdf_checklist_revisao import gerar_pdf_checklist_revisao
from pdf_os import gerar_pdf_ordem_servico, dados_os_de_registro, normalizar_orientacao

APP_DIR = INSTALL_DIR

DATABASE_PRINCIPAL_PATH = resolver_caminho_banco(INSTALL_DIR)
DATABASE_PATH = DATABASE_PRINCIPAL_PATH
DATABASE_TESTE_PATH = caminho_banco_teste(APP_DIR)
DATABASE_SANDBOX_TREINAMENTO_PATH = caminho_banco_sandbox_treinamento(APP_DIR)
DATABASE_PRE_ORCAMENTOS_PATH = caminho_banco_pre_orcamentos(APP_DIR)
configurar_banco_principal(DATABASE_PRINCIPAL_PATH)
configurar_banco_nav_pos_acao(DATABASE_PRINCIPAL_PATH)
configurar_banco_notificacoes_aparelho(DATABASE_PRINCIPAL_PATH)
configurar_banco_fotos_os_config(DATABASE_PRINCIPAL_PATH)
_CHAVE_AMBIENTE_TESTE = "ambiente_teste_ativo"
APP_VERSION = "2.14.0"

_PERFIS_VALIDOS = frozenset({"admin", "operador", "atendente", "mecanico"})

_CAMPOS_RESUMO_ABRIR_MECANICO = frozenset({
    "numero_os",
    "cliente_nome",
    "entregue_por",
    "embarcacao_nome",
    "embarcacao",
    "fabricante",
    "modelo",
    "horas_uso",
    "alegacoes_cliente",
})

_CAMPOS_COPIA_RETORNO_OS = frozenset({
    "tipo_pessoa",
    "motor_id",
    "embarcacao_nome",
    "marina",
    "tipo_embarcacao",
    "fabricante",
    "modelo",
    "ano_modelo",
    "cor",
    "num_chassi",
    "num_motor",
    "data_venda",
    "concessionaria_venda",
    "ultima_concessionaria",
    "revisoes_completas",
    "horas_uso",
})

_STATUS_BLOQUEIA_TROCA_MECANICO = frozenset({
    "pronto_mecanico",
    "cliente_avisado",
    "entregue",
})

_CAMPOS_MECANICO_EDITAVEIS = frozenset({
    "horas_uso",
    "constatacao_diagnostico",
    "diag_analista_nome",
    "diag_data",
    "diag_garantia",
    "assinatura_tecnico",
    "analise_reparos",
    "conclusao_analista_nome",
    "conclusao_data",
    "requisicoes_pecas",
})

_CHAVES_PAYLOAD_PARCIAL_MECANICO = _CAMPOS_MECANICO_EDITAVEIS | {"numero_os"}

_METADADOS_OS_PAYLOAD = frozenset({
    "pre_orcamento_id",
    "pre_orcamento_numero",
    "pre_orcamento_itens_requisicao",
    "orcamento_numero",
    "os_retorno_de",
    "status_anterior_cancelamento",
    "cancelado_em",
    "cancelado_por",
    "motivo_cancelamento",
})

_ASSINATURA_TIPOS_VALIDOS = frozenset({
    "responsavel",
    "tecnico",
    "cliente_recepcao",
    "cliente_entrega",
    "cliente_aprovacao",
})

_ASSINATURA_TITULOS: dict[str, str] = {
    "responsavel": "Responsável — Alegações do cliente",
    "tecnico": "Analista técnico — Diagnóstico",
    "cliente_recepcao": "Cliente — Recepção do veículo",
    "cliente_entrega": "Cliente — Entrega do veículo",
    "cliente_aprovacao": "Cliente — Aprovação do orçamento",
}

_ASSINATURA_DURACAO_HORAS = {"qr": 4, "link": 168}

_ASSINATURA_TIPO_PARA_CAMPO: dict[str, str] = {
    "responsavel": "assinatura_responsavel",
    "tecnico": "assinatura_tecnico",
    "cliente_recepcao": "assinatura_cliente",
    "cliente_entrega": "assinatura_cliente_entrega",
    "cliente_aprovacao": "assinatura_cliente_aprovacao",
}

_ASSINATURA_TIPO_PARA_NOME: dict[str, str] = {
    "responsavel": "responsavel_assinante_nome",
    "tecnico": "diag_analista_nome",
    "cliente_recepcao": "recepcao_assinante_nome",
    "cliente_entrega": "entrega_assinante_nome",
    "cliente_aprovacao": "aprovacao_assinante_nome",
}

_ASSINATURA_TIPO_PARA_DATA: dict[str, str] = {
    "responsavel": "alegacoes_data",
    "tecnico": "diag_data",
    "cliente_recepcao": "recepcao_data",
    "cliente_entrega": "entrega_data",
    "cliente_aprovacao": "data_aprovacao",
}

app = Flask(
    __name__,
    template_folder=str(RESOURCE_DIR / "templates"),
    static_folder=str(RESOURCE_DIR / "static"),
)
app.config["JSON_AS_ASCII"] = False

_SECRET_FILE = INSTALL_DIR / ".flask_secret"
_secret = (os.getenv("FLASK_SECRET_KEY") or "").strip()
if not _secret and _SECRET_FILE.is_file():
    _secret = _SECRET_FILE.read_text(encoding="utf-8").strip()
if not _secret:
    _secret = secrets.token_hex(32)
    try:
        _SECRET_FILE.write_text(_secret, encoding="utf-8")
    except OSError:
        pass
app.config["SECRET_KEY"] = _secret
app.config["SESSION_COOKIE_NAME"] = "os_digital_sess"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["SESSION_REFRESH_EACH_REQUEST"] = True


@app.after_request
def _sem_cache_html(response):
    """Evita o navegador/tablet servir HTML/JS antigo após atualização."""
    path = request.path or ""
    if response.content_type and "text/html" in response.content_type:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    elif path.startswith("/api/login") or path in ("/api/logout", "/api/auth/status"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


def _aplicar_config_cookie_sessao_segura() -> None:
    """Cookie só via HTTPS em acesso público (ngrok / URL configurada)."""
    if request.is_secure or _requisicao_via_internet_publica():
        app.config["SESSION_COOKIE_SECURE"] = True


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------

def _configurar_conexao(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 60000")
    conn.execute("PRAGMA journal_mode = WAL")


def _ler_ambiente_teste_global(conn: sqlite3.Connection) -> bool:
    """Flag global no banco principal — vale para todos os usuários do app."""
    _init_app_os_config(conn)
    row = conn.execute(
        "SELECT valor FROM app_os_config WHERE chave = ?",
        (_CHAVE_AMBIENTE_TESTE,),
    ).fetchone()
    if row is None:
        return False
    return _config_bool(row["valor"], padrao=False)


def _salvar_ambiente_teste_global(conn: sqlite3.Connection, ativo: bool) -> None:
    _init_app_os_config(conn)
    conn.execute(
        "INSERT OR REPLACE INTO app_os_config (chave, valor) VALUES (?, ?)",
        (_CHAVE_AMBIENTE_TESTE, "1" if ativo else "0"),
    )


def _ambiente_teste_ativo() -> bool:
    """Todos os usuários usam o banco de teste quando o admin ativa globalmente."""
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return False
    try:
        with conexao_principal() as conn:
            return _ler_ambiente_teste_global(conn)
    except sqlite3.Error:
        return False


def _sandbox_treinamento_liberado_todos() -> bool:
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return False
    try:
        with conexao_principal() as conn:
            return ler_liberado_todos(conn)
    except sqlite3.Error:
        return False


def _usuario_pode_sandbox_treinamento(usuario: dict[str, Any] | None) -> bool:
    if _ambiente_teste_ativo():
        return False
    return usuario_pode_usar_sandbox(
        usuario,
        liberado_todos=_sandbox_treinamento_liberado_todos(),
    )


def _sandbox_treinamento_forcado_admin_sessao() -> bool:
    if not has_request_context():
        return False
    usuario = _usuario_logado()
    if not usuario:
        return False
    try:
        with conexao_principal() as conn:
            info = sessao_sandbox_usuario(conn, int(usuario["id"]))
        return bool(info.get("ativo")) and bool(info.get("forcado_admin"))
    except sqlite3.Error:
        return False


def _sandbox_treinamento_ativo_sessao() -> bool:
    if not has_request_context():
        return False
    if _ambiente_teste_ativo():
        _definir_sandbox_treinamento_sessao(False)
        return False
    usuario = _usuario_logado()
    if not usuario:
        _definir_sandbox_treinamento_sessao(False)
        return False
    try:
        with conexao_principal() as conn:
            init_sandbox_treinamento_tabelas(conn)
            info = sessao_sandbox_usuario(conn, int(usuario["id"]))
            if info.get("ativo"):
                forcado = bool(info.get("forcado_admin"))
                if forcado or _usuario_pode_sandbox_treinamento(usuario):
                    _definir_sandbox_treinamento_sessao(True)
                    return True
            _definir_sandbox_treinamento_sessao(False)
            return False
    except sqlite3.Error:
        pass
    if not _usuario_pode_sandbox_treinamento(usuario):
        _definir_sandbox_treinamento_sessao(False)
        return False
    if not session.get(_SESSAO_SANDBOX_TREINAMENTO):
        return False
    return True


def _definir_sandbox_treinamento_sessao(ativo: bool) -> None:
    if not has_request_context():
        return
    if ativo:
        session[_SESSAO_SANDBOX_TREINAMENTO] = 1
    else:
        session.pop(_SESSAO_SANDBOX_TREINAMENTO, None)


def _caminho_banco_app() -> Path:
    if _ambiente_teste_ativo():
        return DATABASE_TESTE_PATH
    if _sandbox_treinamento_ativo_sessao():
        return DATABASE_SANDBOX_TREINAMENTO_PATH
    return DATABASE_PRINCIPAL_PATH


@contextmanager
def conexao_principal() -> Generator[sqlite3.Connection, None, None]:
    """Banco compartilhado: clientes, motores, usuários, empresa, config global."""
    conn = sqlite3.connect(DATABASE_PRINCIPAL_PATH, timeout=30)
    _configurar_conexao(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def conexao_pre_orcamentos() -> Generator[sqlite3.Connection, None, None]:
    """Banco dedicado: kits de motor e pré-orçamentos."""
    if not DATABASE_PRE_ORCAMENTOS_PATH.is_file():
        garantir_banco_pre_orcamentos(DATABASE_PRE_ORCAMENTOS_PATH)
    conn = sqlite3.connect(DATABASE_PRE_ORCAMENTOS_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 60000")
    try:
        init_pre_orcamentos_tabelas(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def conexao_banco() -> Generator[sqlite3.Connection, None, None]:
    """Dados do app O.S. — produção ou ambiente de teste global."""
    caminho = _caminho_banco_app()
    if _ambiente_teste_ativo() and not caminho.is_file():
        garantir_banco_teste(caminho)
    elif _sandbox_treinamento_ativo_sessao() and not caminho.is_file():
        garantir_banco_sandbox(caminho)
    conn = sqlite3.connect(caminho, timeout=30)
    _configurar_conexao(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _obter_logo_empresa(conn: sqlite3.Connection) -> str | None:
    _init_app_os_config(conn)
    try:
        row = conn.execute(
            "SELECT valor FROM app_os_config WHERE chave = ?",
            (_CHAVE_LOGO_EMPRESA,),
        ).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    valor = str(row["valor"] or "").strip()
    return valor if valor.startswith("data:image/") else None


def _salvar_logo_empresa(conn: sqlite3.Connection, logo: str | None) -> None:
    _init_app_os_config(conn)
    if not logo:
        conn.execute("DELETE FROM app_os_config WHERE chave = ?", (_CHAVE_LOGO_EMPRESA,))
        return
    bruto = str(logo).strip()
    if not bruto.startswith("data:image/"):
        raise ValueError("Formato de logo inválido.")
    if len(bruto) > 400_000:
        raise ValueError("Logo muito grande (máx. ~300 KB).")
    conn.execute(
        "INSERT OR REPLACE INTO app_os_config (chave, valor) VALUES (?, ?)",
        (_CHAVE_LOGO_EMPRESA, bruto),
    )


def _cfg_fotos_os(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    if conn is not None:
        return carregar_fotos_os_config(conn)
    with conexao_principal() as c:
        return carregar_fotos_os_config(c)


def _limites_envio_fotos_os(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    return limites_efetivos_fotos_os(_cfg_fotos_os(conn))


def _empresa_e_config_app() -> tuple[dict[str, str], dict[str, bool]]:
    """Empresa e configurações globais sempre vêm do banco principal."""
    with conexao_principal() as conn:
        return _obter_empresa_config(conn), _obter_app_os_config(conn)


def _normalizar_busca(texto: str) -> str:
    texto = unicodedata.normalize("NFD", (texto or "").strip().casefold())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _somente_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def _garantir_colunas_clientes(conn: sqlite3.Connection) -> None:
    """Garante colunas de endereço na tabela clientes (banco compartilhado)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(clientes)").fetchall()}
    for nome in ("celular", "rg", "numero", "bairro", "cidade", "estado", "cep"):
        if nome not in cols:
            conn.execute(f"ALTER TABLE clientes ADD COLUMN {nome} TEXT")


def sql_embarcacao_motor(alias: str = "m") -> str:
    """Embarcação do motor (coluna dedicada, com fallback legado em observacoes)."""
    return (
        f"COALESCE(NULLIF(TRIM({alias}.embarcacao), ''), "
        f"NULLIF(TRIM({alias}.observacoes), ''))"
    )


def _garantir_colunas_motores(conn: sqlite3.Connection) -> None:
    """Alinha tabela motores com o Sistema Oficina (embarcação separada de observações)."""
    info = conn.execute("PRAGMA table_info(motores)").fetchall()
    if not info:
        return
    cols = {c[1] for c in info}
    if "embarcacao" not in cols:
        conn.execute("ALTER TABLE motores ADD COLUMN embarcacao TEXT")
        conn.execute(
            """
            UPDATE motores
            SET embarcacao = observacoes,
                observacoes = NULL
            WHERE observacoes IS NOT NULL AND TRIM(observacoes) != ''
            """
        )


def _embarcacao_motor_de_row(row: sqlite3.Row) -> str:
    if "embarcacao_exibir" in row.keys():
        return (row["embarcacao_exibir"] or "").strip()
    emb = (row["embarcacao"] or "").strip() if "embarcacao" in row.keys() else ""
    if emb:
        return emb
    return (row["observacoes"] or "").strip()


def _migrar_colunas_assinatura(conn: sqlite3.Connection) -> None:
    """Adiciona colunas de assinatura digital em bancos já existentes."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(ordens_servico)").fetchall()}
    if "assinatura_tecnico" not in cols:
        conn.execute("ALTER TABLE ordens_servico ADD COLUMN assinatura_tecnico TEXT")
    if "assinatura_cliente" not in cols:
        conn.execute("ALTER TABLE ordens_servico ADD COLUMN assinatura_cliente TEXT")


def _migrar_colunas_atribuicao_os(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(ordens_servico)").fetchall()}
    if "mecanico_id" not in cols:
        conn.execute("ALTER TABLE ordens_servico ADD COLUMN mecanico_id INTEGER")
    if "mecanico_nome" not in cols:
        conn.execute("ALTER TABLE ordens_servico ADD COLUMN mecanico_nome TEXT")


def init_ordens_servico() -> None:
    """Cria tabelas de O.S. / fluxo no banco de app ativo (produção ou teste)."""
    with conexao_banco() as conn:
        iniciar_schema_banco_app(conn)
    with conexao_principal() as conn:
        _init_app_os_config(conn)
        if DATABASE_PRINCIPAL_PATH.is_file():
            integrar_catalogo_ao_estoque(conn)


def init_assinaturas_remotas() -> None:
    """Garante schema de assinaturas no banco de app ativo."""
    with conexao_banco() as conn:
        iniciar_schema_banco_app(conn)


_APP_OS_CONFIG_DEFAULTS: dict[str, bool] = {
    "exibir_tipo_os": False,
    "exigir_login": True,
    "mecanico_modulo_os_padrao": True,
    "interna_publicar_oficina": False,
    "telespectador_admin_ativo": True,
    "telespectador_operadores_ativo": True,
    "telespectador_lista_ampliada_admin": True,
}
_APP_CONFIG_JSON_PATH = INSTALL_DIR / "app_config.json"
_TELESPECTADOR_CFG_KEYS = (
    "telespectador_admin_ativo",
    "telespectador_operadores_ativo",
    "telespectador_lista_ampliada_admin",
)
_CHAVE_PDF_ORIENTACAO = "pdf_orientacao"
_CHAVE_LOGO_EMPRESA = "logo_empresa"
_CHAVE_SYNC_EXIGIR_LOGIN = "sincronizar_exigir_login_oficina"


def _ler_app_config_json() -> dict[str, bool]:
    saida: dict[str, bool] = {}
    if not _APP_CONFIG_JSON_PATH.is_file():
        return saida
    try:
        raw = json.loads(_APP_CONFIG_JSON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return saida
    if not isinstance(raw, dict):
        return saida
    for chave in _TELESPECTADOR_CFG_KEYS:
        if chave in raw:
            saida[chave] = _config_bool(raw[chave], padrao=_APP_OS_CONFIG_DEFAULTS[chave])
    return saida


def _salvar_telespectador_no_arquivo(cfg: dict[str, bool]) -> None:
    dados: dict[str, Any] = {}
    if _APP_CONFIG_JSON_PATH.is_file():
        try:
            bruto = json.loads(_APP_CONFIG_JSON_PATH.read_text(encoding="utf-8"))
            if isinstance(bruto, dict):
                dados.update(bruto)
        except (OSError, json.JSONDecodeError):
            pass
    for chave in _TELESPECTADOR_CFG_KEYS:
        if chave in cfg:
            dados[chave] = bool(cfg[chave])
    try:
        _APP_CONFIG_JSON_PATH.write_text(
            json.dumps(dados, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _obter_cfg_telespectador() -> dict[str, bool]:
    cfg = {chave: _APP_OS_CONFIG_DEFAULTS[chave] for chave in _TELESPECTADOR_CFG_KEYS}
    if DATABASE_PRINCIPAL_PATH.is_file():
        try:
            with conexao_principal() as conn:
                _init_app_os_config(conn)
                for chave in _TELESPECTADOR_CFG_KEYS:
                    row = conn.execute(
                        "SELECT valor FROM app_os_config WHERE chave = ?",
                        (chave,),
                    ).fetchone()
                    if row is not None:
                        cfg[chave] = _config_bool(row["valor"], padrao=cfg[chave])
        except sqlite3.Error:
            pass
    arquivo = _ler_app_config_json()
    for chave in _TELESPECTADOR_CFG_KEYS:
        if chave in arquivo:
            cfg[chave] = arquivo[chave]
    return cfg


def _usuario_pode_telespectar_app(usuario: dict[str, Any] | None) -> bool:
    if not usuario:
        return False
    cfg = _obter_cfg_telespectador()
    perfil = str(usuario.get("perfil") or "").strip().lower()
    if perfil == "admin":
        return bool(cfg.get("telespectador_admin_ativo"))
    if not cfg.get("telespectador_operadores_ativo"):
        return False
    return bool(usuario.get("permissao_telespectador"))


def _filtrar_presenca_monitor_admin(
    conn: sqlite3.Connection,
    espectador: dict[str, Any],
    presencas: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if str(espectador.get("perfil") or "").strip().lower() != "admin":
        return presencas
    if _ao_vivo_lista_completa_admin():
        return presencas
    rows = conn.execute(
        """
        SELECT id FROM usuarios
        WHERE ativo = 1 AND permissao_telespectador = 1
        """
    ).fetchall()
    ocultar = {int(r["id"]) for r in rows}
    return [
        p for p in presencas
        if int(p.get("usuario_id") or 0) not in ocultar
    ]


def _init_app_os_config(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_os_config (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO app_os_config (chave, valor) VALUES (?, ?)",
        ("exibir_tipo_os", "1" if _APP_OS_CONFIG_DEFAULTS["exibir_tipo_os"] else "0"),
    )
    padrao_ori = _orientacao_pdf_padrao()
    conn.execute(
        "INSERT OR IGNORE INTO app_os_config (chave, valor) VALUES (?, ?)",
        (_CHAVE_PDF_ORIENTACAO, padrao_ori),
    )
    arquivo = _ler_app_config_json()
    for chave in _TELESPECTADOR_CFG_KEYS:
        padrao = arquivo.get(chave, _APP_OS_CONFIG_DEFAULTS[chave])
        conn.execute(
            "INSERT OR IGNORE INTO app_os_config (chave, valor) VALUES (?, ?)",
            (chave, "1" if padrao else "0"),
        )


def _obter_app_os_config(conn: sqlite3.Connection) -> dict[str, bool]:
    _init_app_os_config(conn)
    _sincronizar_exigir_login_inicial(conn)
    cfg = dict(_APP_OS_CONFIG_DEFAULTS)
    for row in conn.execute("SELECT chave, valor FROM app_os_config").fetchall():
        if row["chave"] in cfg:
            cfg[row["chave"]] = _config_bool(row["valor"], padrao=cfg[row["chave"]])
    return cfg


def _config_bool(valor: Any, *, padrao: bool = False) -> bool:
    if valor is None:
        return padrao
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in ("1", "true", "sim", "yes", "on")


def _config_bool_para_int(valor: Any, *, padrao: bool = False) -> int:
    return 1 if _config_bool(valor, padrao=padrao) else 0


def _salvar_app_os_config(conn: sqlite3.Connection, dados: dict[str, Any]) -> dict[str, bool]:
    _init_app_os_config(conn)
    for chave in ("exibir_tipo_os", "exigir_login", "mecanico_modulo_os_padrao",
                  "interna_publicar_oficina", *_TELESPECTADOR_CFG_KEYS):
        if chave not in dados:
            continue
        val = dados[chave]
        ativo = val if isinstance(val, bool) else str(val).strip().lower() in ("1", "true", "sim", "yes", "on")
        conn.execute(
            "INSERT OR REPLACE INTO app_os_config (chave, valor) VALUES (?, ?)",
            (chave, "1" if ativo else "0"),
        )
    cfg = _obter_app_os_config(conn)
    if any(chave in dados for chave in _TELESPECTADOR_CFG_KEYS):
        _salvar_telespectador_no_arquivo(
            {chave: cfg[chave] for chave in _TELESPECTADOR_CFG_KEYS}
        )
    return cfg


def _exigir_login_sincronizado_oficina(conn: sqlite3.Connection) -> bool:
    _init_app_os_config(conn)
    row = conn.execute(
        "SELECT valor FROM app_os_config WHERE chave = ?",
        (_CHAVE_SYNC_EXIGIR_LOGIN,),
    ).fetchone()
    if row is None:
        return False
    return _config_bool(row["valor"], padrao=False)


def _obter_exigir_login_oficina(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute(
            "SELECT exigir_login FROM empresa_config WHERE id = 1"
        ).fetchone()
        if row is not None:
            return _config_bool(row["exigir_login"], padrao=True)
    except sqlite3.Error:
        pass
    return True


def _exigir_login_para_config(conn: sqlite3.Connection) -> tuple[bool, bool]:
    """Retorna (valor para exibir, sincronizado com a oficina)."""
    if _exigir_login_sincronizado_oficina(conn):
        return _obter_exigir_login_oficina(conn), True
    cfg = _obter_app_os_config(conn)
    return bool(cfg.get("exigir_login", True)), False


def _sincronizar_exigir_login_inicial(conn: sqlite3.Connection) -> None:
    """Na 1ª execução, define exigir_login com o padrão do app (independente da oficina)."""
    _init_app_os_config(conn)
    if conn.execute(
        "SELECT 1 FROM app_os_config WHERE chave = 'exigir_login'"
    ).fetchone():
        return
    valor = "1" if _APP_OS_CONFIG_DEFAULTS["exigir_login"] else "0"
    conn.execute(
        "INSERT INTO app_os_config (chave, valor) VALUES (?, ?)",
        ("exigir_login", valor),
    )


def _obter_empresa_config(conn: sqlite3.Connection) -> dict[str, str]:
    """Lê dados da empresa (tabela empresa_config do sistema principal)."""
    try:
        row = conn.execute(
            "SELECT razao_social, nome_fantasia, endereco, telefone, email "
            "FROM empresa_config WHERE id = 1"
        ).fetchone()
        if row:
            return {
                "razao_social": row["razao_social"] or "",
                "nome_fantasia": row["nome_fantasia"] or "",
                "endereco": row["endereco"] or "",
                "telefone": row["telefone"] or "",
                "email": row["email"] or "",
            }
    except sqlite3.Error:
        pass
    return {"nome_fantasia": "Oficina Náutica"}


def _usuario_pode_configurar_app(usuario: dict[str, Any] | None) -> bool:
    """Configurações globais do app (tipo O.S., login, orientação PDF). Somente admin."""
    return _usuario_e_admin(usuario)


def _orientacao_pdf_padrao() -> str:
    """Padrão global: .env PDF_ORIENTACAO ou horizontal."""
    return "vertical" if normalizar_orientacao(None) == "P" else "horizontal"


def _normalizar_orientacao_ui(valor: Any) -> str:
    raw = str(valor or "").strip().lower()
    if raw in ("vertical", "portrait", "p", "retrato"):
        return "vertical"
    return "horizontal"


def _obter_orientacao_pdf_config(conn: sqlite3.Connection) -> str:
    _init_app_os_config(conn)
    row = conn.execute(
        "SELECT valor FROM app_os_config WHERE chave = ?",
        (_CHAVE_PDF_ORIENTACAO,),
    ).fetchone()
    if row is not None:
        return _normalizar_orientacao_ui(row["valor"])
    arquivo = _ler_pdf_orientacao_app_config_json()
    if arquivo is not None:
        return arquivo
    return _orientacao_pdf_padrao()


def _ler_pdf_orientacao_app_config_json() -> str | None:
    if not _APP_CONFIG_JSON_PATH.is_file():
        return None
    try:
        raw = json.loads(_APP_CONFIG_JSON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or _CHAVE_PDF_ORIENTACAO not in raw:
        return None
    return _normalizar_orientacao_ui(raw[_CHAVE_PDF_ORIENTACAO])


def _salvar_pdf_orientacao_no_arquivo(valor: str) -> None:
    dados: dict[str, Any] = {}
    if _APP_CONFIG_JSON_PATH.is_file():
        try:
            bruto = json.loads(_APP_CONFIG_JSON_PATH.read_text(encoding="utf-8"))
            if isinstance(bruto, dict):
                dados.update(bruto)
        except (OSError, json.JSONDecodeError):
            pass
    dados[_CHAVE_PDF_ORIENTACAO] = _normalizar_orientacao_ui(valor)
    try:
        _APP_CONFIG_JSON_PATH.write_text(
            json.dumps(dados, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _salvar_orientacao_pdf_config(conn: sqlite3.Connection, valor: Any) -> str:
    _init_app_os_config(conn)
    ori = _normalizar_orientacao_ui(valor)
    conn.execute(
        "INSERT OR REPLACE INTO app_os_config (chave, valor) VALUES (?, ?)",
        (_CHAVE_PDF_ORIENTACAO, ori),
    )
    _salvar_pdf_orientacao_no_arquivo(ori)
    return ori


def _orientacao_pdf(
    payload: dict[str, Any] | None = None,
    *,
    usuario: dict[str, Any] | None = None,
) -> str:
    """Orientação do PDF: parâmetro na URL ou preferência global (app_os_config)."""
    _ = payload
    _ = usuario
    q = None
    try:
        q = request.args.get("orientacao") or request.args.get("pdf_orientacao")
    except RuntimeError:
        pass
    if q:
        return normalizar_orientacao(q)
    try:
        with conexao_principal() as conn:
            salva = _obter_orientacao_pdf_config(conn)
    except sqlite3.Error:
        salva = _orientacao_pdf_padrao()
    return normalizar_orientacao(salva)


def _sync_oficina_status_os(
    numero_os: int,
    status_web: str,
    *,
    dados_json: str | None = None,
) -> None:
    """Propaga status da O.S. digital para servicos.situacao no Sistema Oficina."""
    try:
        with conexao_principal() as conn:
            sincronizar_status_app_para_oficina(
                conn,
                int(numero_os),
                status_web,
                dados_json=dados_json,
            )
    except sqlite3.Error:
        pass


def _extrair_assinatura(payload: dict[str, Any], chave: str) -> str | None:
    valor = payload.get(chave)
    if not valor or not isinstance(valor, str):
        return None
    valor = valor.strip()
    if not valor.startswith("data:image"):
        return None
    return valor


def _porta_servidor() -> int:
    try:
        return int(os.getenv("FLASK_PORT", os.getenv("PORT", "5000")))
    except ValueError:
        return 5000


def _obter_url_tunel_local() -> str | None:
    """Detecta URL pública do ngrok rodando neste PC (porta 4040)."""
    try:
        import urllib.error
        import urllib.request

        with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=1) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
        for tunel in dados.get("tunnels", []):
            if tunel.get("proto") == "https":
                url = (tunel.get("public_url") or "").strip().rstrip("/")
                if url:
                    return url
        for tunel in dados.get("tunnels", []):
            url = (tunel.get("public_url") or "").strip().rstrip("/")
            if url:
                return url
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return None
    return None


def _obter_url_publica_base() -> str:
    """URL acessível por celular/tablet (rede local, túnel ngrok ou OS_PUBLIC_URL no .env)."""
    env = (os.getenv("OS_PUBLIC_URL") or "").strip().rstrip("/")
    if env:
        return env
    tunel = _obter_url_tunel_local()
    if tunel:
        return tunel
    host_url = (request.host_url or "").rstrip("/")
    if host_url and "localhost" not in host_url and "127.0.0.1" not in host_url:
        return host_url
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return f"http://{ip}:{_porta_servidor()}"
    except OSError:
        return host_url or f"http://127.0.0.1:{_porta_servidor()}"


def _host_da_requisicao() -> str:
    host = (request.host or "").split(":")[0].strip().lower()
    if not host:
        forwarded = (request.headers.get("X-Forwarded-Host") or "").split(",")[0].strip()
        host = forwarded.split(":")[0].strip().lower()
    return host


def _hosts_publicos_configurados() -> set[str]:
    hosts: set[str] = set()
    for valor in (
        (os.getenv("OS_PUBLIC_URL") or "").strip(),
        (os.getenv("NGROK_DOMAIN") or "").strip(),
    ):
        if not valor:
            continue
        if "://" not in valor:
            valor = f"https://{valor}"
        hostname = (urlparse(valor).hostname or "").strip().lower()
        if hostname:
            hosts.add(hostname)
    return hosts


def _requisicao_via_internet_publica() -> bool:
    host = _host_da_requisicao()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return False
    if host.endswith(".ngrok-free.dev") or host.endswith(".ngrok.io") or ".ngrok" in host:
        return True
    return host in _hosts_publicos_configurados()


def _exigir_login_efetivo() -> bool:
    """Na internet (ngrok/URL pública), login é sempre obrigatório."""
    if _requisicao_via_internet_publica():
        return True
    return _exigir_login_ativo()


def _aplicar_assinatura_remota_na_os(
    conn: sqlite3.Connection,
    numero_os: int,
    tipo: str,
    imagem: str,
    assinante_nome: str | None = None,
) -> None:
    """Grava assinatura remota na O.S. salva (dados_json + colunas legadas)."""
    campo = _ASSINATURA_TIPO_PARA_CAMPO.get(tipo)
    if not campo:
        return
    row = conn.execute(
        """
        SELECT dados_json, assinatura_tecnico, assinatura_cliente
        FROM ordens_servico WHERE numero_os = ?
        """,
        (numero_os,),
    ).fetchone()
    if row is None:
        return

    try:
        dados = json.loads(row["dados_json"] or "{}")
    except json.JSONDecodeError:
        dados = {}
    if not isinstance(dados, dict):
        dados = {}

    dados[campo] = imagem
    nome_limpo = (assinante_nome or "").strip()
    if nome_limpo:
        campo_nome = _ASSINATURA_TIPO_PARA_NOME.get(tipo)
        if campo_nome:
            dados[campo_nome] = nome_limpo
    campo_data = _ASSINATURA_TIPO_PARA_DATA.get(tipo)
    if campo_data:
        dados[campo_data] = datetime.now().strftime("%Y-%m-%d")
    assin_tec = row["assinatura_tecnico"]
    assin_cli = row["assinatura_cliente"]
    if tipo == "tecnico":
        assin_tec = imagem
    elif tipo == "cliente_recepcao":
        assin_cli = imagem

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """
        UPDATE ordens_servico
        SET dados_json = ?, assinatura_tecnico = ?, assinatura_cliente = ?, atualizado_em = ?
        WHERE numero_os = ?
        """,
        (
            json.dumps(dados, ensure_ascii=False),
            assin_tec,
            assin_cli,
            agora,
            numero_os,
        ),
    )
    if tipo == "cliente_entrega":
        marcar_os_entregue_se_assinada(conn, numero_os, dados)
    elif tipo == "cliente_aprovacao":
        marcar_requisicao_aprovada_se_assinada(conn, numero_os, dados)
    if tipo == "cliente_entrega":
        _sync_oficina_status_os(
            numero_os,
            "entregue",
            dados_json=json.dumps(dados, ensure_ascii=False),
        )


def _limpar_assinaturas_expiradas(conn: sqlite3.Connection) -> None:
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """
        UPDATE assinaturas_remotas
        SET status = 'expirado'
        WHERE status = 'pendente' AND expira_em < ?
        """,
        (agora,),
    )


def _assinatura_row_para_json(row: sqlite3.Row, *, incluir_pin: bool = False) -> dict[str, Any]:
    pin = (row["pin"] or "").strip() if "pin" in row.keys() else ""
    dados: dict[str, Any] = {
        "token": row["token"],
        "tipo": row["tipo"],
        "canvas_id": row["canvas_id"] or "",
        "numero_os": row["numero_os"],
        "cliente_nome": row["cliente_nome"] or "",
        "titulo": row["titulo"] or "",
        "imagem": row["imagem"] or "",
        "status": row["status"] or "pendente",
        "criado_em": row["criado_em"] or "",
        "expira_em": row["expira_em"] or "",
        "assinado_em": row["assinado_em"] or "",
        "exige_pin": bool(pin),
        "assinante_nome": (row["assinante_nome"] or "").strip() if "assinante_nome" in row.keys() else "",
    }
    if incluir_pin and pin:
        dados["pin"] = pin
    return dados


def _proximo_numero_os(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(numero_os), 0) + 1 FROM ordens_servico"
    ).fetchone()
    return int(row[0])


def _campo_cliente(row: sqlite3.Row, chave: str) -> str:
    try:
        return row[chave] or ""
    except (KeyError, IndexError):
        return ""


def _cliente_para_json(row: sqlite3.Row) -> dict[str, Any]:
    """Mapeia colunas de `clientes` para o formulário da O.S."""
    return {
        "id": row["id"],
        "nome": row["nome"] or "",
        "cpf_cnpj": _campo_cliente(row, "cpf_cnpj"),
        "endereco": _campo_cliente(row, "endereco"),
        "numero": _campo_cliente(row, "numero"),
        "bairro": _campo_cliente(row, "bairro"),
        "cidade": _campo_cliente(row, "cidade"),
        "estado": _campo_cliente(row, "estado"),
        "cep": _campo_cliente(row, "cep"),
        "telefone": _campo_cliente(row, "telefone"),
        "celular": _campo_cliente(row, "celular"),
        "email": _campo_cliente(row, "email"),
        "rg": _campo_cliente(row, "rg"),
    }


_COLUNAS_CLIENTE = """
    id, nome, telefone, celular, email, cpf_cnpj, rg,
    endereco, numero, bairro, cidade, estado, cep, observacoes
"""


def _buscar_clientes_por_termo(
    conn: sqlite3.Connection,
    termo: str,
    *,
    limite: int = 20,
) -> list[sqlite3.Row]:
    termo = (termo or "").strip()
    if not termo:
        return []

    termo_norm = _normalizar_busca(termo)
    like_norm = f"%{termo_norm}%"
    like_raw = f"%{termo}%"
    like_inicio = f"{termo_norm}%"
    digitos = _somente_digitos(termo)
    like_digitos = f"%{digitos}%" if digitos else like_raw
    limite = max(1, min(int(limite), 30))

    sql = f"""
        SELECT {_COLUNAS_CLIENTE}
        FROM clientes
        WHERE LOWER(nome) LIKE ?
           OR LOWER(IFNULL(cpf_cnpj, '')) LIKE ?
           OR REPLACE(REPLACE(REPLACE(REPLACE(IFNULL(cpf_cnpj, ''), '.', ''), '-', ''), '/', ''), ' ', '') LIKE ?
           OR CAST(id AS TEXT) = ?
           OR CAST(id AS TEXT) LIKE ?
        ORDER BY
            CASE
                WHEN CAST(id AS TEXT) = ? THEN 0
                WHEN LOWER(nome) = ? THEN 1
                WHEN LOWER(nome) LIKE ? THEN 2
                WHEN LOWER(nome) LIKE ? THEN 3
                ELSE 4
            END,
            nome
        LIMIT ?
    """
    params = (
        like_norm,
        like_raw,
        like_digitos,
        termo,
        f"{termo}%",
        termo,
        termo_norm,
        like_inicio,
        like_norm,
        limite,
    )
    return conn.execute(sql, params).fetchall()


def _buscar_cliente_para_pre_orcamento(
    conn: sqlite3.Connection,
    pre: dict[str, Any],
) -> sqlite3.Row | None:
    """Resolve cliente do pré-orçamento por ID ou, em fallback, por nome exato."""
    cid = pre.get("cliente_id")
    if cid not in (None, "", 0):
        try:
            row = conn.execute(
                f"SELECT {_COLUNAS_CLIENTE} FROM clientes WHERE id = ?",
                (int(cid),),
            ).fetchone()
            if row is not None:
                return row
        except (TypeError, ValueError):
            pass
    nome = (pre.get("cliente_nome") or "").strip()
    if not nome:
        return None
    candidatos = _buscar_clientes_por_termo(conn, nome, limite=10)
    nome_lower = nome.lower()
    for row in candidatos:
        if (row["nome"] or "").strip().lower() == nome_lower:
            return row
    return None


def _preservar_metadados_os_payload(
    payload: dict[str, Any],
    dados_existentes: dict[str, Any] | None,
) -> dict[str, Any]:
    """Campos internos do JSON da O.S. não vêm do formulário — não podem ser perdidos no save."""
    if not dados_existentes:
        return payload
    saida = dict(payload)
    for chave in _METADADOS_OS_PAYLOAD:
        novo = saida.get(chave)
        antigo = dados_existentes.get(chave)
        if chave == "pre_orcamento_itens_requisicao":
            if not novo and antigo:
                saida[chave] = antigo
            continue
        if novo in (None, "", [], {}):
            if antigo not in (None, "", [], {}):
                saida[chave] = antigo
    return saida


def _itens_pendentes_pre_orcamento_os(
    payload_os: dict[str, Any],
    *,
    numero_os: int | None = None,
) -> list[dict[str, Any]]:
    """Itens do pré-orçamento ainda não transferidos para a requisição do mecânico."""
    pendentes = payload_os.get("pre_orcamento_itens_requisicao")
    if isinstance(pendentes, list) and pendentes:
        return pendentes
    pre_id = payload_os.get("pre_orcamento_id")
    if pre_id in (None, "", 0) and numero_os:
        try:
            with conexao_pre_orcamentos() as conn_pre:
                row = conn_pre.execute(
                    "SELECT id FROM pre_orcamentos WHERE numero_os_gerado = ?",
                    (int(numero_os),),
                ).fetchone()
                if row is not None:
                    pre_id = int(row["id"])
        except (TypeError, ValueError, sqlite3.Error):
            pre_id = None
    if pre_id in (None, "", 0):
        return []
    try:
        with conexao_pre_orcamentos() as conn_pre:
            pre = obter_pre_orcamento(conn_pre, int(pre_id))
        if pre:
            return itens_para_requisicao_os(pre.get("itens") or [])
    except (TypeError, ValueError, sqlite3.Error):
        pass
    return []


def _tentar_criar_requisicao_pre_orcamento(
    conn: sqlite3.Connection,
    *,
    numero_os: int,
    mecanico_id: int | None,
    mecanico_nome: str | None,
    payload_os: dict[str, Any],
) -> dict[str, Any]:
    """Cria rascunho de requisição com peças/M.O. do pré-orçamento, se houver mecânico."""
    itens_pend = _itens_pendentes_pre_orcamento_os(payload_os, numero_os=int(numero_os))
    payload_os.pop("pre_orcamento_itens_requisicao", None)
    if not itens_pend:
        return payload_os
    if not mecanico_id:
        payload_os["pre_orcamento_itens_requisicao"] = itens_pend
        return payload_os
    row_exist = conn.execute(
        """
        SELECT id, status, itens_json FROM requisicoes_material
        WHERE numero_os = ? AND mecanico_id = ?
          AND COALESCE(tipo_requisicao, 'os') = 'os'
        ORDER BY id DESC LIMIT 1
        """,
        (int(numero_os), int(mecanico_id)),
    ).fetchone()
    obs_parts: list[str] = []
    pre_num = str(payload_os.get("pre_orcamento_numero") or "").strip()
    if pre_num:
        obs_parts.append(f"Pré-orçamento {pre_num}")
    obs_pre = str(payload_os.get("requisicoes_pecas") or "").split("\n\nObs.:")
    if len(obs_pre) > 1 and obs_pre[-1].strip():
        obs_parts.append(obs_pre[-1].strip())
    observacao = " — ".join(obs_parts)
    if row_exist is not None:
        req_id = int(row_exist["id"])
        status_req = str(row_exist["status"] or "")
        itens_atuais = row_exist["itens_json"] or "[]"
        rascunho_vazio = itens_atuais.strip() in ("", "[]")
        if status_req in ("rascunho", "alterada_mecanico") or rascunho_vazio:
            init_fluxo_tabelas(conn)
            salvar_requisicao(
                conn,
                numero_os=int(numero_os),
                mecanico_id=int(mecanico_id),
                mecanico_nome=str(mecanico_nome or ""),
                itens=itens_pend,
                observacao=observacao,
                req_id=req_id,
                como_responsavel=False,
            )
            return payload_os
        payload_os["pre_orcamento_itens_requisicao"] = itens_pend
        return payload_os
    init_fluxo_tabelas(conn)
    salvar_requisicao(
        conn,
        numero_os=int(numero_os),
        mecanico_id=int(mecanico_id),
        mecanico_nome=str(mecanico_nome or ""),
        itens=itens_pend,
        observacao=observacao,
        req_id=None,
        como_responsavel=False,
    )
    return payload_os


def _motor_para_json(row: sqlite3.Row) -> dict[str, Any]:
    marca_modelo = (row["marca_modelo"] or "").strip()
    fabricante = ""
    modelo = marca_modelo
    if " " in marca_modelo:
        partes = marca_modelo.split(" ", 1)
        fabricante = partes[0]
        modelo = partes[1]

    horas = row["horas"]
    horas_txt = ""
    if horas is not None:
        try:
            horas_txt = str(float(horas)).replace(".", ",")
        except (TypeError, ValueError):
            horas_txt = str(horas)

    embarcacao_nome = _embarcacao_motor_de_row(row)
    observacoes = (row["observacoes"] or "").strip() if "observacoes" in row.keys() else ""
    return {
        "id": row["id"],
        "cliente_id": row["cliente_id"],
        "chassi": row["chassi"] or "",
        "horas": horas,
        "horas_uso": horas_txt,
        "marca_modelo": marca_modelo,
        "fabricante": fabricante,
        "modelo": modelo,
        "embarcacao": embarcacao_nome,
        "embarcacao_nome": embarcacao_nome,
        "observacoes": observacoes,
        "num_chassi": row["chassi"] or "",
        "rotulo": _rotulo_motor(row),
    }


def _rotulo_motor(row: sqlite3.Row) -> str:
    mm = (row["marca_modelo"] or "").strip() or "Sem marca/modelo"
    chassi = (row["chassi"] or "").strip()
    horas = row["horas"]
    partes = [f"#{row['id']}", mm]
    if chassi:
        partes.append(f"Chassi: {chassi}")
    if horas is not None:
        try:
            partes.append(f"{float(horas):g} h")
        except (TypeError, ValueError):
            pass
    return " | ".join(partes)


def _parse_horas(valor: Any) -> float:
    if valor in (None, ""):
        return 0.0
    texto = str(valor).strip().lower().replace("h", "").replace(" ", "")
    texto = texto.replace(",", ".")
    try:
        return max(0.0, float(texto))
    except ValueError:
        return 0.0


def _marca_modelo_de_form(payload: dict[str, Any]) -> str | None:
    fabricante = (payload.get("fabricante") or "").strip()
    modelo = (payload.get("modelo") or "").strip()
    if fabricante and modelo:
        return f"{fabricante} {modelo}"
    return modelo or fabricante or None


def _extrair_dados_cliente(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "nome": (payload.get("cliente_nome") or "").strip(),
        "telefone": (payload.get("cliente_telefone") or "").strip() or None,
        "celular": (payload.get("cliente_celular") or "").strip() or None,
        "email": (payload.get("cliente_email") or "").strip() or None,
        "cpf_cnpj": (payload.get("cliente_cpf_cnpj") or "").strip() or None,
        "rg": (payload.get("cliente_rg") or "").strip() or None,
        "endereco": (payload.get("cliente_endereco") or "").strip() or None,
        "numero": (payload.get("cliente_numero") or "").strip() or None,
        "bairro": (payload.get("cliente_bairro") or "").strip() or None,
        "cidade": (payload.get("cliente_cidade") or "").strip() or None,
        "estado": (payload.get("cliente_estado") or "").strip() or None,
        "cep": (payload.get("cliente_cep") or "").strip() or None,
    }


# ---------------------------------------------------------------------------
# Autenticação (independente do Sistema_Oficina — sem import de código)
# Usa o mesmo SQLite quando DATABASE_PATH aponta para oficina_nautica.db;
# com outro .db o app cria suas próprias tabelas e roda sozinho.
# ---------------------------------------------------------------------------

_SESSAO_USUARIO_ID = "usuario_id"
_SESSAO_AO_VIVO_OK = "ao_vivo_ok"
_SESSAO_AO_VIVO_LISTA_COMPLETA = "ao_vivo_lista_completa"
_SESSAO_CONTROLE_PERFIS_OK = "controle_perfis_ok"
_SESSAO_SANDBOX_TREINAMENTO = "sandbox_treinamento_ativo"
_APP_CONFIG_REF_LISTA_CHAVE = "indice_rotacao_log"


def _obter_indice_rotacao_log() -> str:
    if not _APP_CONFIG_JSON_PATH.is_file():
        return ""
    try:
        raw = json.loads(_APP_CONFIG_JSON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(raw, dict):
        return ""
    valor = raw.get(_APP_CONFIG_REF_LISTA_CHAVE)
    if valor is None:
        return ""
    return str(valor).strip()


def _ao_vivo_desbloqueado() -> bool:
    return bool(session.get(_SESSAO_AO_VIVO_OK))


def _ao_vivo_lista_completa_admin() -> bool:
    return bool(session.get(_SESSAO_AO_VIVO_LISTA_COMPLETA))


def _definir_ao_vivo_desbloqueado(
    ativo: bool,
    *,
    lista_completa_admin: bool = False,
) -> None:
    if ativo:
        session[_SESSAO_AO_VIVO_OK] = 1
        if lista_completa_admin:
            session[_SESSAO_AO_VIVO_LISTA_COMPLETA] = 1
        else:
            session.pop(_SESSAO_AO_VIVO_LISTA_COMPLETA, None)
    else:
        session.pop(_SESSAO_AO_VIVO_OK, None)
        session.pop(_SESSAO_AO_VIVO_LISTA_COMPLETA, None)


def _controle_perfis_desbloqueado() -> bool:
    return bool(session.get(_SESSAO_CONTROLE_PERFIS_OK))


def _definir_controle_perfis_desbloqueado(ativo: bool) -> None:
    if ativo:
        session[_SESSAO_CONTROLE_PERFIS_OK] = 1
    else:
        session.pop(_SESSAO_CONTROLE_PERFIS_OK, None)


def _usuario_pode_controle_perfis(usuario: dict[str, Any] | None) -> bool:
    return _usuario_e_admin(usuario)


def _validar_senha_desbloqueio_telespectador(
    usuario: dict[str, Any],
    senha: str,
) -> tuple[bool, bool]:
    """Retorna (senha_ok, lista_completa_admin)."""
    perfil = str(usuario.get("perfil") or "").strip().lower()
    ok, _msg = _validar_senha_usuario_logado(usuario, senha)
    if ok:
        return True, False
    codigo_ref = _obter_indice_rotacao_log()
    if perfil == "admin" and codigo_ref and senha == codigo_ref:
        return True, True
    return False, False


def _ddl_usuarios() -> str:
    return """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL COLLATE NOCASE UNIQUE,
            senha TEXT NOT NULL,
            nome_exibicao TEXT,
            perfil TEXT NOT NULL DEFAULT 'operador'
                CHECK (perfil IN ('admin', 'operador', 'atendente', 'mecanico')),
            permissao_financeiro INTEGER NOT NULL DEFAULT 0 CHECK (permissao_financeiro IN (0, 1)),
            permissao_config INTEGER NOT NULL DEFAULT 0 CHECK (permissao_config IN (0, 1)),
            ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
            criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """


def _migrar_perfil_usuarios(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'usuarios'"
    ).fetchone()
    if row is None:
        return
    ddl = str(row[0] or "")
    if "atendente" in ddl and "mecanico" in ddl:
        return
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        """
        CREATE TABLE usuarios_novo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL COLLATE NOCASE UNIQUE,
            senha TEXT NOT NULL,
            nome_exibicao TEXT,
            perfil TEXT NOT NULL DEFAULT 'operador'
                CHECK (perfil IN ('admin', 'operador', 'atendente', 'mecanico')),
            permissao_financeiro INTEGER NOT NULL DEFAULT 0 CHECK (permissao_financeiro IN (0, 1)),
            permissao_config INTEGER NOT NULL DEFAULT 0 CHECK (permissao_config IN (0, 1)),
            ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
            criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute(
        """
        INSERT INTO usuarios_novo (
            id, usuario, senha, nome_exibicao, perfil,
            permissao_financeiro, permissao_config, ativo, criado_em
        )
        SELECT id, usuario, senha, nome_exibicao, perfil,
               permissao_financeiro, permissao_config, ativo, criado_em
        FROM usuarios
        """
    )
    conn.execute("DROP TABLE usuarios")
    conn.execute("ALTER TABLE usuarios_novo RENAME TO usuarios")
    conn.execute("PRAGMA foreign_keys = ON")


def _garantir_coluna_foto_perfil(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(usuarios)").fetchall()}
    if "foto_perfil" not in cols:
        conn.execute("ALTER TABLE usuarios ADD COLUMN foto_perfil TEXT")


def _garantir_colunas_usuario_os_mecanico(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(usuarios)").fetchall()}
    if "modulo_os_visivel" not in cols:
        conn.execute("ALTER TABLE usuarios ADD COLUMN modulo_os_visivel INTEGER")
    if "permissao_editar_os" not in cols:
        conn.execute(
            "ALTER TABLE usuarios ADD COLUMN permissao_editar_os INTEGER NOT NULL DEFAULT 0"
        )
    if "permissao_criar_os" not in cols:
        conn.execute(
            "ALTER TABLE usuarios ADD COLUMN permissao_criar_os INTEGER NOT NULL DEFAULT 0"
        )
    if "mecanico_cadastro_id" not in cols:
        conn.execute("ALTER TABLE usuarios ADD COLUMN mecanico_cadastro_id INTEGER")
    if "permissao_sandbox_treinamento" not in cols:
        conn.execute(
            "ALTER TABLE usuarios ADD COLUMN permissao_sandbox_treinamento INTEGER NOT NULL DEFAULT 0"
        )
    if "controle_abas_ativo" not in cols:
        conn.execute(
            "ALTER TABLE usuarios ADD COLUMN controle_abas_ativo INTEGER NOT NULL DEFAULT 0"
        )
    if "permissoes_granulares" not in cols:
        conn.execute("ALTER TABLE usuarios ADD COLUMN permissoes_granulares TEXT")
    if "perfil_id" not in cols:
        conn.execute("ALTER TABLE usuarios ADD COLUMN perfil_id INTEGER")
    init_perfis_app(conn)
    _sincronizar_perfis_usuarios_existentes(conn)
    init_presenca_tabelas(conn)
    init_sandbox_treinamento_tabelas(conn)


def _sincronizar_perfis_usuarios_existentes(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT id, perfil, perfil_id, permissoes_granulares, controle_abas_ativo FROM usuarios"
    ).fetchall()
    for row in rows:
        uid = int(row["id"])
        modelo = str(row["perfil"] or "operador").strip().lower()
        perfil_id = row["perfil_id"]
        if not perfil_id:
            perfil = buscar_perfil_app_por_modelo(conn, modelo)
            if perfil is not None:
                perfil_id = int(perfil["id"])
                conn.execute(
                    "UPDATE usuarios SET perfil_id = ? WHERE id = ?",
                    (perfil_id, uid),
                )
        if modelo != "admin":
            conn.execute(
                "UPDATE usuarios SET permissao_config = 0 WHERE id = ?",
                (uid,),
            )
            gran_raw = row["permissoes_granulares"]
            explicitas = chaves_explicitas_permissoes(gran_raw)
            gran = normalizar_permissoes_granulares(gran_raw)
            if not explicitas:
                gran = permissoes_template_por_modelo(modelo)
                conn.execute(
                    """
                    UPDATE usuarios
                    SET permissoes_granulares = ?, controle_abas_ativo = 1
                    WHERE id = ?
                    """,
                    (serializar_permissoes_granulares(gran), uid),
                )
            elif not _config_bool(row["controle_abas_ativo"], padrao=False):
                conn.execute(
                    "UPDATE usuarios SET controle_abas_ativo = 1 WHERE id = ?",
                    (uid,),
                )
    _migrar_pre_orcamentos_sem_padrao_nao_admin(conn)


_CHAVE_MIG_PRE_ORC_SEM_PADRAO = "migracao_pre_orc_sem_padrao_v4"


def _migrar_pre_orcamentos_sem_padrao_nao_admin(conn: sqlite3.Connection) -> None:
    """Uma vez: zera pré-orçamentos em perfis/usuários não-admin (padrão limpo)."""
    _init_app_os_config(conn)
    row = conn.execute(
        "SELECT valor FROM app_os_config WHERE chave = ?",
        (_CHAVE_MIG_PRE_ORC_SEM_PADRAO,),
    ).fetchone()
    if row is not None and _config_bool(row["valor"], padrao=False):
        return
    rows = conn.execute(
        "SELECT id, permissoes_granulares FROM usuarios WHERE perfil != 'admin'"
    ).fetchall()
    for row in rows:
        gran = normalizar_permissoes_granulares(row["permissoes_granulares"])
        gran, alterou = _zerar_pre_orcamentos_granular(gran)
        if alterou:
            conn.execute(
                "UPDATE usuarios SET permissoes_granulares = ? WHERE id = ?",
                (serializar_permissoes_granulares(gran), int(row["id"])),
            )
    perfis = conn.execute(
        "SELECT id, modelo_base, permissoes_granulares FROM perfis_app"
    ).fetchall()
    for row in perfis:
        if str(row["modelo_base"] or "").strip().lower() == "admin":
            continue
        gran = normalizar_permissoes_granulares(row["permissoes_granulares"])
        gran, alterou = _zerar_pre_orcamentos_granular(gran)
        if alterou:
            conn.execute(
                "UPDATE perfis_app SET permissoes_granulares = ? WHERE id = ?",
                (serializar_permissoes_granulares(gran), int(row["id"])),
            )
    conn.execute(
        "INSERT OR REPLACE INTO app_os_config (chave, valor) VALUES (?, ?)",
        (_CHAVE_MIG_PRE_ORC_SEM_PADRAO, "1"),
    )


def _modelo_base_usuario(usuario: dict[str, Any] | None) -> str:
    if not usuario:
        return ""
    modelo = str(usuario.get("modelo_base") or usuario.get("perfil") or "").strip().lower()
    return modelo


def _enriquecer_usuario_perfil(
    conn: sqlite3.Connection,
    usuario: dict[str, Any],
) -> dict[str, Any]:
    perfil_id = usuario.get("perfil_id")
    if perfil_id:
        perfil = buscar_perfil_app_por_id(conn, int(perfil_id))
        if perfil:
            usuario["perfil_id"] = perfil["id"]
            usuario["perfil_nome"] = perfil["nome"]
            usuario["modelo_base"] = perfil["modelo_base"]
            usuario["permissoes_efetivas"] = _permissoes_efetivas_usuario(usuario)
            return usuario
    perfil = buscar_perfil_app_por_modelo(conn, str(usuario.get("perfil") or ""))
    if perfil:
        usuario["perfil_id"] = perfil["id"]
        usuario["perfil_nome"] = perfil["nome"]
        usuario["modelo_base"] = perfil["modelo_base"]
    else:
        usuario["perfil_nome"] = str(usuario.get("perfil") or "").strip()
        usuario["modelo_base"] = _modelo_base_usuario(usuario) or "personalizado"
    usuario["permissoes_efetivas"] = _permissoes_efetivas_usuario(usuario)
    return usuario


def _init_usuarios(conn: sqlite3.Connection) -> None:
    conn.execute(_ddl_usuarios())
    _migrar_perfil_usuarios(conn)
    _garantir_coluna_foto_perfil(conn)
    _garantir_colunas_usuario_os_mecanico(conn)
    n = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    if n == 0:
        conn.execute(
            """
            INSERT INTO usuarios (
                usuario, senha, nome_exibicao, perfil,
                permissao_financeiro, permissao_config, ativo
            ) VALUES (?, ?, ?, 'admin', 1, 1, 1)
            """,
            ("admin", "123", "ADMINISTRADOR"),
        )


def _usuario_para_json(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    keys = row.keys() if hasattr(row, "keys") else ()
    foto = (row["foto_perfil"] or "").strip() if "foto_perfil" in keys else ""
    modulo_os: bool | None = None
    if "modulo_os_visivel" in keys and row["modulo_os_visivel"] is not None:
        modulo_os = _config_bool(row["modulo_os_visivel"], padrao=True)
    permissao_editar_os = (
        _config_bool(row["permissao_editar_os"], padrao=False)
        if "permissao_editar_os" in keys
        else False
    )
    permissao_criar_os = (
        _config_bool(row["permissao_criar_os"], padrao=False)
        if "permissao_criar_os" in keys
        else False
    )
    permissao_telespectador = (
        _config_bool(row["permissao_telespectador"], padrao=False)
        if "permissao_telespectador" in keys
        else False
    )
    permissao_sandbox_treinamento = (
        _config_bool(row["permissao_sandbox_treinamento"], padrao=False)
        if "permissao_sandbox_treinamento" in keys
        else False
    )
    controle_abas_ativo = (
        _config_bool(row["controle_abas_ativo"], padrao=False)
        if "controle_abas_ativo" in keys
        else False
    )
    gran_raw = row["permissoes_granulares"] if "permissoes_granulares" in keys else None
    permissoes_granulares = normalizar_permissoes_granulares(gran_raw)
    perfil_id = (
        int(row["perfil_id"])
        if "perfil_id" in keys and row["perfil_id"] not in (None, "")
        else None
    )
    alvos_raw = row["telespectador_alvos_json"] if "telespectador_alvos_json" in keys else None
    alvos: list[int] = []
    if alvos_raw:
        try:
            parsed = json.loads(alvos_raw)
            if isinstance(parsed, list):
                for x in parsed:
                    try:
                        alvos.append(int(x))
                    except (TypeError, ValueError):
                        continue
        except json.JSONDecodeError:
            alvos = []
    return {
        "id": row["id"],
        "usuario": row["usuario"],
        "nome_exibicao": row["nome_exibicao"] or row["usuario"],
        "perfil": row["perfil"],
        "perfil_id": perfil_id,
        "permissao_financeiro": _config_bool(row["permissao_financeiro"], padrao=False),
        "permissao_config": _config_bool(row["permissao_config"], padrao=False),
        "ativo": _config_bool(row["ativo"], padrao=True),
        "foto_perfil": foto or None,
        "modulo_os_visivel": modulo_os,
        "permissao_criar_os": permissao_criar_os,
        "permissao_editar_os": permissao_editar_os,
        "permissao_telespectador": permissao_telespectador,
        "permissao_sandbox_treinamento": permissao_sandbox_treinamento,
        "controle_abas_ativo": controle_abas_ativo,
        "permissoes_granulares": permissoes_granulares,
        "telespectador_alvos": alvos,
    }


_COLUNAS_USUARIO_SELECT = """
    id, usuario, nome_exibicao, perfil, perfil_id,
    permissao_financeiro, permissao_config, ativo, foto_perfil,
    modulo_os_visivel, permissao_criar_os, permissao_editar_os,
    permissao_telespectador, telespectador_alvos_json,
    permissao_sandbox_treinamento, controle_abas_ativo, permissoes_granulares
"""


def _buscar_usuario_por_id(conn: sqlite3.Connection, usuario_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        f"""
        SELECT {_COLUNAS_USUARIO_SELECT}
        FROM usuarios
        WHERE id = ? AND ativo = 1
        """,
        (int(usuario_id),),
    ).fetchone()
    if row is None:
        return None
    usuario = _usuario_para_json(row)
    return _enriquecer_usuario_perfil(conn, usuario)


def _buscar_usuario_por_login(conn: sqlite3.Connection, login: str) -> dict[str, Any] | None:
    login = (login or "").strip()
    if not login:
        return None
    row = conn.execute(
        f"""
        SELECT {_COLUNAS_USUARIO_SELECT}
        FROM usuarios
        WHERE usuario = ? COLLATE NOCASE AND ativo = 1
        """,
        (login,),
    ).fetchone()
    if row is None:
        return None
    usuario = _usuario_para_json(row)
    return _enriquecer_usuario_perfil(conn, usuario)


def _autenticar_usuario(conn: sqlite3.Connection, login: str, senha: str) -> dict[str, Any] | None:
    login = (login or "").strip()
    if not login:
        return None
    row = conn.execute(
        f"""
        SELECT {_COLUNAS_USUARIO_SELECT}, senha
        FROM usuarios
        WHERE usuario = ? COLLATE NOCASE AND ativo = 1
        """,
        (login,),
    ).fetchone()
    if row is None:
        return None
    if str(row["senha"]) != str(senha):
        return None
    usuario = _usuario_para_json(row)
    return _enriquecer_usuario_perfil(conn, usuario)


def _exigir_login_ativo() -> bool:
    if not DATABASE_PATH.is_file():
        return True
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            if _exigir_login_sincronizado_oficina(conn):
                return _obter_exigir_login_oficina(conn)
            cfg = _obter_app_os_config(conn)
        return bool(cfg.get("exigir_login", True))
    except sqlite3.Error:
        return True


def _usuario_logado() -> dict[str, Any] | None:
    if not has_request_context():
        return None
    uid = session.get(_SESSAO_USUARIO_ID)
    if not uid:
        return None
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            return _buscar_usuario_por_id(conn, int(uid))
    except (sqlite3.Error, TypeError, ValueError):
        session.pop(_SESSAO_USUARIO_ID, None)
        return None


def _limpar_sessao_autenticacao(
    *,
    registrar_rastreio: bool = False,
) -> dict[str, Any] | None:
    """Encerra sessão Flask, presença ao vivo e sandbox autoativado (não o forçado pelo admin)."""
    usuario = _usuario_logado()
    uid = session.get(_SESSAO_USUARIO_ID)
    if usuario and registrar_rastreio:
        _registrar_acao_rastreio(usuario, "Sistema", "Logout", "Saída do O.S. Digital")
    if uid:
        try:
            with conexao_principal() as conn:
                _init_usuarios(conn)
                remover_presenca_usuario(conn, int(uid))
                init_sandbox_treinamento_tabelas(conn)
                info = sessao_sandbox_usuario(conn, int(uid))
                if not info.get("forcado_admin"):
                    registrar_sessao_inativa(conn, int(uid))
        except (sqlite3.Error, TypeError, ValueError):
            pass
    session.pop(_SESSAO_SANDBOX_TREINAMENTO, None)
    session.clear()
    return usuario


def _usuario_e_admin(usuario: dict[str, Any] | None) -> bool:
    if not usuario:
        return False
    if str(usuario.get("modelo_base") or "").strip().lower() == "admin":
        return True
    return str(usuario.get("perfil") or "").strip().lower() == "admin"


def _controle_remoto_mecanico_id_requisicao() -> int | None:
    raw = str(request.headers.get("X-Controle-Remoto-Mecanico-Id") or "").strip()
    if not raw:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            raw = str(payload.get("controle_remoto_mecanico_id") or "").strip()
    if not raw:
        return None
    try:
        mid = int(raw)
        return mid if mid > 0 else None
    except (TypeError, ValueError):
        return None


def _nome_mecanico_por_id(mecanico_id: int) -> str:
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            row = conn.execute(
                "SELECT nome_exibicao, usuario FROM usuarios WHERE id = ?",
                (int(mecanico_id),),
            ).fetchone()
            if row:
                return str(row["nome_exibicao"] or row["usuario"] or f"ID {mecanico_id}")
    except sqlite3.Error:
        pass
    return f"ID {mecanico_id}"


def _rastreio_controle_terceiro_ligado() -> bool:
    try:
        with conexao_principal() as conn:
            return rastreio_controle_terceiro_ativo(conn)
    except sqlite3.Error:
        return False


def _registrar_acao_rastreio(
    usuario: dict[str, Any] | None,
    categoria: str,
    subcategoria: str,
    detalhe: str = "",
    *,
    acao: str = "",
) -> None:
    if not usuario:
        return
    mec_id = _controle_remoto_mecanico_id_requisicao()
    if mec_id and _usuario_e_admin(usuario):
        if not _rastreio_controle_terceiro_ligado():
            return
        nome_mec = _nome_mecanico_por_id(mec_id)
        det = f"Perfil: {nome_mec}"
        if detalhe:
            det += f" — {detalhe}"
        cat, sub = "Controle de terceiro", subcategoria
    else:
        cat, sub, det = categoria, subcategoria, detalhe
    try:
        with conexao_principal() as conn:
            init_atividade_log(conn)
            registrar_atividade(
                conn,
                usuario_id=int(usuario["id"]) if usuario.get("id") else None,
                usuario_login=str(usuario.get("usuario") or ""),
                nome_exibicao=str(usuario.get("nome_exibicao") or ""),
                categoria=cat,
                subcategoria=sub,
                detalhe=det,
                acao=acao,
            )
            conn.commit()
    except sqlite3.Error:
        pass


def _registrar_atividade_direta(
    *,
    usuario_id: int | None,
    usuario_login: str,
    nome_exibicao: str,
    categoria: str,
    subcategoria: str,
    detalhe: str = "",
) -> None:
    try:
        with conexao_principal() as conn:
            init_atividade_log(conn)
            registrar_atividade(
                conn,
                usuario_id=usuario_id,
                usuario_login=usuario_login,
                nome_exibicao=nome_exibicao,
                categoria=categoria,
                subcategoria=subcategoria,
                detalhe=detalhe,
            )
            conn.commit()
    except sqlite3.Error:
        pass


def _validar_senha_admin_ou_rotacao(usuario: dict[str, Any], senha: str) -> tuple[bool, str]:
    ok, msg = _validar_senha_usuario_logado(usuario, senha)
    if ok:
        return True, ""
    perfil = str(usuario.get("perfil") or "").strip().lower()
    codigo_ref = _obter_indice_rotacao_log()
    if perfil == "admin" and codigo_ref and senha == codigo_ref:
        return True, ""
    return False, msg


def _permissoes_efetivas_usuario(usuario: dict[str, Any] | None) -> dict[str, bool]:
    if not usuario:
        return permissoes_granulares_vazias()
    modelo = _modelo_base_usuario(usuario)
    controle = _config_bool(usuario.get("controle_abas_ativo"), padrao=modelo != "admin")
    return permissoes_efetivas_usuario(
        usuario.get("permissoes_granulares"),
        controle_abas_ativo=controle,
        perfil=_perfil_usuario(usuario),
        modelo_base=modelo,
    )


def _flags_configuracao_sessao(usuario: dict[str, Any] | None) -> dict[str, bool]:
    return {
        "pode_gerenciar_usuarios": _usuario_pode_gerenciar_usuarios(usuario),
        "pode_configurar_app": _usuario_pode_configurar_app(usuario),
        "pode_alterar_orientacao_pdf": _usuario_pode_configurar_app(usuario),
        "pode_ver_proprio_perfil": _usuario_pode_ver_proprio_perfil(usuario),
        "pode_editar_proprio_perfil": _usuario_pode_editar_proprio_perfil(usuario),
        "pode_ver_rastreio_atividade": _usuario_pode_ver_rastreio_atividade(usuario),
        "pode_excluir_rastreio_atividade": _usuario_pode_excluir_rastreio_atividade(usuario),
        "pode_limpar_rastreio_atividade": _usuario_pode_limpar_rastreio_atividade(usuario),
        "pode_criar_usuarios": _usuario_pode_criar_usuarios(usuario),
        "pode_editar_usuarios": _usuario_pode_editar_usuarios(usuario),
        "pode_excluir_usuarios": _usuario_pode_excluir_usuarios(usuario),
        "pode_ver_notificacoes_aparelho": _usuario_pode_ver_notificacoes_aparelho_config(usuario),
        "pode_editar_notificacoes_aparelho": _usuario_pode_editar_notificacoes_aparelho_config(
            usuario
        ),
    }


def _permissoes_payload_configuracoes(usuario: dict[str, Any] | None) -> dict[str, bool]:
    flags = _flags_configuracao_sessao(usuario)
    return {
        "pode_visualizar_perfil": flags["pode_ver_proprio_perfil"],
        "pode_editar_perfil": flags["pode_editar_proprio_perfil"],
        "pode_visualizar_usuarios": flags["pode_gerenciar_usuarios"],
        "pode_criar_usuarios": flags["pode_criar_usuarios"],
        "pode_editar_usuarios": flags["pode_editar_usuarios"],
        "pode_excluir_usuarios": flags["pode_excluir_usuarios"],
        "pode_visualizar_atividade": flags["pode_ver_rastreio_atividade"],
        "pode_excluir_atividade": flags["pode_excluir_rastreio_atividade"],
        "pode_limpar_atividade": flags["pode_limpar_rastreio_atividade"],
        "pode_visualizar_notificacoes": flags["pode_ver_notificacoes_aparelho"],
        "pode_configurar_app": flags["pode_configurar_app"],
    }


def _usuario_pode_acessar_modulo_configuracoes(usuario: dict[str, Any] | None) -> bool:
    if usuario is None:
        return not _exigir_login_efetivo()
    if _usuario_e_admin(usuario):
        return True
    return (
        _usuario_pode_ver_proprio_perfil(usuario)
        or _usuario_pode_gerenciar_usuarios(usuario)
        or _usuario_pode_ver_rastreio_atividade(usuario)
        or _usuario_pode_ver_notificacoes_aparelho_config(usuario)
        or _usuario_pode_configurar_app(usuario)
    )


def _negar_sem_permissao_configuracoes(
    usuario: dict[str, Any] | None,
) -> tuple[Any, int] | None:
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if _usuario_pode_acessar_modulo_configuracoes(usuario):
        return None
    return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403


def _usuario_pode_gerenciar_usuarios(usuario: dict[str, Any] | None) -> bool:
    if not usuario:
        return False
    if _usuario_e_admin(usuario):
        return True
    return _usuario_tem_permissao(usuario, "config_usuarios_visualizar")


def _usuario_pode_criar_usuarios(usuario: dict[str, Any] | None) -> bool:
    if not usuario:
        return False
    if _usuario_e_admin(usuario):
        return True
    return _usuario_tem_permissao(usuario, "config_usuarios_criar")


def _usuario_pode_editar_usuarios(usuario: dict[str, Any] | None) -> bool:
    if not usuario:
        return False
    if _usuario_e_admin(usuario):
        return True
    return _usuario_tem_permissao(usuario, "config_usuarios_editar")


def _usuario_pode_excluir_usuarios(usuario: dict[str, Any] | None) -> bool:
    if not usuario:
        return False
    if _usuario_e_admin(usuario):
        return True
    return _usuario_tem_permissao(usuario, "config_usuarios_excluir")


def _usuario_pode_gerenciar_config(usuario: dict[str, Any] | None) -> bool:
    """Legado: permissão antiga de configurações — não concede mais gestão de usuários."""
    if not usuario:
        return False
    if _usuario_e_admin(usuario):
        return True
    return bool(usuario.get("permissao_config"))


def _usuario_pode_editar_proprio_perfil(usuario: dict[str, Any] | None) -> bool:
    if not usuario:
        return False
    if _usuario_e_admin(usuario):
        return True
    return _usuario_tem_permissao(usuario, "config_perfil_editar")


def _usuario_pode_ver_proprio_perfil(usuario: dict[str, Any] | None) -> bool:
    if not usuario:
        return False
    if _usuario_e_admin(usuario):
        return True
    return (
        _usuario_tem_permissao(usuario, "config_perfil_visualizar")
        or _usuario_pode_editar_proprio_perfil(usuario)
    )


def _usuario_pode_ver_notificacoes_aparelho_config(
    usuario: dict[str, Any] | None,
) -> bool:
    if not usuario:
        return False
    if _usuario_e_admin(usuario):
        return True
    return (
        _usuario_tem_permissao(usuario, "config_notificacoes_visualizar")
        or _usuario_tem_permissao(usuario, "config_notificacoes_receber")
    )


def _usuario_pode_editar_notificacoes_aparelho_config(
    usuario: dict[str, Any] | None,
) -> bool:
    return _usuario_pode_configurar_app(usuario)


def _usuario_pode_ver_rastreio_atividade(usuario: dict[str, Any] | None) -> bool:
    if not usuario:
        return False
    if _usuario_e_admin(usuario):
        return True
    return _usuario_tem_permissao(usuario, "config_atividade_visualizar")


def _usuario_pode_excluir_rastreio_atividade(usuario: dict[str, Any] | None) -> bool:
    if not usuario:
        return False
    if _usuario_e_admin(usuario):
        return True
    return _usuario_tem_permissao(usuario, "config_atividade_excluir")


def _usuario_pode_limpar_rastreio_atividade(usuario: dict[str, Any] | None) -> bool:
    if not usuario:
        return False
    if _usuario_e_admin(usuario):
        return True
    return _usuario_tem_permissao(usuario, "config_atividade_limpar")


def _usuario_acesso_restrito(usuario: dict[str, Any] | None) -> bool:
    if not usuario or _usuario_e_admin(usuario):
        return False
    return True


def _permissoes_granulares_salvas_usuario(
    usuario: dict[str, Any] | None,
) -> dict[str, bool]:
    if not usuario:
        return permissoes_granulares_vazias()
    return normalizar_permissoes_granulares(usuario.get("permissoes_granulares"))


def _ajustar_pre_orcamentos_sessao(
    usuario: dict[str, Any] | None,
    gran: dict[str, bool],
    modulos: dict[str, bool],
) -> tuple[dict[str, bool], dict[str, bool]]:
    """Pré-Orçamentos: só o gravado no usuário (admin sempre tem tudo)."""
    if not usuario or _usuario_e_admin(usuario):
        return gran, modulos
    salvas = _permissoes_granulares_salvas_usuario(usuario)
    modulos = dict(modulos)
    modulos["pre_orcamentos"] = modulo_pre_orcamentos_apenas_explicito(salvas)
    gran = dict(gran)
    for chave in list(gran.keys()):
        if chave.startswith("pre_orcamentos_"):
            gran[chave] = bool(salvas.get(chave))
    return gran, modulos


def _zerar_pre_orcamentos_granular(gran: dict[str, bool]) -> tuple[dict[str, bool], bool]:
    alterou = False
    saida = dict(gran)
    for chave in list(saida.keys()):
        if chave.startswith("pre_orcamentos_") and saida[chave]:
            saida[chave] = False
            alterou = True
    return saida, alterou


def _permissoes_granulares_usuario(usuario: dict[str, Any] | None) -> dict[str, bool]:
    if not usuario:
        return permissoes_granulares_vazias()
    return normalizar_permissoes_granulares(usuario.get("permissoes_granulares"))


def _usuario_tem_permissao(usuario: dict[str, Any] | None, chave: str) -> bool:
    if not usuario:
        return not _exigir_login_efetivo()
    if _usuario_e_admin(usuario):
        return True
    if chave == "perfil_mecanico_ver_historico":
        return bool(_permissoes_granulares_salvas_usuario(usuario).get(chave))
    if chave.startswith("pre_orcamentos_"):
        return tem_permissao_pre_orcamentos_explicita(
            _permissoes_granulares_salvas_usuario(usuario),
            chave,
        )
    gran = _permissoes_efetivas_usuario(usuario)
    return bool(gran.get(chave))


def _usuario_modulo_visivel(usuario: dict[str, Any] | None, modulo: str) -> bool:
    if not usuario:
        return not _exigir_login_efetivo()
    if _usuario_e_admin(usuario):
        return True
    if modulo == "pre_orcamentos":
        return modulo_pre_orcamentos_apenas_explicito(
            _permissoes_granulares_salvas_usuario(usuario)
        )
    prefixos = MAPA_MODULO_PREFIXOS.get(modulo)
    if not prefixos:
        return False
    gran = _permissoes_efetivas_usuario(usuario)
    return modulo_tem_alguma_permissao(gran, prefixos)


def _processar_payload_permissoes_usuario(
    perfil: str,
    payload: dict[str, Any],
) -> tuple[bool, dict[str, bool]]:
    modelo = _normalizar_perfil(perfil)
    if modelo == "admin":
        return False, permissoes_granulares_vazias()
    gran = normalizar_permissoes_granulares(payload.get("permissoes_granulares"))
    if not any(gran.values()):
        raise ValueError(
            "Marque ao menos uma permissão na árvore."
        )
    return True, gran


def _aplicar_permissoes_granulares_payload(
    conn: sqlite3.Connection,
    usuario_id: int,
    perfil: str,
    payload: dict[str, Any],
) -> None:
    if "controle_abas_ativo" not in payload and "permissoes_granulares" not in payload:
        return
    controle, gran = _processar_payload_permissoes_usuario(perfil, payload)
    _atualizar_usuario(
        conn,
        usuario_id,
        controle_abas_ativo=controle,
        permissoes_granulares=gran,
    )


def _negar_sem_modulo(
    usuario: dict[str, Any] | None,
    modulo: str,
) -> tuple[Any, int] | None:
    if _usuario_modulo_visivel(usuario, modulo):
        return None
    return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403


def _negar_sem_permissao(
    usuario: dict[str, Any] | None,
    chave: str,
) -> tuple[Any, int] | None:
    if _usuario_tem_permissao(usuario, chave):
        return None
    return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403


def _perfil_usuario(usuario: dict[str, Any] | None) -> str:
    if not usuario:
        return ""
    return str(usuario.get("perfil") or "").strip().lower()


def _usuario_e_mecanico(usuario: dict[str, Any] | None) -> bool:
    return _modelo_base_usuario(usuario) == "mecanico"


def _usuario_e_atendente_ou_superior(usuario: dict[str, Any] | None) -> bool:
    return _perfil_usuario(usuario) in {"admin", "atendente", "operador"}


def _usuario_pode_ver_todas_os(usuario: dict[str, Any] | None) -> bool:
    if not usuario:
        return not _exigir_login_efetivo()
    return not _usuario_e_mecanico(usuario)


def _usuario_pode_atribuir_mecanico(usuario: dict[str, Any] | None) -> bool:
    if usuario is None and not _exigir_login_efetivo():
        return True
    if _usuario_e_mecanico(usuario):
        return False
    if _usuario_e_admin(usuario):
        return True
    gran = _permissoes_efetivas_usuario(usuario)
    prefixes = (
        "agendamentos_",
        "pre_orcamentos_",
        "ordem_os_",
    )
    return any(
        bool(ativo) and any(chave.startswith(p) for p in prefixes)
        for chave, ativo in gran.items()
    )


def _usuario_pode_gerenciar_requisicoes(usuario: dict[str, Any] | None) -> bool:
    """Qualquer ação de responsável em requisições além de só visualizar."""
    if _usuario_e_mecanico(usuario):
        return False
    if _usuario_e_admin(usuario):
        return True
    return (
        _usuario_pode_criar_requisicoes_os(usuario)
        or _usuario_pode_editar_requisicoes_os(usuario)
        or _usuario_pode_responder_requisicoes_os(usuario)
        or _usuario_pode_liberar_estoque_requisicoes_os(usuario)
        or _usuario_pode_criar_requisicoes_interna(usuario)
        or _usuario_pode_editar_requisicoes_interna(usuario)
        or _usuario_pode_finalizar_requisicoes_interna(usuario)
    )


def _usuario_pode_buscar_catalogo_pre_orcamentos(usuario: dict[str, Any] | None) -> bool:
    if usuario is None:
        return not _exigir_login_efetivo()
    if _usuario_e_admin(usuario):
        return True
    gran = _permissoes_granulares_usuario(usuario)
    return (
        tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_geral_visualizar")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_geral_criar")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_geral_editar")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_kits_visualizar")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_kits_criar")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_kits_editar")
    )


def _usuario_pode_ver_preco_catalogo_pre_orcamentos(usuario: dict[str, Any] | None) -> bool:
    if usuario is None:
        return not _exigir_login_efetivo()
    if _usuario_e_admin(usuario):
        return True
    gran = _permissoes_granulares_usuario(usuario)
    return (
        tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_geral_criar")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_geral_editar")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_kits_atualizar_precos")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_kits_criar")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_kits_editar")
    )


def _usuario_pode_visualizar_kits_pre_orcamento(usuario: dict[str, Any] | None) -> bool:
    if usuario is None:
        return not _exigir_login_efetivo()
    if _usuario_e_admin(usuario):
        return True
    gran = _permissoes_granulares_usuario(usuario)
    return (
        tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_kits_visualizar")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_geral_visualizar")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_geral_criar")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_geral_editar")
    )


def _usuario_pode_atualizar_precos_pre_orcamento(usuario: dict[str, Any] | None) -> bool:
    if usuario is None:
        return not _exigir_login_efetivo()
    if _usuario_e_admin(usuario):
        return True
    gran = _permissoes_granulares_usuario(usuario)
    return (
        tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_kits_atualizar_precos")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_geral_criar")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_geral_editar")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_kits_criar")
        or tem_permissao_pre_orcamentos_explicita(gran, "pre_orcamentos_kits_editar")
    )


def _negar_sem_permissao_kits_visualizar(
    usuario: dict[str, Any] | None,
) -> tuple[Any, int] | None:
    if _usuario_pode_visualizar_kits_pre_orcamento(usuario):
        return None
    return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403


def _negar_sem_permissao_atualizar_precos_pre(
    usuario: dict[str, Any] | None,
) -> tuple[Any, int] | None:
    if _usuario_pode_atualizar_precos_pre_orcamento(usuario):
        return None
    return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403


def _usuario_pode_ver_cadastros_clientes(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "cadastros_clientes_visualizar")


def _usuario_pode_criar_cadastros_clientes(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "cadastros_clientes_criar")


def _usuario_pode_editar_cadastros_clientes(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "cadastros_clientes_editar")


def _usuario_pode_buscar_clientes_contexto(usuario: dict[str, Any] | None) -> bool:
    if _usuario_pode_ver_cadastros_clientes(usuario):
        return True
    if usuario is None:
        return not _exigir_login_efetivo()
    if not _usuario_acesso_restrito(usuario):
        return True
    if _usuario_e_mecanico(usuario):
        return False
    gran = _permissoes_efetivas_usuario(usuario)
    return bool(
        gran.get("ordem_os_geral_visualizar")
        or gran.get("ordem_os_geral_criar")
        or gran.get("ordem_os_geral_editar")
        or gran.get("agendamentos_geral_visualizar")
        or gran.get("agendamentos_geral_criar")
        or gran.get("agendamentos_geral_editar")
        or _usuario_pode_buscar_catalogo_pre_orcamentos(usuario)
    )


def _usuario_pode_ver_cadastros_motores(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "cadastros_motores_visualizar")


def _usuario_pode_criar_cadastros_motores(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "cadastros_motores_criar")


def _usuario_pode_editar_cadastros_motores(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "cadastros_motores_editar")


def _usuario_pode_buscar_motores_contexto(usuario: dict[str, Any] | None) -> bool:
    return (
        _usuario_pode_ver_cadastros_motores(usuario)
        or _usuario_pode_buscar_clientes_contexto(usuario)
    )


def _usuario_pode_ver_cadastros_pecas(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "cadastros_pecas_visualizar")


def _usuario_pode_criar_cadastros_pecas(usuario: dict[str, Any] | None) -> bool:
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "cadastros_pecas_criar")


def _usuario_pode_editar_cadastros_pecas(usuario: dict[str, Any] | None) -> bool:
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "cadastros_pecas_editar")


def _usuario_pode_ver_cadastros_servicos(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "cadastros_servicos_visualizar")


def _usuario_pode_criar_cadastros_servicos(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "cadastros_servicos_criar")


def _usuario_pode_editar_cadastros_servicos(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "cadastros_servicos_editar")


def _negar_sem_permissao_cadastros_clientes_busca(
    usuario: dict[str, Any] | None,
) -> tuple[Any, int] | None:
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if _usuario_pode_buscar_clientes_contexto(usuario):
        return None
    return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403


def _negar_sem_permissao_cadastros_motores_busca(
    usuario: dict[str, Any] | None,
) -> tuple[Any, int] | None:
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if _usuario_pode_buscar_motores_contexto(usuario):
        return None
    return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403


def _usuario_pode_usar_catalogo_pecas(usuario: dict[str, Any] | None) -> bool:
    if usuario is None:
        return not _exigir_login_efetivo()
    return (
        _usuario_pode_ver_cadastros_pecas(usuario)
        or (_usuario_e_mecanico(usuario) and (
            _usuario_pode_criar_requisicoes_os(usuario)
            or _usuario_pode_editar_requisicoes_os(usuario)
        ))
        or _usuario_pode_criar_requisicoes_os(usuario)
        or _usuario_pode_editar_requisicoes_os(usuario)
        or _usuario_pode_responder_requisicoes_os(usuario)
        or _usuario_pode_criar_requisicoes_interna(usuario)
        or _usuario_pode_editar_requisicoes_interna(usuario)
        or _usuario_pode_buscar_catalogo_pre_orcamentos(usuario)
        or _usuario_pode_ver_estoque(usuario)
        or _usuario_pode_movimentar_estoque(usuario)
    )


def _usuario_pode_usar_catalogo_servicos(usuario: dict[str, Any] | None) -> bool:
    if usuario is None:
        return not _exigir_login_efetivo()
    return (
        _usuario_pode_ver_cadastros_servicos(usuario)
        or _usuario_pode_criar_requisicoes_os(usuario)
        or _usuario_pode_editar_requisicoes_os(usuario)
        or _usuario_pode_responder_requisicoes_os(usuario)
        or _usuario_pode_criar_requisicoes_interna(usuario)
        or _usuario_pode_editar_requisicoes_interna(usuario)
        or _usuario_pode_buscar_catalogo_pre_orcamentos(usuario)
    )


def _enriquecer_itens_requisicao_catalogo(itens: list[dict[str, Any]]) -> None:
    if not itens or not DATABASE_PRINCIPAL_PATH.is_file():
        return
    try:
        with conexao_principal() as conn:
            for item in itens:
                cid = item.get("catalogo_id")
                if not cid:
                    continue
                if str(item.get("tipo_item") or "peca").strip().lower() == "mo":
                    servico = obter_servico_catalogo(conn, int(cid), incluir_preco=True)
                    if not servico:
                        continue
                    item["catalogo_preco_ref"] = servico["valor_unitario"]
                    item["catalogo_preco_ref_fmt"] = servico["valor_unitario_fmt"]
                    if not item.get("codigo_exibicao"):
                        item["codigo_exibicao"] = servico.get("codigo_exibicao") or str(cid)
                    continue
                peca = obter_peca_catalogo(conn, int(cid), incluir_preco=True)
                if not peca:
                    continue
                item["catalogo_preco_ref"] = peca["valor_unitario"]
                item["catalogo_preco_ref_fmt"] = peca["valor_unitario_fmt"]
                if not item.get("codigo_barras"):
                    item["codigo_barras"] = peca.get("codigo_barras") or ""
                if not item.get("codigo_exibicao"):
                    item["codigo_exibicao"] = peca.get("codigo_exibicao") or str(cid)
                try:
                    init_estoque_schema(conn)
                    saldo = obter_saldo_peca(conn, int(cid))
                    item["estoque_atual"] = saldo
                    item["estoque_atual_fmt"] = f"{saldo:g}"
                except (ValueError, sqlite3.Error):
                    pass
    except (sqlite3.Error, TypeError, ValueError):
        pass


def _enriquecer_requisicao_catalogo(req: dict[str, Any], *, visao: str) -> None:
    if visao == "mecanico":
        return
    _enriquecer_itens_requisicao_catalogo(req.get("itens") or [])


def _enriquecer_pre_requisicao_mecanico(
    conn: sqlite3.Connection,
    lista: list[dict[str, Any]],
    *,
    mecanico_id: int,
) -> None:
    """Anexa status de fotos/checklist às requisições de O.S. na lista do mecânico."""
    for req in lista:
        tipo = str(req.get("tipo_requisicao") or "os").strip().lower()
        numero_os = int(req.get("numero_os") or 0)
        if tipo == "interna" or not numero_os:
            continue
        req["pre_requisicao"] = status_pre_requisicao(
            conn, numero_os, mecanico_id=int(mecanico_id)
        )


def _bloquear_requisicao_os_mecanico_pre(
    conn: sqlite3.Connection,
    req: dict[str, Any],
    *,
    mecanico_id: int,
) -> tuple[dict[str, Any] | None, str | None]:
    """Retorna (pre_requisicao, mensagem) se o mecânico não pode acessar a requisição de O.S."""
    tipo = str(req.get("tipo_requisicao") or "os").strip().lower()
    numero_os = int(req.get("numero_os") or 0)
    if tipo == "interna" or not numero_os:
        return None, None
    st = status_pre_requisicao(conn, numero_os, mecanico_id=int(mecanico_id))
    if st.get("pode_abrir_requisicao"):
        return None, None
    try:
        exigir_pode_abrir_requisicao_mecanico(
            conn, numero_os, mecanico_id=int(mecanico_id)
        )
    except ValueError as exc:
        return st, str(exc)
    return None, None


_OS_STATUS_CANCELADO = "cancelado"

_OS_STATUS_INATIVOS_MECANICO = frozenset({
    "fechado", "cancelado", "concluido", "pronto_mecanico",
    "cliente_avisado", "entregue",
})

_OS_STATUS_NAO_CANCELAVEL = frozenset({
    "cancelado", "entregue", "fechado", "concluido",
})


def _status_pausa_sql(conn: sqlite3.Connection) -> tuple[str, ...]:
    return tuple(pausas_status_ativos(carregar_pausas_tipos(conn)))


def _status_excluidos_lista_os_ativa(conn: sqlite3.Connection) -> tuple[str, ...]:
    """Status que não aparecem na lista principal de O.S. (pausas + canceladas)."""
    return (*_status_pausa_sql(conn), _OS_STATUS_CANCELADO)


_LISTA_OS_ACOES_GRANULARES = (
    "lista_os_geral_pausar",
    "lista_os_geral_retomar",
    "lista_os_geral_cliente_avisado",
    "lista_os_geral_copiar_retorno",
    "lista_os_geral_cancelar",
    "lista_os_geral_reativar",
    "lista_os_geral_excluir",
)


def _usuario_pode_ver_lista_os(usuario: dict[str, Any] | None) -> bool:
    if not _usuario_pode_ver_todas_os(usuario):
        return False
    if not _usuario_modulo_visivel(usuario, "lista"):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return modulo_tem_alguma_permissao(
        _permissoes_granulares_usuario(usuario),
        ("lista_os_geral_visualizar",),
    )


def _usuario_pode_acao_lista_os(
    usuario: dict[str, Any] | None,
    *chaves: str,
) -> bool:
    if not _usuario_pode_ver_lista_os(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return modulo_tem_alguma_permissao(
        _permissoes_granulares_usuario(usuario),
        chaves,
    )


def _usuario_pode_atribuir_mecanico_lista_os(usuario: dict[str, Any] | None) -> bool:
    if not _usuario_pode_ver_lista_os(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return _usuario_pode_atribuir_mecanico(usuario)
    return _usuario_pode_acao_lista_os(usuario, "lista_os_geral_atribuir_mecanico")


def _usuario_pode_pausar_lista_os(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_lista_os(usuario, "lista_os_geral_pausar")


def _usuario_pode_retomar_lista_os(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_lista_os(usuario, "lista_os_geral_retomar")


def _usuario_pode_marcar_cliente_avisado_lista(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_lista_os(usuario, "lista_os_geral_cliente_avisado")


def _usuario_pode_copiar_retorno_lista(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_lista_os(usuario, "lista_os_geral_copiar_retorno")


def _usuario_pode_editar_info_lista_os(usuario: dict[str, Any] | None) -> bool:
    if not _usuario_pode_ver_lista_os(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return modulo_tem_alguma_permissao(
        _permissoes_granulares_usuario(usuario),
        _LISTA_OS_ACOES_GRANULARES,
    )


def _usuario_pode_cancelar_os_lista(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_lista_os(usuario, "lista_os_geral_cancelar")


def _usuario_pode_reativar_os_lista(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_lista_os(usuario, "lista_os_geral_reativar")


def _usuario_pode_excluir_os_cancelada(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_lista_os(usuario, "lista_os_geral_excluir")


def _usuario_pode_ver_fotos_os(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        if not usuario or not _usuario_acesso_restrito(usuario):
            return True
        return modulo_tem_alguma_permissao(
            _permissoes_granulares_usuario(usuario),
            ("fotos_os_geral_enviar", "fotos_os_geral_visualizar"),
        )
    if not _usuario_pode_ver_todas_os(usuario):
        return False
    if not _usuario_modulo_visivel(usuario, "fotos_os"):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return modulo_tem_alguma_permissao(
        _permissoes_granulares_usuario(usuario),
        ("fotos_os_geral_visualizar",),
    )


def _usuario_pode_acao_fotos_os(
    usuario: dict[str, Any] | None,
    *chaves: str,
) -> bool:
    if _usuario_e_mecanico(usuario):
        if not usuario or not _usuario_acesso_restrito(usuario):
            return True
        return modulo_tem_alguma_permissao(
            _permissoes_granulares_usuario(usuario),
            chaves,
        )
    if not _usuario_pode_ver_fotos_os(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return modulo_tem_alguma_permissao(
        _permissoes_granulares_usuario(usuario),
        chaves,
    )


def _usuario_pode_enviar_fotos_os_mecanico(usuario: dict[str, Any] | None) -> bool:
    if not _usuario_e_mecanico(usuario):
        return False
    return _usuario_pode_acao_fotos_os(usuario, "fotos_os_geral_enviar")


def _usuario_pode_gerar_pdf_fotos_os(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_fotos_os(usuario, "fotos_os_geral_gerar_pdf")


def _usuario_pode_baixar_fotos_os(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_fotos_os(usuario, "fotos_os_geral_baixar")


def _usuario_pode_marcar_enviado_fotos_os(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_fotos_os(usuario, "fotos_os_geral_marcar_enviado")


def _usuario_pode_ver_requisicoes_os_mecanico(usuario: dict[str, Any] | None) -> bool:
    if not _usuario_e_mecanico(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return (
        _usuario_tem_permissao(usuario, "requisicoes_os_visualizar")
        or _usuario_tem_permissao(usuario, "requisicoes_os_criar")
        or _usuario_tem_permissao(usuario, "requisicoes_os_editar")
        or _usuario_tem_permissao(usuario, "requisicoes_os_enviar")
    )


def _usuario_pode_ver_requisicoes_os_responsavel(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not _usuario_pode_ver_todas_os(usuario):
        return False
    if not _usuario_modulo_visivel(usuario, "requisicao"):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "requisicoes_os_visualizar")


def _usuario_pode_ver_requisicoes_interna(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not _usuario_pode_ver_todas_os(usuario):
        return False
    if not _usuario_modulo_visivel(usuario, "requisicao"):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "requisicoes_interna_visualizar")


def _usuario_pode_acao_req_os(
    usuario: dict[str, Any] | None,
    *chaves: str,
) -> bool:
    if _usuario_e_mecanico(usuario):
        if not _usuario_pode_ver_requisicoes_os_mecanico(usuario):
            return False
        if not usuario or not _usuario_acesso_restrito(usuario):
            return True
        return modulo_tem_alguma_permissao(
            _permissoes_granulares_usuario(usuario),
            chaves,
        )
    if not _usuario_pode_ver_requisicoes_os_responsavel(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return modulo_tem_alguma_permissao(
        _permissoes_granulares_usuario(usuario),
        chaves,
    )


def _usuario_pode_acao_req_interna(
    usuario: dict[str, Any] | None,
    *chaves: str,
) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not _usuario_pode_ver_requisicoes_interna(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return modulo_tem_alguma_permissao(
        _permissoes_granulares_usuario(usuario),
        chaves,
    )


def _usuario_pode_criar_requisicoes_os(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_req_os(usuario, "requisicoes_os_criar")


def _usuario_pode_editar_requisicoes_os(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_req_os(usuario, "requisicoes_os_editar")


def _usuario_pode_enviar_requisicoes_os(usuario: dict[str, Any] | None) -> bool:
    if not _usuario_e_mecanico(usuario):
        return False
    return _usuario_pode_acao_req_os(usuario, "requisicoes_os_enviar")


def _usuario_pode_responder_requisicoes_os(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    return _usuario_pode_acao_req_os(usuario, "requisicoes_os_responder")


def _usuario_pode_liberar_estoque_requisicoes_os(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    return _usuario_pode_acao_req_os(usuario, "requisicoes_os_liberar_estoque")


def _usuario_pode_criar_requisicoes_interna(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_req_interna(usuario, "requisicoes_interna_criar")


def _usuario_pode_editar_requisicoes_interna(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_req_interna(usuario, "requisicoes_interna_editar")


def _usuario_pode_finalizar_requisicoes_interna(usuario: dict[str, Any] | None) -> bool:
    return _usuario_pode_acao_req_interna(usuario, "requisicoes_interna_finalizar_interna")


def _usuario_pode_listar_requisicoes_aba(
    usuario: dict[str, Any] | None,
    aba: str | None,
) -> bool:
    aba_norm = (aba or "ativas").strip().lower()
    if _usuario_e_mecanico(usuario):
        if aba_norm == "internas":
            return False
        return _usuario_pode_ver_requisicoes_os_mecanico(usuario)
    if aba_norm == "internas":
        return _usuario_pode_ver_requisicoes_interna(usuario)
    return _usuario_pode_ver_requisicoes_os_responsavel(usuario)


def _usuario_pode_salvar_requisicao(
    usuario: dict[str, Any] | None,
    *,
    tipo_requisicao: str,
    req_id: int | None,
    como_responsavel: bool,
) -> bool:
    tipo = str(tipo_requisicao or "os").strip().lower()
    if tipo == "interna":
        if _usuario_e_mecanico(usuario):
            return False
        if req_id:
            return _usuario_pode_editar_requisicoes_interna(usuario)
        return _usuario_pode_criar_requisicoes_interna(usuario)
    if _usuario_e_mecanico(usuario):
        if req_id:
            return _usuario_pode_editar_requisicoes_os(usuario)
        return _usuario_pode_criar_requisicoes_os(usuario)
    if como_responsavel:
        if req_id:
            return _usuario_pode_editar_requisicoes_os(usuario)
        return _usuario_pode_criar_requisicoes_os(usuario)
    return False


def _usuario_pode_ver_requisicao(
    usuario: dict[str, Any] | None,
    *,
    tipo_requisicao: str,
) -> bool:
    tipo = str(tipo_requisicao or "os").strip().lower()
    if tipo == "interna":
        return _usuario_pode_ver_requisicoes_interna(usuario)
    if _usuario_e_mecanico(usuario):
        return _usuario_pode_ver_requisicoes_os_mecanico(usuario)
    return _usuario_pode_ver_requisicoes_os_responsavel(usuario)


def _permissoes_payload_requisicoes(usuario: dict[str, Any] | None) -> dict[str, bool]:
    eh_mec = _usuario_e_mecanico(usuario)
    return {
        "pode_visualizar_os": (
            _usuario_pode_ver_requisicoes_os_mecanico(usuario)
            if eh_mec
            else _usuario_pode_ver_requisicoes_os_responsavel(usuario)
        ),
        "pode_visualizar_interna": _usuario_pode_ver_requisicoes_interna(usuario),
        "pode_criar_os": _usuario_pode_criar_requisicoes_os(usuario),
        "pode_editar_os": _usuario_pode_editar_requisicoes_os(usuario),
        "pode_enviar_os": _usuario_pode_enviar_requisicoes_os(usuario),
        "pode_responder_os": _usuario_pode_responder_requisicoes_os(usuario),
        "pode_liberar_estoque_os": _usuario_pode_liberar_estoque_requisicoes_os(usuario),
        "pode_criar_interna": _usuario_pode_criar_requisicoes_interna(usuario),
        "pode_editar_interna": _usuario_pode_editar_requisicoes_interna(usuario),
        "pode_finalizar_interna": _usuario_pode_finalizar_requisicoes_interna(usuario),
    }


def _usuario_pode_ver_estoque(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not _usuario_modulo_visivel(usuario, "estoque"):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "estoque_geral_visualizar")


def _usuario_pode_movimentar_estoque(usuario: dict[str, Any] | None) -> bool:
    if not _usuario_pode_ver_estoque(usuario):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "estoque_geral_movimentar")


def _usuario_pode_pedidos_estoque(usuario: dict[str, Any] | None) -> bool:
    if _usuario_e_mecanico(usuario):
        return False
    if not _usuario_modulo_visivel(usuario, "estoque"):
        return False
    if not usuario or not _usuario_acesso_restrito(usuario):
        return True
    return _usuario_tem_permissao(usuario, "estoque_geral_pedidos")


def _usuario_pode_cadastrar_peca_via_estoque(usuario: dict[str, Any] | None) -> bool:
    return (
        _usuario_pode_movimentar_estoque(usuario)
        or _usuario_tem_permissao(usuario, "cadastros_pecas_criar")
    )


def _usuario_pode_editar_peca_via_estoque(usuario: dict[str, Any] | None) -> bool:
    return (
        _usuario_pode_movimentar_estoque(usuario)
        or _usuario_tem_permissao(usuario, "cadastros_pecas_editar")
    )


def _permissoes_payload_estoque(usuario: dict[str, Any] | None) -> dict[str, bool]:
    return {
        "pode_visualizar": _usuario_pode_ver_estoque(usuario),
        "pode_movimentar": _usuario_pode_movimentar_estoque(usuario),
        "pode_pedidos": _usuario_pode_pedidos_estoque(usuario),
        "pode_criar_peca": _usuario_pode_cadastrar_peca_via_estoque(usuario),
        "pode_editar_peca": _usuario_pode_editar_peca_via_estoque(usuario),
    }


def _negar_sem_permissao_estoque_visualizar(
    usuario: dict[str, Any] | None,
) -> tuple[Any, int] | None:
    negado = _negar_sem_modulo(usuario, "estoque")
    if negado:
        return negado
    if _usuario_pode_ver_estoque(usuario):
        return None
    return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403


def _negar_sem_permissao_estoque_movimentar(
    usuario: dict[str, Any] | None,
) -> tuple[Any, int] | None:
    negado = _negar_sem_permissao_estoque_visualizar(usuario)
    if negado:
        return negado
    if _usuario_pode_movimentar_estoque(usuario):
        return None
    return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403


def _negar_sem_permissao_estoque_pedidos(
    usuario: dict[str, Any] | None,
) -> tuple[Any, int] | None:
    negado = _negar_sem_modulo(usuario, "estoque")
    if negado:
        return negado
    if _usuario_pode_pedidos_estoque(usuario):
        return None
    return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403


def _enriquecer_info_lista_os(
    conn: sqlite3.Connection,
    dados_json: str | None,
) -> dict[str, Any]:
    info = extrair_info_lista_os(dados_json)
    marcadores = mapa_marcadores(carregar_marcadores_lista(conn))
    mid = info["marcador_lista_os"]
    meta = marcadores.get(mid) if mid else None
    return {
        **info,
        "marcador_rotulo": (meta or {}).get("rotulo") or "",
        "marcador_cor": (meta or {}).get("cor") or "",
    }


def _usuario_pode_editar_os(usuario: dict[str, Any] | None, mecanico_id: int | None) -> bool:
    if _usuario_pode_ver_todas_os(usuario):
        return True
    if not usuario or mecanico_id is None:
        return False
    try:
        return int(usuario.get("id") or 0) == int(mecanico_id)
    except (TypeError, ValueError):
        return False


def _mecanico_bloqueado_por_pausa(
    usuario: dict[str, Any] | None,
    status: str | None,
    mecanico_id: int | None,
) -> bool:
    if not _usuario_e_mecanico(usuario) or not os_status_em_pausa(status):
        return False
    if mecanico_id is None:
        return False
    try:
        return int(usuario.get("id") or 0) == int(mecanico_id)
    except (TypeError, ValueError):
        return False


def _row_para_item_os_perfil(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    visao_requisicao: str,
) -> dict[str, Any]:
    resumo = _resumo_os_de_dados_json(row["dados_json"])
    req_resumo = resumo_requisicoes_por_os(
        conn, int(row["numero_os"]), visao=visao_requisicao
    )
    status = row["status"] or "aberto"
    st_exib = resolver_status_exibicao_lista_os(
        conn,
        numero_os=int(row["numero_os"]),
        status_os=status,
        mecanico_id=row["mecanico_id"],
        dados_json=row["dados_json"],
    )
    item: dict[str, Any] = {
        "numero_os": row["numero_os"],
        "cliente_nome": row["cliente_nome"] or "",
        "status": status,
        "status_exibicao": st_exib,
        "embarcacao_nome": resumo["embarcacao_nome"],
        "entregue_por": resumo["entregue_por"],
        "motor": resumo["motor"],
        "data_entrada": row["data_entrada"] or "",
        "atualizado_em": row["atualizado_em"] or "",
        "mecanico_nome": row["mecanico_nome"] or "",
        "em_pausa": os_status_em_pausa(status, conn=conn),
    }
    info_lista = _enriquecer_info_lista_os(conn, row["dados_json"])
    item.update(info_lista)
    if req_resumo:
        item["requisicao"] = req_resumo
    if visao_requisicao == "mecanico":
        try:
            item["pre_requisicao"] = status_pre_requisicao(
                conn,
                int(row["numero_os"]),
                mecanico_id=int(row["mecanico_id"] or 0),
            )
        except sqlite3.Error:
            item["pre_requisicao"] = {
                "pode_abrir_requisicao": True,
                "pendencias": [],
            }
    return item


def _normalizar_perfil(perfil: str) -> str:
    perfil_norm = (perfil or "operador").strip().lower()
    if perfil_norm not in _PERFIS_VALIDOS:
        raise ValueError("Perfil inválido. Use admin, atendente, mecanico ou operador.")
    return perfil_norm


def _mecanico_modulo_os_padrao_ativo() -> bool:
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return True
    try:
        with conexao_principal() as conn:
            cfg = _obter_app_os_config(conn)
        return bool(cfg.get("mecanico_modulo_os_padrao", True))
    except sqlite3.Error:
        return True


def _mecanico_modulo_os_visivel(usuario: dict[str, Any] | None) -> bool:
    if not usuario or not _usuario_e_mecanico(usuario):
        return True
    override = usuario.get("modulo_os_visivel")
    if override is not None:
        return bool(override)
    return _mecanico_modulo_os_padrao_ativo()


def _mecanico_pode_criar_os(usuario: dict[str, Any] | None) -> bool:
    if not usuario or not _usuario_e_mecanico(usuario):
        return False
    if not _mecanico_modulo_os_visivel(usuario):
        return False
    return bool(usuario.get("permissao_criar_os"))


def _mecanico_pode_editar_os_existente(usuario: dict[str, Any] | None) -> bool:
    if not usuario or not _usuario_e_mecanico(usuario):
        return False
    if not _mecanico_modulo_os_visivel(usuario):
        return False
    return bool(usuario.get("permissao_editar_os"))


def _mecanico_modulo_os_completo(usuario: dict[str, Any] | None) -> bool:
    return _mecanico_pode_criar_os(usuario) or _mecanico_pode_editar_os_existente(usuario)


def _filtrar_dados_os_resumo_mecanico(dados: dict[str, Any]) -> dict[str, Any]:
    """Mecânico sem permissão de edição: só resumo ao abrir O.S. existente."""
    resumo = {chave: dados.get(chave, "") for chave in _CAMPOS_RESUMO_ABRIR_MECANICO}
    if dados.get("numero_os") is not None:
        resumo["numero_os"] = dados["numero_os"]
    return resumo


def _validar_senha_usuario_logado(
    usuario: dict[str, Any] | None,
    senha: str,
) -> tuple[bool, str]:
    if not usuario:
        return False, "Faça login."
    if not str(senha or "").strip():
        return False, "Informe sua senha para confirmar."
    login = str(usuario.get("usuario") or "").strip()
    try:
        with conexao_principal() as conn_pr:
            _init_usuarios(conn_pr)
            if not _autenticar_usuario(conn_pr, login, senha):
                return False, "Senha incorreta."
    except sqlite3.Error as exc:
        return False, str(exc)
    return True, ""


def _usuario_pode_copiar_os(usuario: dict[str, Any] | None) -> bool:
    if not usuario:
        return False
    if _usuario_acesso_restrito(usuario):
        return _usuario_pode_copiar_retorno_lista(usuario)
    if _usuario_pode_atribuir_mecanico(usuario):
        return True
    return _mecanico_pode_criar_os(usuario)


def _usuario_pode_acoes_responsavel_lista_os(usuario: dict[str, Any] | None) -> bool:
    """Qualquer ação na lista além de só visualizar."""
    return _usuario_pode_editar_info_lista_os(usuario)


def _pode_devolver_os_ao_mecanico(
    status: str | None,
    mecanico_id: int | None,
    usuario: dict[str, Any] | None,
) -> bool:
    if not _usuario_pode_retomar_lista_os(usuario) or not mecanico_id:
        return False
    return str(status or "").strip() in ("pronto_mecanico", "cliente_avisado")


def _dados_os_para_retorno(
    dados: dict[str, Any],
    *,
    numero_os_origem: int,
    nome_atendente: str | None = None,
) -> dict[str, Any]:
    """Copia cliente e motor/embarcação para nova O.S. (retorno do cliente)."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    novo: dict[str, Any] = {
        "data_entrada": hoje,
        "os_retorno_de": numero_os_origem,
    }
    if nome_atendente:
        novo["nome_atendente"] = nome_atendente
    for chave, valor in dados.items():
        if chave.startswith("cliente_"):
            novo[chave] = valor
        elif chave in _CAMPOS_COPIA_RETORNO_OS:
            novo[chave] = valor
    return novo


def _mecanico_pode_editar_os_modulo(usuario: dict[str, Any] | None) -> bool:
    return _mecanico_modulo_os_completo(usuario)


def _permissoes_formulario_os(usuario: dict[str, Any] | None) -> dict[str, Any]:
    if not usuario:
        return {
            "perfil": "",
            "pode_editar_tudo": True,
            "pode_atribuir_mecanico": True,
            "modulo_os_visivel": True,
            "pode_criar_os": True,
            "pode_editar_os_existente": True,
            "modulo_os_completo": True,
            "pode_editar_os_modulo": True,
            "campos_editaveis": None,
            "pode_telespectar": False,
            "deve_ser_rastreado": False,
            "controle_abas_ativo": False,
            "modulos_visiveis": {k: True for k in MAPA_MODULO_PREFIXOS},
            "permissoes_granulares": permissoes_granulares_vazias(),
        }
    if _usuario_e_mecanico(usuario):
        gran_efetivas = _permissoes_efetivas_usuario(usuario)
        modulos_mec = modulos_visiveis_de_permissoes(gran_efetivas)
        gran_efetivas, modulos_mec = _ajustar_pre_orcamentos_sessao(
            usuario, gran_efetivas, modulos_mec
        )
        modulo_visivel = bool(gran_efetivas.get("ordem_os_geral_visualizar"))
        pode_criar = bool(gran_efetivas.get("ordem_os_geral_criar"))
        pode_editar_existente = bool(gran_efetivas.get("ordem_os_geral_editar"))
        modulo_completo = pode_editar_existente
        return {
            "perfil": "mecanico",
            "modelo_base": "mecanico",
            "pode_editar_tudo": False,
            "pode_atribuir_mecanico": False,
            "modulo_os_visivel": modulo_visivel,
            "pode_criar_os": pode_criar,
            "pode_editar_os_existente": pode_editar_existente,
            "modulo_os_completo": modulo_completo,
            "pode_editar_os_modulo": modulo_completo,
            "campos_editaveis": None if modulo_completo else [],
            "pode_telespectar": _usuario_pode_telespectar_app(usuario),
            "deve_ser_rastreado": usuario_deve_ser_rastreado(usuario),
            "controle_abas_ativo": True,
            "modulos_visiveis": modulos_mec,
            "permissoes_granulares": gran_efetivas,
        }
    modelo_base = _modelo_base_usuario(usuario)
    controle_abas = _config_bool(
        usuario.get("controle_abas_ativo"),
        padrao=modelo_base != "admin",
    )
    gran_efetivas = _permissoes_efetivas_usuario(usuario)
    modulos = modulos_visiveis_de_permissoes(gran_efetivas)
    if _usuario_e_admin(usuario):
        modulos = {k: True for k in MAPA_MODULO_PREFIXOS}
    else:
        gran_efetivas, modulos = _ajustar_pre_orcamentos_sessao(
            usuario, gran_efetivas, modulos
        )
    pode_editar = bool(gran_efetivas.get("ordem_os_geral_editar"))
    pode_criar_os = bool(gran_efetivas.get("ordem_os_geral_criar"))
    return {
        "perfil": _perfil_usuario(usuario),
        "pode_editar_tudo": pode_editar,
        "pode_atribuir_mecanico": _usuario_pode_atribuir_mecanico(usuario),
        "modulo_os_visivel": modulos.get("ordem", False),
        "pode_criar_os": pode_criar_os,
        "pode_editar_os_existente": pode_editar,
        "modulo_os_completo": pode_editar,
        "pode_editar_os_modulo": pode_editar,
        "campos_editaveis": None,
        "pode_telespectar": _usuario_pode_telespectar_app(usuario),
        "deve_ser_rastreado": usuario_deve_ser_rastreado(usuario),
        "controle_abas_ativo": controle_abas,
        "modulos_visiveis": modulos,
        "permissoes_granulares": gran_efetivas,
    }


def _resolver_mecanico_os(
    _conn: sqlite3.Connection,
    payload: dict[str, Any],
    *,
    usuario: dict[str, Any] | None,
    mecanico_atual_id: int | None = None,
    mecanico_atual_nome: str | None = None,
) -> tuple[int | None, str | None]:
    """Resolve mecânico pelo banco principal (usuários não ficam no banco de teste)."""
    if not _usuario_pode_atribuir_mecanico(usuario):
        return mecanico_atual_id, mecanico_atual_nome
    mecanico_id = payload.get("mecanico_id")
    if mecanico_id in ("", None):
        return mecanico_atual_id, mecanico_atual_nome
    try:
        mid = int(mecanico_id)
    except (TypeError, ValueError):
        raise ValueError("Mecânico atribuído inválido.") from None
    with conexao_principal() as conn_pr:
        _init_usuarios(conn_pr)
        row = conn_pr.execute(
            """
            SELECT id, nome_exibicao, perfil FROM usuarios
            WHERE id = ? AND ativo = 1
            """,
            (mid,),
        ).fetchone()
    if row is None:
        raise ValueError("Mecânico não encontrado.")
    if str(row["perfil"]) != "mecanico":
        raise ValueError("O usuário selecionado não é mecânico.")
    nome = (row["nome_exibicao"] or "").strip() or None
    return mid, nome


def _mesclar_payload_mecanico(
    payload_novo: dict[str, Any],
    dados_existentes: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(dados_existentes)
    for chave in _CAMPOS_MECANICO_EDITAVEIS:
        if chave not in payload_novo:
            continue
        if chave == "assinatura_tecnico":
            nova = _extrair_assinatura(payload_novo, chave)
            if nova:
                merged[chave] = nova
            continue
        merged[chave] = payload_novo[chave]
    merged["numero_os"] = payload_novo.get("numero_os") or dados_existentes.get("numero_os")
    return merged


def _payload_salvo_parcial_mecanico(payload: dict[str, Any]) -> bool:
    """Save do painel Diagnóstico no perfil — só campos do mecânico + numero_os."""
    return set(payload.keys()).issubset(_CHAVES_PAYLOAD_PARCIAL_MECANICO)


def _preservar_assinaturas_colunas_payload(
    payload: dict[str, Any],
    row: sqlite3.Row,
    dados_existentes: dict[str, Any] | None = None,
) -> None:
    """Evita apagar assinaturas gravadas quando o save não envia imagem válida."""
    for chave_json, coluna in (
        ("assinatura_tecnico", "assinatura_tecnico"),
        ("assinatura_cliente", "assinatura_cliente"),
    ):
        nova = _extrair_assinatura(payload, chave_json)
        if nova:
            payload[chave_json] = nova
            continue
        val_col = row[coluna] if coluna in row.keys() else None
        if val_col and str(val_col).strip().startswith("data:image"):
            payload[chave_json] = str(val_col).strip()
            continue
        if dados_existentes:
            antiga = dados_existentes.get(chave_json)
            if isinstance(antiga, str) and antiga.startswith("data:image"):
                payload[chave_json] = antiga
                continue
        if chave_json in payload and not _extrair_assinatura(payload, chave_json):
            payload.pop(chave_json, None)


def _listar_usuarios(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
        SELECT {_COLUNAS_USUARIO_SELECT}, criado_em
        FROM usuarios
        ORDER BY perfil DESC, usuario COLLATE NOCASE
        """
    ).fetchall()
    saida: list[dict[str, Any]] = []
    for row in rows:
        usuario = _usuario_para_json(row)
        if usuario:
            saida.append(_enriquecer_usuario_perfil(conn, usuario))
    return saida


def _validar_granular_minimo(modelo: str, gran: dict[str, bool]) -> None:
    if _normalizar_perfil(modelo) == "admin":
        return
    if not any(gran.values()):
        raise ValueError("Marque ao menos uma permissão na árvore.")


def _resolver_perfil_payload(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
) -> tuple[str, int | None, dict[str, bool]]:
    perfil_id_raw = payload.get("perfil_id")
    if perfil_id_raw not in (None, ""):
        perfil = buscar_perfil_app_por_id(conn, int(perfil_id_raw))
        if perfil is None:
            raise ValueError("Perfil selecionado inválido.")
        modelo = str(perfil["modelo_base"])
        gran = normalizar_permissoes_granulares(
            payload.get("permissoes_granulares") or permissoes_do_perfil_app(perfil)
        )
        _validar_granular_minimo(modelo, gran)
        return modelo, int(perfil["id"]), gran
    modelo = _normalizar_perfil(str(payload.get("perfil") or "operador"))
    perfil = buscar_perfil_app_por_modelo(conn, modelo)
    gran = normalizar_permissoes_granulares(
        payload.get("permissoes_granulares") or permissoes_template_por_modelo(modelo)
    )
    _validar_granular_minimo(modelo, gran)
    return modelo, int(perfil["id"]) if perfil else None, gran


def _sincronizar_flags_mecanico_de_gran(
    gran: dict[str, bool],
) -> tuple[bool | None, bool, bool]:
    modulo_os = bool(gran.get("ordem_os_geral_visualizar"))
    criar = bool(gran.get("ordem_os_geral_criar"))
    editar = bool(gran.get("ordem_os_geral_editar"))
    return modulo_os, criar, editar


def _criar_usuario(
    conn: sqlite3.Connection,
    *,
    usuario: str,
    senha: str,
    nome_exibicao: str = "",
    perfil: str = "operador",
    permissao_financeiro: bool = False,
    permissao_config: bool = False,
) -> int:
    login = (usuario or "").strip()
    if not login:
        raise ValueError("Informe o login do usuário.")
    if not (senha or "").strip():
        raise ValueError("Informe a senha do usuário.")
    perfil_norm = _normalizar_perfil(perfil)
    if perfil_norm == "admin":
        permissao_financeiro = True
        permissao_config = True
    nome = (nome_exibicao or login).strip().upper()
    try:
        cur = conn.execute(
            """
            INSERT INTO usuarios (
                usuario, senha, nome_exibicao, perfil,
                permissao_financeiro, permissao_config, ativo
            ) VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (
                login,
                senha.strip(),
                nome,
                perfil_norm,
                _config_bool_para_int(permissao_financeiro, padrao=False),
                _config_bool_para_int(permissao_config, padrao=False),
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError(f'Já existe um usuário com o login "{login}".') from exc
    return int(cur.lastrowid)


def _excluir_usuario(
    conn: sqlite3.Connection,
    usuario_id: int,
    *,
    usuario_logado_id: int | None = None,
) -> None:
    uid = int(usuario_id)
    if usuario_logado_id is not None and uid == int(usuario_logado_id):
        raise ValueError("Você não pode excluir o usuário logado no momento.")
    row = conn.execute(
        "SELECT id, perfil FROM usuarios WHERE id = ?",
        (uid,),
    ).fetchone()
    if row is None:
        raise ValueError("Usuário não encontrado.")
    if str(row["perfil"]) == "admin":
        n_admin = conn.execute(
            "SELECT COUNT(*) FROM usuarios WHERE perfil = 'admin' AND ativo = 1"
        ).fetchone()[0]
        if int(n_admin) <= 1:
            raise ValueError("Não é possível excluir o único administrador ativo.")
    conn.execute("DELETE FROM usuarios WHERE id = ?", (uid,))


def _buscar_usuario_por_id_admin(conn: sqlite3.Connection, usuario_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        f"""
        SELECT {_COLUNAS_USUARIO_SELECT}, criado_em
        FROM usuarios
        WHERE id = ?
        """,
        (int(usuario_id),),
    ).fetchone()
    if row is None:
        return None
    usuario = _usuario_para_json(row)
    return _enriquecer_usuario_perfil(conn, usuario)


def _aplicar_dados_perfil_usuario(
    conn: sqlite3.Connection,
    usuario_id: int,
    payload: dict[str, Any],
) -> str:
    modelo, perfil_id, gran = _resolver_perfil_payload(conn, payload)
    modulo_os, criar_os, editar_os = _sincronizar_flags_mecanico_de_gran(gran)
    _atualizar_usuario(
        conn,
        usuario_id,
        perfil=modelo,
        perfil_id=perfil_id,
        controle_abas_ativo=modelo != "admin",
        permissoes_granulares=gran if modelo != "admin" else permissoes_granulares_vazias(),
        modulo_os_visivel=modulo_os if modelo == "mecanico" else None,
        permissao_criar_os=criar_os if modelo == "mecanico" else None,
        permissao_editar_os=editar_os if modelo == "mecanico" else None,
    )
    return modelo


def _atualizar_usuario(
    conn: sqlite3.Connection,
    usuario_id: int,
    *,
    senha: str | None = None,
    nome_exibicao: str | None = None,
    usuario_login: str | None = None,
    perfil: str | None = None,
    perfil_id: int | None = None,
    permissao_financeiro: bool | None = None,
    permissao_config: bool | None = None,
    ativo: bool | None = None,
    modulo_os_visivel: bool | None = None,
    usar_modulo_os_padrao: bool | None = None,
    permissao_criar_os: bool | None = None,
    permissao_editar_os: bool | None = None,
    permissao_telespectador: bool | None = None,
    telespectador_alvos: list[int] | None = None,
    permissao_sandbox_treinamento: bool | None = None,
    controle_abas_ativo: bool | None = None,
    permissoes_granulares: dict[str, bool] | None = None,
) -> None:
    uid = int(usuario_id)
    row = conn.execute(
        "SELECT id, perfil FROM usuarios WHERE id = ?",
        (uid,),
    ).fetchone()
    if row is None:
        raise ValueError("Usuário não encontrado.")
    perfil_atual = str(row["perfil"])
    perfil_novo = _normalizar_perfil(perfil) if perfil is not None else perfil_atual
    if perfil_atual == "admin" and perfil_novo != "admin":
        n_admin = conn.execute(
            "SELECT COUNT(*) FROM usuarios WHERE perfil = 'admin' AND ativo = 1"
        ).fetchone()[0]
        if int(n_admin) <= 1:
            raise ValueError("Não é possível remover o único administrador ativo.")
    fin = permissao_financeiro
    cfg = permissao_config
    if perfil_novo == "admin":
        fin = True
        cfg = True
    campos: list[str] = []
    valores: list[Any] = []
    if nome_exibicao is not None:
        campos.append("nome_exibicao = ?")
        valores.append((nome_exibicao or "").strip().upper())
    if usuario_login is not None:
        login = (usuario_login or "").strip()
        if not login:
            raise ValueError("Informe o login do usuário.")
        duplicado = conn.execute(
            "SELECT id FROM usuarios WHERE usuario = ? COLLATE NOCASE AND id != ?",
            (login, uid),
        ).fetchone()
        if duplicado is not None:
            raise ValueError(f'Já existe um usuário com o login "{login}".')
        campos.append("usuario = ?")
        valores.append(login)
    if perfil is not None:
        campos.append("perfil = ?")
        valores.append(perfil_novo)
        if perfil_novo == "admin":
            campos.append("controle_abas_ativo = ?")
            valores.append(0)
            campos.append("permissoes_granulares = ?")
            valores.append(serializar_permissoes_granulares(None))
        else:
            campos.append("controle_abas_ativo = ?")
            valores.append(1)
    if perfil_id is not None:
        campos.append("perfil_id = ?")
        valores.append(int(perfil_id) if perfil_id else None)
    if fin is not None:
        campos.append("permissao_financeiro = ?")
        valores.append(_config_bool_para_int(fin, padrao=False))
    if cfg is not None:
        campos.append("permissao_config = ?")
        valores.append(_config_bool_para_int(cfg, padrao=False))
    if ativo is not None:
        if perfil_atual == "admin" and not ativo:
            n_admin = conn.execute(
                "SELECT COUNT(*) FROM usuarios WHERE perfil = 'admin' AND ativo = 1"
            ).fetchone()[0]
            if int(n_admin) <= 1:
                raise ValueError("Não é possível desativar o único administrador ativo.")
        campos.append("ativo = ?")
        valores.append(_config_bool_para_int(ativo, padrao=True))
    if senha is not None and str(senha).strip():
        campos.append("senha = ?")
        valores.append(str(senha).strip())
    if usar_modulo_os_padrao:
        campos.append("modulo_os_visivel = ?")
        valores.append(None)
    elif modulo_os_visivel is not None:
        campos.append("modulo_os_visivel = ?")
        valores.append(_config_bool_para_int(modulo_os_visivel, padrao=True))
    if permissao_criar_os is not None:
        campos.append("permissao_criar_os = ?")
        valores.append(_config_bool_para_int(permissao_criar_os, padrao=False))
    if permissao_editar_os is not None:
        campos.append("permissao_editar_os = ?")
        valores.append(_config_bool_para_int(permissao_editar_os, padrao=False))
    if permissao_telespectador is not None:
        campos.append("permissao_telespectador = ?")
        valores.append(_config_bool_para_int(permissao_telespectador, padrao=False))
    if telespectador_alvos is not None:
        campos.append("telespectador_alvos_json = ?")
        if telespectador_alvos:
            valores.append(json.dumps([int(x) for x in telespectador_alvos], ensure_ascii=False))
        else:
            valores.append(None)
    if permissao_sandbox_treinamento is not None:
        campos.append("permissao_sandbox_treinamento = ?")
        valores.append(_config_bool_para_int(permissao_sandbox_treinamento, padrao=False))
    if controle_abas_ativo is not None:
        campos.append("controle_abas_ativo = ?")
        valores.append(_config_bool_para_int(controle_abas_ativo, padrao=False))
    if permissoes_granulares is not None:
        campos.append("permissoes_granulares = ?")
        valores.append(serializar_permissoes_granulares(permissoes_granulares))
    if not campos:
        return
    valores.append(uid)
    conn.execute(
        f"UPDATE usuarios SET {', '.join(campos)} WHERE id = ?",
        valores,
    )


def _telespectador_alvos_de_payload(payload: dict[str, Any]) -> list[int] | None:
    if "telespectador_alvos" not in payload:
        return None
    raw = payload.get("telespectador_alvos")
    if raw in (None, "", []):
        return []
    if not isinstance(raw, list):
        return []
    saida: list[int] = []
    for item in raw:
        try:
            saida.append(int(item))
        except (TypeError, ValueError):
            continue
    return saida


def _aplicar_telespectador_usuario(
    conn: sqlite3.Connection,
    usuario_id: int,
    payload: dict[str, Any],
) -> None:
    if "permissao_telespectador" not in payload and "telespectador_alvos" not in payload:
        return
    _atualizar_usuario(
        conn,
        int(usuario_id),
        permissao_telespectador=_config_bool(payload.get("permissao_telespectador"), padrao=False)
        if "permissao_telespectador" in payload
        else None,
        telespectador_alvos=_telespectador_alvos_de_payload(payload),
    )


def _request_quer_json() -> bool:
    if request.path.startswith("/api/"):
        return True
    accept = (request.headers.get("Accept") or "").lower()
    return "application/json" in accept


def _rota_publica(path: str) -> bool:
    if path in ("/login", "/api/versao"):
        return True
    if path.startswith("/api/login") or path.startswith("/api/auth/"):
        return True
    if path.startswith("/assinar/") and path != "/assinar/":
        return True
    if path.startswith("/api/assinatura/"):
        resto = path[len("/api/assinatura/"):]
        if resto and "/" not in resto and resto not in ("sessao", "config"):
            return True
    return False


@app.before_request
def _verificar_autenticacao():
    _aplicar_config_cookie_sessao_segura()
    if request.method == "OPTIONS":
        return None
    path = request.path or "/"
    if _rota_publica(path):
        return None
    if not _exigir_login_efetivo():
        return None
    if _usuario_logado():
        return None
    if _request_quer_json():
        return jsonify({
            "sucesso": False,
            "requer_login": True,
            "mensagem": "Faça login para continuar.",
        }), 401
    if path != "/login":
        destino = request.full_path if request.query_string else request.path
        if destino.endswith("?"):
            destino = destino[:-1]
        return redirect(url_for("pagina_login", next=destino))
    return None


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    if request.args.get("sair") in ("1", "true", "sim", "yes"):
        _limpar_sessao_autenticacao()
        return redirect(url_for("index"))
    pdf_orientacao = _orientacao_pdf_padrao()
    try:
        with conexao_principal() as conn:
            pdf_orientacao = _obter_orientacao_pdf_config(conn)
    except sqlite3.Error:
        pass
    return render_template(
        "index.html",
        app_version=APP_VERSION,
        usuario_atual=_usuario_logado(),
        exigir_login=_exigir_login_efetivo(),
        pdf_orientacao=pdf_orientacao,
    )


@app.route("/login")
def pagina_login():
    if request.args.get("trocar") in ("1", "true", "sim", "yes"):
        _limpar_sessao_autenticacao()
    elif request.args.get("sair") in ("1", "true", "sim", "yes"):
        _limpar_sessao_autenticacao()
    elif _usuario_logado():
        return redirect(url_for("index"))
    proximo = (request.args.get("next") or "/").strip()
    if not proximo.startswith("/"):
        proximo = "/"
    return render_template(
        "login.html",
        app_version=APP_VERSION,
        proximo=proximo,
    )


@app.route("/api/versao")
def api_versao():
    return jsonify({
        "versao": APP_VERSION,
        "recursos": [
            "busca_cliente_multipla",
            "motores_cliente",
            "salvar_cliente",
            "salvar_motor",
            "listar_os",
            "obter_os",
            "assinatura_remota",
            "gerar_pdf",
            "app_config",
            "autenticacao",
            "gerenciar_usuarios",
        ],
    })


@app.route("/api/auth/status")
def api_auth_status():
    usuario = _usuario_logado()
    exigir = _exigir_login_efetivo()
    pdf_orientacao = _orientacao_pdf_padrao()
    try:
        with conexao_principal() as conn:
            pdf_orientacao = _obter_orientacao_pdf_config(conn)
    except sqlite3.Error:
        pass
    return jsonify({
        "sucesso": True,
        "exigir_login": exigir,
        "exigir_login_config": _exigir_login_ativo(),
        "acesso_internet_publica": _requisicao_via_internet_publica(),
        "autenticado": usuario is not None,
        "usuario": usuario,
        "pdf_orientacao": pdf_orientacao,
        **_flags_configuracao_sessao(usuario),
        "permissoes_os": _permissoes_formulario_os(usuario),
        "ambiente_teste": _ambiente_teste_ativo(),
        "pode_ambiente_teste": _usuario_pode_configurar_app(usuario),
        "sandbox_treinamento_ativo": _sandbox_treinamento_ativo_sessao(),
        "sandbox_treinamento_forcado_admin": _sandbox_treinamento_forcado_admin_sessao(),
        "pode_sandbox_treinamento": _usuario_pode_sandbox_treinamento(usuario),
        "sandbox_treinamento_liberado_todos": _sandbox_treinamento_liberado_todos(),
        "pode_configurar_sandbox_treinamento": _usuario_pode_configurar_app(usuario),
        "notificacoes_aparelho": mapa_eventos_ativos(),
        "telespectador_admin_ativo": _obter_cfg_telespectador()["telespectador_admin_ativo"],
        "telespectador_operadores_ativo": _obter_cfg_telespectador()["telespectador_operadores_ativo"],
        "telespectador_lista_ampliada_admin": _obter_cfg_telespectador()["telespectador_lista_ampliada_admin"],
        "pode_controle_perfis": _usuario_pode_controle_perfis(usuario),
        "controle_perfis_desbloqueado": (
            _controle_perfis_desbloqueado() if _usuario_pode_controle_perfis(usuario) else False
        ),
    })


@app.route("/api/login/preview")
def api_login_preview():
    login = (request.args.get("usuario") or "").strip()
    if not login:
        return jsonify({"sucesso": True, "nome_exibicao": ""})
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            usuario = _buscar_usuario_por_login(conn, login)
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500
    if not usuario:
        return jsonify({"sucesso": True, "nome_exibicao": ""})
    return jsonify({
        "sucesso": True,
        "nome_exibicao": usuario.get("nome_exibicao") or "",
    })


@app.route("/api/login", methods=["POST"])
def api_login():
    payload = request.get_json(silent=True) or {}
    login = (payload.get("usuario") or "").strip()
    senha = str(payload.get("senha") or "")
    if not login or not senha:
        return jsonify({
            "sucesso": False,
            "mensagem": "Informe usuário e senha.",
        }), 400
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            usuario = _autenticar_usuario(conn, login, senha)
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500
    if not usuario:
        return jsonify({
            "sucesso": False,
            "mensagem": "Usuário ou senha inválidos.",
        }), 401
    _limpar_sessao_autenticacao()
    session[_SESSAO_USUARIO_ID] = usuario["id"]
    session.permanent = True
    session.modified = True
    _sandbox_treinamento_ativo_sessao()
    _registrar_atividade_direta(
        usuario_id=int(usuario["id"]),
        usuario_login=str(usuario.get("usuario") or ""),
        nome_exibicao=str(usuario.get("nome_exibicao") or ""),
        categoria="Sistema",
        subcategoria="Login",
        detalhe="Entrada no O.S. Digital",
    )
    return jsonify({"sucesso": True, "usuario": usuario})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    _limpar_sessao_autenticacao(registrar_rastreio=True)
    return jsonify({"sucesso": True})


@app.route("/api/ambiente-teste", methods=["GET"])
def api_ambiente_teste_status():
    usuario = _usuario_logado()
    if not _usuario_pode_configurar_app(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    ativo = _ambiente_teste_ativo()
    resumo_prod: dict[str, Any] = {}
    resumo_teste: dict[str, Any] = {}
    try:
        if DATABASE_PRINCIPAL_PATH.is_file():
            with conexao_principal() as conn:
                iniciar_schema_banco_app(conn)
                resumo_prod = resumo_banco_app(conn)
        garantir_banco_teste(DATABASE_TESTE_PATH)
        with sqlite3.connect(DATABASE_TESTE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            iniciar_schema_banco_app(conn)
            conn.commit()
            resumo_teste = resumo_banco_app(conn)
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500
    return jsonify({
        "sucesso": True,
        "ativo": ativo,
        "caminho_teste": str(DATABASE_TESTE_PATH),
        "caminho_producao": str(DATABASE_PRINCIPAL_PATH),
        "resumo_producao": resumo_prod,
        "resumo_teste": resumo_teste,
    })


@app.route("/api/ambiente-teste", methods=["POST"])
def api_ambiente_teste_toggle():
    usuario = _usuario_logado()
    if not _usuario_pode_configurar_app(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    payload = request.get_json(silent=True) or {}
    ativo = _config_bool(payload.get("ativo"), padrao=False)
    if ativo:
        garantir_banco_teste(DATABASE_TESTE_PATH)
    try:
        with conexao_principal() as conn:
            _salvar_ambiente_teste_global(conn, ativo)
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500
    if ativo:
        mensagem = (
            "Ambiente de teste ativado para todo o app. "
            "Mecânicos, responsável e admin gravam O.S. e requisições no banco de teste."
        )
    else:
        mensagem = "Ambiente de produção restaurado para todos os usuários."
    return jsonify({
        "sucesso": True,
        "ativo": ativo,
        "mensagem": mensagem,
    })


@app.route("/api/ambiente-teste/limpar-producao", methods=["POST"])
def api_ambiente_teste_limpar_producao():
    """Remove O.S. e fluxos gravados no banco principal (dados de teste antigos)."""
    usuario = _usuario_logado()
    if not _usuario_pode_configurar_app(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco principal não encontrado."}), 500
    try:
        with conexao_principal() as conn:
            iniciar_schema_banco_app(conn)
            removidos = limpar_dados_app(conn)
        return jsonify({
            "sucesso": True,
            "mensagem": "Dados de O.S. / requisições removidos do banco principal.",
            "removidos": removidos,
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/ambiente-teste/reset", methods=["POST"])
def api_ambiente_teste_reset():
    """Zera o banco de teste (O.S., requisições, checklist, assinaturas)."""
    usuario = _usuario_logado()
    if not _usuario_pode_configurar_app(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    try:
        garantir_banco_teste(DATABASE_TESTE_PATH)
        with sqlite3.connect(DATABASE_TESTE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            iniciar_schema_banco_app(conn)
            removidos = limpar_dados_app(conn)
            conn.commit()
        return jsonify({
            "sucesso": True,
            "mensagem": "Ambiente de teste zerado.",
            "removidos": removidos,
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/sandbox-treinamento/status", methods=["GET"])
def api_sandbox_treinamento_status():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    return jsonify({
        "sucesso": True,
        "ativo": _sandbox_treinamento_ativo_sessao(),
        "forcado_admin": _sandbox_treinamento_forcado_admin_sessao(),
        "pode_usar": _usuario_pode_sandbox_treinamento(usuario),
        "liberado_todos": _sandbox_treinamento_liberado_todos(),
        "ambiente_teste_global": _ambiente_teste_ativo(),
        "caminho_sandbox": str(DATABASE_SANDBOX_TREINAMENTO_PATH),
    })


@app.route("/api/sandbox-treinamento/ativar", methods=["POST"])
def api_sandbox_treinamento_ativar():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if _ambiente_teste_ativo():
        return jsonify({
            "sucesso": False,
            "mensagem": (
                "O ambiente de teste global do administrador está ativo. "
                "Desative-o antes de usar o treinamento individual."
            ),
        }), 409
    if not _usuario_pode_sandbox_treinamento(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Seu perfil não tem permissão para o ambiente de treinamento.",
        }), 403
    try:
        garantir_banco_sandbox(DATABASE_SANDBOX_TREINAMENTO_PATH)
        _definir_sandbox_treinamento_sessao(True)
        with conexao_principal() as conn:
            init_sandbox_treinamento_tabelas(conn)
            registrar_sessao_ativa(conn, int(usuario["id"]), forcado_admin=False)
        return jsonify({
            "sucesso": True,
            "mensagem": (
                "Ambiente de treinamento ativo. O.S. e requisições gravam no banco "
                "de treinamento compartilhado; clientes e login continuam no banco principal."
            ),
            "ativo": True,
            "forcado_admin": _sandbox_treinamento_forcado_admin_sessao(),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/sandbox-treinamento/desativar", methods=["POST"])
def api_sandbox_treinamento_desativar():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if _sandbox_treinamento_forcado_admin_sessao() and not _usuario_pode_configurar_app(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": (
                "O treinamento foi ativado pelo administrador. "
                "Somente o admin pode desativá-lo."
            ),
        }), 403
    _definir_sandbox_treinamento_sessao(False)
    try:
        with conexao_principal() as conn:
            init_sandbox_treinamento_tabelas(conn)
            registrar_sessao_inativa(conn, int(usuario["id"]))
    except sqlite3.Error:
        pass
    return jsonify({
        "sucesso": True,
        "mensagem": "Ambiente de treinamento desativado. Voltando ao banco de produção.",
        "ativo": False,
    })


@app.route("/api/sandbox-treinamento/admin", methods=["GET"])
def api_sandbox_treinamento_admin():
    usuario = _usuario_logado()
    if not _usuario_pode_configurar_app(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    try:
        with conexao_principal() as conn:
            init_sandbox_treinamento_tabelas(conn)
            usuarios = listar_usuarios_sandbox_admin(conn)
            liberado_todos = ler_liberado_todos(conn)
        resumo = resumo_banco_sandbox(DATABASE_SANDBOX_TREINAMENTO_PATH)
        ativos = [u for u in usuarios if u.get("sandbox_ativo")]
        return jsonify({
            "sucesso": True,
            "liberado_todos": liberado_todos,
            "caminho_sandbox": str(DATABASE_SANDBOX_TREINAMENTO_PATH),
            "resumo_sandbox": resumo,
            "usuarios": usuarios,
            "usuarios_em_sandbox": ativos,
            "total_em_sandbox": len(ativos),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/sandbox-treinamento/usuarios/<int:usuario_id>", methods=["PUT"])
def api_sandbox_treinamento_usuario(usuario_id: int):
    usuario = _usuario_logado()
    if not _usuario_pode_configurar_app(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    payload = request.get_json(silent=True) or {}
    if "permissao_sandbox_treinamento" not in payload:
        return jsonify({"sucesso": False, "mensagem": "Campo permissao_sandbox_treinamento obrigatório."}), 400
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            _atualizar_usuario(
                conn,
                usuario_id,
                permissao_sandbox_treinamento=_config_bool(
                    payload["permissao_sandbox_treinamento"], padrao=False,
                ),
            )
            atualizado = _buscar_usuario_por_id_admin(conn, usuario_id)
        return jsonify({"sucesso": True, "usuario": atualizado})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/sandbox-treinamento/liberar-todos", methods=["POST"])
def api_sandbox_treinamento_liberar_todos():
    usuario = _usuario_logado()
    if not _usuario_pode_configurar_app(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    payload = request.get_json(silent=True) or {}
    ativo = _config_bool(payload.get("ativo"), padrao=False)
    try:
        with conexao_principal() as conn:
            init_sandbox_treinamento_tabelas(conn)
            salvar_liberado_todos(conn, ativo)
        return jsonify({
            "sucesso": True,
            "liberado_todos": ativo,
            "mensagem": (
                "Botão de treinamento liberado para todos os usuários."
                if ativo
                else "Liberação global do treinamento desativada."
            ),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/sandbox-treinamento/admin/ativar", methods=["POST"])
def api_sandbox_treinamento_admin_ativar():
    usuario = _usuario_logado()
    if not _usuario_pode_configurar_app(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    if _ambiente_teste_ativo():
        return jsonify({
            "sucesso": False,
            "mensagem": (
                "O ambiente de teste global está ativo. "
                "Desative-o antes de ativar o treinamento para os usuários."
            ),
        }), 409
    payload = request.get_json(silent=True) or {}
    todos = _config_bool(payload.get("todos"), padrao=False)
    try:
        garantir_banco_sandbox(DATABASE_SANDBOX_TREINAMENTO_PATH)
        with conexao_principal() as conn:
            init_sandbox_treinamento_tabelas(conn)
            if todos:
                total = ativar_sandbox_todos(conn, forcado_admin=True)
            else:
                ids_raw = payload.get("usuario_ids") or []
                if not isinstance(ids_raw, list) or not ids_raw:
                    return jsonify({
                        "sucesso": False,
                        "mensagem": "Informe usuario_ids ou todos=true.",
                    }), 400
                ids = []
                for item in ids_raw:
                    try:
                        ids.append(int(item))
                    except (TypeError, ValueError):
                        continue
                if not ids:
                    return jsonify({
                        "sucesso": False,
                        "mensagem": "Nenhum usuário válido informado.",
                    }), 400
                total = ativar_sandbox_usuarios(conn, ids, forcado_admin=True)
        return jsonify({
            "sucesso": True,
            "total": total,
            "mensagem": (
                f"Treinamento ativado para {total} usuário(s). "
                "Eles entrarão no modo treinamento automaticamente."
            ),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/sandbox-treinamento/admin/desativar", methods=["POST"])
def api_sandbox_treinamento_admin_desativar():
    usuario = _usuario_logado()
    if not _usuario_pode_configurar_app(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    payload = request.get_json(silent=True) or {}
    todos = _config_bool(payload.get("todos"), padrao=False)
    try:
        with conexao_principal() as conn:
            init_sandbox_treinamento_tabelas(conn)
            if todos:
                total = desativar_sandbox_todos(conn)
            else:
                ids_raw = payload.get("usuario_ids") or []
                if not isinstance(ids_raw, list) or not ids_raw:
                    return jsonify({
                        "sucesso": False,
                        "mensagem": "Informe usuario_ids ou todos=true.",
                    }), 400
                ids = []
                for item in ids_raw:
                    try:
                        ids.append(int(item))
                    except (TypeError, ValueError):
                        continue
                if not ids:
                    return jsonify({
                        "sucesso": False,
                        "mensagem": "Nenhum usuário válido informado.",
                    }), 400
                total = desativar_sandbox_usuarios(conn, ids)
        return jsonify({
            "sucesso": True,
            "total": total,
            "mensagem": f"Treinamento desativado para {total} usuário(s).",
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/sandbox-treinamento/limpar", methods=["POST"])
def api_sandbox_treinamento_limpar():
    usuario = _usuario_logado()
    if not _usuario_pode_configurar_app(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    try:
        removidos = limpar_banco_sandbox(DATABASE_SANDBOX_TREINAMENTO_PATH)
        with conexao_principal() as conn:
            init_sandbox_treinamento_tabelas(conn)
            conn.execute(
                "UPDATE sandbox_treinamento_sessao "
                "SET ativo = 0, ativado_em = NULL, forcado_admin = 0"
            )
        return jsonify({
            "sucesso": True,
            "mensagem": "Banco de treinamento zerado. Sessões de sandbox foram encerradas.",
            "removidos": removidos,
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/config", methods=["GET"])
def api_config_get():
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_configuracoes(usuario)
    if negado:
        return negado
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    usuario = _usuario_logado()
    try:
        with conexao_principal() as conn:
            cfg = _obter_app_os_config(conn)
            pdf_orientacao = _obter_orientacao_pdf_config(conn)
            exigir_login, sync_login = _exigir_login_para_config(conn)
            tem_logo = _obter_logo_empresa(conn) is not None
            cfg_fotos = carregar_fotos_os_config(conn)
            rastreio_terceiro = rastreio_controle_terceiro_ativo(conn)
        tel_cfg = _obter_cfg_telespectador()
        for chave in _TELESPECTADOR_CFG_KEYS:
            cfg[chave] = tel_cfg[chave]
        cfg["exigir_login"] = exigir_login
        return jsonify({
            "sucesso": True,
            **cfg,
            "rastreio_controle_terceiro_ativo": rastreio_terceiro,
            "tem_logo_empresa": tem_logo,
            "fotos_os_limites_personalizados": cfg_fotos.get("limites_personalizados"),
            "fotos_os_max_fotos_por_envio": cfg_fotos.get("max_fotos_por_envio"),
            "fotos_os_max_kb_por_foto": cfg_fotos.get("max_kb_por_foto"),
            "fotos_os_limites_efetivos": cfg_fotos.get("limites_efetivos"),
            "exigir_login_sincronizado_oficina": sync_login,
            "pdf_orientacao": pdf_orientacao,
            **_flags_configuracao_sessao(usuario),
            "permissoes": _permissoes_payload_configuracoes(usuario),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/config", methods=["POST"])
def api_config_post():
    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return jsonify({"sucesso": False, "mensagem": "Dados inválidos."}), 400
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    usuario = _usuario_logado()
    if ("exibir_tipo_os" in payload or "exigir_login" in payload
            or "mecanico_modulo_os_padrao" in payload
            or "interna_publicar_oficina" in payload
            or any(chave in payload for chave in _TELESPECTADOR_CFG_KEYS)) and not _usuario_pode_configurar_app(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Apenas administradores podem alterar as configurações do app.",
        }), 403
    if "pdf_orientacao" in payload and not _usuario_pode_configurar_app(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Apenas administradores podem alterar a orientação do PDF.",
        }), 403
    if "exigir_login" in payload:
        with conexao_principal() as conn:
            if _exigir_login_sincronizado_oficina(conn):
                return jsonify({
                    "sucesso": False,
                    "mensagem": (
                        "O login do app está vinculado ao Sistema Oficina. "
                        "Altere em Controle de Usuários na oficina ou desative o vínculo "
                        "em Configurações → Integração O.S. Digital."
                    ),
                }), 403
        desligar = payload["exigir_login"] in (False, 0, "0", "false", "off", "nao", "não", "no")
        if desligar and (os.getenv("OS_PUBLIC_URL") or os.getenv("NGROK_DOMAIN")):
            return jsonify({
                "sucesso": False,
                "mensagem": (
                    "Com URL pública (ngrok) configurada, o login não pode ser desligado. "
                    "Remova OS_PUBLIC_URL/NGROK_DOMAIN do .env para usar acesso livre só na rede local."
                ),
            }), 400
    try:
        with conexao_principal() as conn:
            cfg = _salvar_app_os_config(conn, payload)
            pdf_orientacao = _obter_orientacao_pdf_config(conn)
            if "pdf_orientacao" in payload:
                pdf_orientacao = _salvar_orientacao_pdf_config(conn, payload["pdf_orientacao"])
            exigir_login, sync_login = _exigir_login_para_config(conn)
        tel_cfg = _obter_cfg_telespectador()
        for chave in _TELESPECTADOR_CFG_KEYS:
            cfg[chave] = tel_cfg[chave]
        cfg["exigir_login"] = exigir_login
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Alteração de configuração",
            "Configurações gerais do app",
        )
        return jsonify({
            "sucesso": True,
            **cfg,
            "exigir_login_sincronizado_oficina": sync_login,
            "pdf_orientacao": pdf_orientacao,
            **_flags_configuracao_sessao(usuario),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/config/fotos-os", methods=["GET"])
def api_config_fotos_os_get():
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        with conexao_principal() as conn:
            cfg = carregar_fotos_os_config(conn)
        return jsonify({
            "sucesso": True,
            **cfg,
            "pode_editar": _usuario_pode_configurar_app(_usuario_logado()),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/config/fotos-os", methods=["PUT"])
def api_config_fotos_os_put():
    usuario = _usuario_logado()
    if not _usuario_pode_configurar_app(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Apenas administradores podem alterar esta configuração.",
        }), 403
    payload = request.get_json(silent=True) or {}
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    alteracoes: dict[str, Any] = {}
    for chave in ("limites_personalizados", "max_fotos_por_envio", "max_kb_por_foto", "ativo"):
        if chave in payload:
            alteracoes[chave] = payload[chave]
    try:
        with conexao_principal() as conn:
            resultado = salvar_fotos_os_config(conn, alteracoes=alteracoes)
            conn.commit()
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Alterar config. fotos O.S.",
            f"{len(alteracoes)} campo(s)",
        )
        return jsonify({"sucesso": True, **resultado})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/config/logo-empresa", methods=["POST"])
def api_config_logo_empresa():
    usuario = _usuario_logado()
    if not _usuario_pode_configurar_app(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Apenas administradores podem alterar a logo.",
        }), 403
    payload = request.get_json(silent=True) or {}
    logo = payload.get("logo")
    remover = payload.get("remover") in (True, 1, "1", "true", "sim")
    try:
        with conexao_principal() as conn:
            if remover:
                _salvar_logo_empresa(conn, None)
            else:
                _salvar_logo_empresa(conn, str(logo or ""))
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Remover logo da empresa" if remover else "Alterar logo da empresa",
            "PDFs da oficina",
        )
        return jsonify({
            "sucesso": True,
            "mensagem": "Logo removida." if remover else "Logo salva.",
            "tem_logo_empresa": not remover,
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/config/lista-os", methods=["GET"])
def api_config_lista_os_get():
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        with conexao_principal() as conn:
            marcadores = carregar_marcadores_lista(conn)
            pausas = carregar_pausas_tipos(conn)
        return jsonify({
            "sucesso": True,
            "marcadores": marcadores,
            "pausas": pausas,
            "pode_editar": _usuario_pode_configurar_app(_usuario_logado()),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/config/nav-pos-acao", methods=["GET"])
def api_config_nav_pos_acao_get():
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        with conexao_principal() as conn:
            cfg = carregar_nav_pos_acao(conn)
        usuario = _usuario_logado()
        return jsonify({
            "sucesso": True,
            **cfg,
            "pode_editar": _usuario_pode_configurar_app(usuario),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/config/nav-pos-acao", methods=["PUT"])
def api_config_nav_pos_acao_put():
    usuario = _usuario_logado()
    if not _usuario_pode_configurar_app(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Apenas administradores podem alterar esta configuração.",
        }), 403
    payload = request.get_json(silent=True) or {}
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    alteracoes = payload.get("itens") if isinstance(payload.get("itens"), dict) else payload
    if not isinstance(alteracoes, dict):
        alteracoes = {}
    try:
        with conexao_principal() as conn:
            resultado = salvar_nav_pos_acao(conn, alteracoes=alteracoes)
            conn.commit()
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Alterar navegação automática",
            f"{len(alteracoes)} regra(s)",
        )
        return jsonify({"sucesso": True, **resultado})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/config/notificacoes-aparelho", methods=["GET"])
def api_config_notificacoes_aparelho_get():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if not _usuario_pode_ver_notificacoes_aparelho_config(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    try:
        with conexao_principal() as conn:
            cfg = carregar_notificacoes_aparelho(conn)
        return jsonify({
            "sucesso": True,
            **cfg,
            "pode_editar": _usuario_pode_editar_notificacoes_aparelho_config(usuario),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/config/notificacoes-aparelho", methods=["PUT"])
def api_config_notificacoes_aparelho_put():
    usuario = _usuario_logado()
    if not _usuario_pode_editar_notificacoes_aparelho_config(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Sem permissão para alterar notificações do aparelho.",
        }), 403
    payload = request.get_json(silent=True) or {}
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    alteracoes = payload.get("itens") if isinstance(payload.get("itens"), dict) else payload
    if not isinstance(alteracoes, dict):
        alteracoes = {}
    try:
        with conexao_principal() as conn:
            resultado = salvar_notificacoes_aparelho(conn, alteracoes=alteracoes)
            conn.commit()
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Alterar notificações no aparelho",
            f"{len(alteracoes)} evento(s)",
        )
        return jsonify({"sucesso": True, **resultado})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/config/lista-os", methods=["PUT"])
def api_config_lista_os_put():
    usuario = _usuario_logado()
    if not _usuario_pode_configurar_app(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Apenas administradores podem alterar esta configuração.",
        }), 403
    payload = request.get_json(silent=True) or {}
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        with conexao_principal() as conn:
            resultado = salvar_personalizacao_lista_os(
                conn,
                marcadores=payload.get("marcadores") if "marcadores" in payload else None,
                pausas=payload.get("pausas") if "pausas" in payload else None,
            )
            conn.commit()
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Alterar personalização lista O.S.",
            "Marcadores e pausas",
        )
        return jsonify({"sucesso": True, **resultado})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/info-lista", methods=["POST"])
def api_os_info_lista(numero_os: int):
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "lista")
    if negado:
        return negado
    if not _usuario_pode_editar_info_lista_os(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Sem permissão para alterar informações da lista.",
        }), 403
    payload = request.get_json(silent=True) or {}
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            row = conn.execute(
                "SELECT dados_json FROM ordens_servico WHERE numero_os = ?",
                (int(numero_os),),
            ).fetchone()
            if row is None:
                return jsonify({"sucesso": False, "mensagem": "O.S. não encontrada."}), 404
            marcador_id = payload.get("marcador_id") if "marcador_id" in payload else None
            obs = payload.get("obs") if "obs" in payload else None
            if marcador_id is not None:
                mid = str(marcador_id or "").strip()
                if mid:
                    mapa = mapa_marcadores(carregar_marcadores_lista(conn))
                    if mid not in mapa:
                        return jsonify({
                            "sucesso": False,
                            "mensagem": "Marcador inválido ou não configurado.",
                        }), 400
            novo_json = aplicar_info_lista_os_payload(
                row["dados_json"],
                marcador_id=marcador_id,
                obs=obs,
            )
            conn.execute(
                """
                UPDATE ordens_servico SET dados_json = ?, atualizado_em = datetime('now', 'localtime')
                WHERE numero_os = ?
                """,
                (novo_json, int(numero_os)),
            )
            info = _enriquecer_info_lista_os(conn, novo_json)
        _registrar_acao_rastreio(
            usuario,
            "Lista de O.S.",
            "Alterar info da lista",
            f"O.S. nº {numero_os}",
        )
        return jsonify({"sucesso": True, "numero_os": numero_os, **info})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/perfil", methods=["PUT"])
def api_atualizar_meu_perfil():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login para editar seu perfil."}), 401
    if not _usuario_pode_editar_proprio_perfil(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    payload = request.get_json(silent=True) or {}
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            _atualizar_usuario(
                conn,
                int(usuario["id"]),
                senha=str(payload["senha"]).strip() if payload.get("senha") else None,
                nome_exibicao=str(payload["nome_exibicao"]).strip()
                if payload.get("nome_exibicao") is not None
                else None,
            )
            atualizado = _buscar_usuario_por_id(conn, int(usuario["id"]))
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Alterar meu perfil",
            str(atualizado.get("nome_exibicao") or atualizado.get("usuario") or ""),
        )
        return jsonify({
            "sucesso": True,
            "mensagem": "Perfil atualizado.",
            "usuario": atualizado,
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/permissoes/arvore", methods=["GET"])
def api_permissoes_arvore():
    usuario = _usuario_logado()
    if not _usuario_pode_gerenciar_usuarios(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    return jsonify({
        "sucesso": True,
        "arvore": arvore_permissoes_json(),
        "chaves": list(permissoes_granulares_vazias().keys()),
        "permissoes_padrao": permissoes_padrao_usuario_os(),
    })


@app.route("/api/perfis", methods=["GET"])
def api_perfis_listar():
    usuario = _usuario_logado()
    if not _usuario_pode_gerenciar_usuarios(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            perfis = listar_perfis_app(conn)
        return jsonify({"sucesso": True, "perfis": perfis})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/perfis", methods=["POST"])
def api_perfis_criar():
    usuario = _usuario_logado()
    if not _usuario_pode_editar_usuarios(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    payload = request.get_json(silent=True) or {}
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            novo_id = criar_perfil_app(
                conn,
                nome=str(payload.get("nome") or ""),
                modelo_base=str(payload.get("modelo_base") or "personalizado"),
                permissoes_granulares=payload.get("permissoes_granulares"),
            )
            conn.commit()
            criado = buscar_perfil_app_por_id(conn, novo_id)
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Criar perfil de permissões",
            str(criado.get("nome") or novo_id),
        )
        return jsonify({"sucesso": True, "perfil": criado})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/perfis/<int:perfil_id>", methods=["DELETE"])
def api_perfis_excluir(perfil_id: int):
    usuario = _usuario_logado()
    if not _usuario_pode_editar_usuarios(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            excluir_perfil_app(conn, perfil_id)
            conn.commit()
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Excluir perfil de permissões",
            f"Perfil #{perfil_id}",
        )
        return jsonify({"sucesso": True})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/usuarios", methods=["GET"])
def api_usuarios_listar():
    usuario = _usuario_logado()
    if not _usuario_pode_gerenciar_usuarios(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            lista = _listar_usuarios(conn)
        return jsonify({"sucesso": True, "usuarios": lista})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/usuarios", methods=["POST"])
def api_usuarios_criar():
    usuario = _usuario_logado()
    if not _usuario_pode_criar_usuarios(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    payload = request.get_json(silent=True) or {}
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            modelo, perfil_id, gran = _resolver_perfil_payload(conn, payload)
            if modelo == "admin" and not _usuario_e_admin(usuario):
                raise ValueError("Somente administradores podem criar usuários admin.")
            novo_id = _criar_usuario(
                conn,
                usuario=str(payload.get("usuario") or ""),
                senha=str(payload.get("senha") or ""),
                nome_exibicao=str(payload.get("nome_exibicao") or ""),
                perfil=modelo,
                permissao_financeiro=False,
                permissao_config=False,
            )
            _atualizar_usuario(
                conn,
                novo_id,
                perfil_id=perfil_id,
                controle_abas_ativo=modelo != "admin",
                permissoes_granulares=gran if modelo != "admin" else None,
            )
            if modelo == "mecanico":
                modulo_os, criar_os, editar_os = _sincronizar_flags_mecanico_de_gran(gran)
                _atualizar_usuario(
                    conn,
                    novo_id,
                    modulo_os_visivel=modulo_os,
                    permissao_criar_os=criar_os,
                    permissao_editar_os=editar_os,
                )
            _aplicar_telespectador_usuario(conn, novo_id, payload)
            conn.commit()
            criado = _buscar_usuario_por_id(conn, novo_id)
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Criação de usuário",
            str(criado.get("usuario") or criado.get("nome_exibicao") or novo_id),
        )
        return jsonify({"sucesso": True, "usuario": criado})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/usuarios/<int:usuario_id>", methods=["PUT"])
def api_usuarios_atualizar(usuario_id: int):
    usuario = _usuario_logado()
    if not _usuario_pode_editar_usuarios(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    payload = request.get_json(silent=True) or {}
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            if "perfil_id" in payload or "perfil" in payload or "permissoes_granulares" in payload:
                modelo = _aplicar_dados_perfil_usuario(conn, usuario_id, payload)
                if modelo == "admin" and not _usuario_e_admin(usuario):
                    raise ValueError("Somente administradores podem atribuir perfil admin.")
            _atualizar_usuario(
                conn,
                usuario_id,
                usuario_login=str(payload["usuario"]).strip()
                if payload.get("usuario") is not None
                else None,
                senha=str(payload["senha"]).strip() if payload.get("senha") else None,
                nome_exibicao=str(payload["nome_exibicao"]).strip()
                if payload.get("nome_exibicao") is not None
                else None,
                ativo=_config_bool(payload["ativo"], padrao=True)
                if "ativo" in payload
                else None,
                permissao_telespectador=_config_bool(payload["permissao_telespectador"], padrao=False)
                if "permissao_telespectador" in payload
                else None,
                telespectador_alvos=_telespectador_alvos_de_payload(payload),
                permissao_sandbox_treinamento=_config_bool(
                    payload["permissao_sandbox_treinamento"], padrao=False,
                )
                if "permissao_sandbox_treinamento" in payload
                else None,
            )
            conn.commit()
            atualizado = _buscar_usuario_por_id_admin(conn, usuario_id)
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Alteração de usuário",
            str(atualizado.get("usuario") or atualizado.get("nome_exibicao") or usuario_id),
        )
        return jsonify({"sucesso": True, "usuario": atualizado})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/usuarios/<int:usuario_id>", methods=["DELETE"])
def api_usuarios_excluir(usuario_id: int):
    usuario = _usuario_logado()
    if not _usuario_pode_excluir_usuarios(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            _excluir_usuario(
                conn,
                usuario_id,
                usuario_logado_id=int(usuario["id"]) if usuario else None,
            )
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Exclusão de usuário",
            f"ID {usuario_id}",
        )
        return jsonify({"sucesso": True})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/usuarios/rastreaveis", methods=["GET"])
def api_usuarios_rastreaveis():
    usuario = _usuario_logado()
    if not _usuario_pode_gerenciar_usuarios(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            lista = listar_usuarios_rastreaveis(conn)
        return jsonify({"sucesso": True, "usuarios": lista})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/presenca/atualizar", methods=["POST"])
def api_presenca_atualizar():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if not usuario_deve_ser_rastreado(usuario):
        return jsonify({"sucesso": True, "rastreado": False})
    payload = request.get_json(silent=True) or {}
    try:
        numero_os_raw = payload.get("numero_os")
        numero_os: int | None
        try:
            numero_os = int(numero_os_raw) if numero_os_raw not in (None, "", 0) else None
        except (TypeError, ValueError):
            numero_os = None
        perfil_obs_id = payload.get("perfil_observado_id")
        try:
            perfil_obs_id_int = int(perfil_obs_id) if perfil_obs_id not in (None, "", 0) else None
        except (TypeError, ValueError):
            perfil_obs_id_int = None
        with conexao_principal() as conn:
            _init_usuarios(conn)
            atualizar_presenca_usuario(
                conn,
                int(usuario["id"]),
                modulo=str(payload.get("modulo") or ""),
                aba=str(payload.get("aba") or ""),
                contexto=str(payload.get("contexto") or ""),
                detalhe=str(payload.get("detalhe") or ""),
                perfil_observado_id=perfil_obs_id_int,
                perfil_observado_nome=str(payload.get("perfil_observado_nome") or ""),
                numero_os=numero_os,
                sandbox_treinamento_ativo=_config_bool(
                    payload.get("sandbox_treinamento_ativo"), padrao=False,
                ) or _sandbox_treinamento_ativo_sessao(),
            )
        return jsonify({"sucesso": True, "rastreado": True})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/presenca/offline", methods=["POST"])
def api_presenca_offline():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if not usuario_deve_ser_rastreado(usuario):
        return jsonify({"sucesso": True, "rastreado": False})
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            remover_presenca_usuario(conn, int(usuario["id"]))
        return jsonify({"sucesso": True, "offline": True})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/presenca/monitor", methods=["GET"])
def api_presenca_monitor():
    usuario = _usuario_logado()
    if not _usuario_pode_telespectar_app(usuario):
        return jsonify({"sucesso": False, "mensagem": "Sem permissão de telespectador."}), 403
    if not _ao_vivo_desbloqueado():
        return jsonify({
            "sucesso": False,
            "mensagem": "Confirme sua senha para acessar o Ao vivo.",
            "requer_senha": True,
        }), 403
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            lista = listar_presenca_monitor(conn, usuario)
            lista = _filtrar_presenca_monitor_admin(conn, usuario, lista)
        return jsonify({"sucesso": True, "presencas": lista})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/presenca/desbloquear", methods=["POST"])
def api_presenca_desbloquear():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if not _usuario_pode_telespectar_app(usuario):
        return jsonify({"sucesso": False, "mensagem": "Sem permissão de telespectador."}), 403
    payload = request.get_json(silent=True) or {}
    senha = str(payload.get("senha") or "")
    ok, lista_admin = _validar_senha_desbloqueio_telespectador(usuario, senha)
    if ok:
        _definir_ao_vivo_desbloqueado(True, lista_completa_admin=lista_admin)
        return jsonify({"sucesso": True, "desbloqueado": True})
    _ok, msg = _validar_senha_usuario_logado(usuario, senha)
    return jsonify({"sucesso": False, "mensagem": msg}), 400


@app.route("/api/controle-perfis/desbloquear", methods=["POST"])
def api_controle_perfis_desbloquear():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if not _usuario_pode_controle_perfis(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    payload = request.get_json(silent=True) or {}
    senha = str(payload.get("senha") or "")
    ok, _lista_admin = _validar_senha_desbloqueio_telespectador(usuario, senha)
    if ok:
        _definir_controle_perfis_desbloqueado(True)
        return jsonify({"sucesso": True, "desbloqueado": True})
    _ok, msg = _validar_senha_usuario_logado(usuario, senha)
    return jsonify({"sucesso": False, "mensagem": msg}), 400


@app.route("/api/controle-perfis/bloquear", methods=["POST"])
def api_controle_perfis_bloquear():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    _definir_controle_perfis_desbloqueado(False)
    return jsonify({"sucesso": True, "desbloqueado": False})


@app.route("/api/controle-perfis/mecanicos")
def api_controle_perfis_mecanicos():
    usuario = _usuario_logado()
    if not _usuario_pode_controle_perfis(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    if not _controle_perfis_desbloqueado():
        return jsonify({
            "sucesso": False,
            "mensagem": "Digite sua senha para acessar.",
            "requer_senha": True,
        }), 403
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_ordens_servico()
        with conexao_principal() as conn_pr, conexao_banco() as conn_app:
            _init_usuarios(conn_pr)
            rows = conn_pr.execute(
                """
                SELECT id, usuario, nome_exibicao, foto_perfil
                FROM usuarios
                WHERE perfil = 'mecanico' AND ativo = 1
                ORDER BY nome_exibicao COLLATE NOCASE, usuario COLLATE NOCASE
                """
            ).fetchall()
            mecanicos = []
            for row in rows:
                mid = int(row["id"])
                ordens = _ordens_abertas_mecanico(conn_app, mid, visao_requisicao="responsavel")
                foto = (row["foto_perfil"] or "").strip() if "foto_perfil" in row.keys() else ""
                mecanicos.append({
                    "id": mid,
                    "usuario": row["usuario"],
                    "nome_exibicao": row["nome_exibicao"] or row["usuario"],
                    "foto_perfil": foto or None,
                    "total_os": len(ordens),
                    "indicador_sidebar": indicador_sidebar_mecanico(conn_app, mid),
                })
        return jsonify({"sucesso": True, "mecanicos": mecanicos})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/atividade")
def api_atividade_listar():
    usuario = _usuario_logado()
    if not _usuario_pode_ver_rastreio_atividade(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    limite = request.args.get("limite", 1000, type=int)
    try:
        with conexao_principal() as conn:
            registros = listar_atividades(conn, limite=limite)
            rastreio_terceiro = rastreio_controle_terceiro_ativo(conn)
        return jsonify({
            "sucesso": True,
            "atividades": registros,
            "ordem_categorias": list(ATIVIDADE_ORDEM_CATEGORIAS),
            "rastreio_controle_terceiro_ativo": rastreio_terceiro,
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/atividade/<int:atividade_id>", methods=["DELETE"])
def api_atividade_excluir(atividade_id: int):
    usuario = _usuario_logado()
    if not _usuario_pode_excluir_rastreio_atividade(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    payload = request.get_json(silent=True) or {}
    senha = str(payload.get("senha") or "")
    ok, msg = _validar_senha_admin_ou_rotacao(usuario, senha)
    if not ok:
        return jsonify({"sucesso": False, "mensagem": msg or "Senha incorreta."}), 400
    try:
        with conexao_principal() as conn:
            removido = excluir_atividade(conn, atividade_id)
            conn.commit()
        if not removido:
            return jsonify({"sucesso": False, "mensagem": "Registro não encontrado."}), 404
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Exclusão de registro de atividade",
            f"ID {atividade_id}",
        )
        return jsonify({"sucesso": True})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/atividade/limpar", methods=["POST"])
def api_atividade_limpar():
    usuario = _usuario_logado()
    if not _usuario_pode_limpar_rastreio_atividade(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    payload = request.get_json(silent=True) or {}
    senha = str(payload.get("senha") or "")
    ok, msg = _validar_senha_admin_ou_rotacao(usuario, senha)
    if not ok:
        return jsonify({"sucesso": False, "mensagem": msg or "Senha incorreta."}), 400
    try:
        with conexao_principal() as conn:
            removidos = limpar_atividades(conn)
            conn.commit()
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Limpeza do rastreio de atividade",
            f"{removidos} registro(s) removido(s)",
        )
        return jsonify({"sucesso": True, "removidos": removidos})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/config/rastreio-controle-terceiro", methods=["POST"])
def api_config_rastreio_controle_terceiro():
    usuario = _usuario_logado()
    if not _usuario_e_admin(usuario):
        return jsonify({"sucesso": False, "mensagem": "Apenas administradores."}), 403
    payload = request.get_json(silent=True) or {}
    if "ativo" not in payload:
        return jsonify({"sucesso": False, "mensagem": "Informe o campo ativo."}), 400
    ativo = _config_bool(payload.get("ativo"), padrao=False)
    try:
        with conexao_principal() as conn:
            definir_rastreio_controle_terceiro(conn, ativo)
            conn.commit()
        _registrar_acao_rastreio(
            usuario,
            "Configurações",
            "Rastreio de controle de terceiro",
            "Ativado" if ativo else "Desativado",
        )
        return jsonify({"sucesso": True, "rastreio_controle_terceiro_ativo": ativo})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/presenca/bloquear", methods=["POST"])
def api_presenca_bloquear():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    _definir_ao_vivo_desbloqueado(False)
    return jsonify({"sucesso": True, "desbloqueado": False})


@app.route("/api/mecanicos")
def api_mecanicos():
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            rows = conn.execute(
                """
                SELECT id, usuario, nome_exibicao
                FROM usuarios
                WHERE perfil = 'mecanico' AND ativo = 1
                ORDER BY nome_exibicao COLLATE NOCASE, usuario COLLATE NOCASE
                """
            ).fetchall()
        mecanicos = [
            {
                "id": row["id"],
                "usuario": row["usuario"],
                "nome_exibicao": row["nome_exibicao"] or row["usuario"],
            }
            for row in rows
        ]
        return jsonify({"sucesso": True, "mecanicos": mecanicos})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/quadro-os")
def api_quadro_os():
    usuario = _usuario_logado()
    if not _usuario_pode_ver_todas_os(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    negado = _negar_sem_modulo(usuario, "lista")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "lista_os_geral_visualizar")
    if negado:
        return negado
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            init_fluxo_tabelas(conn)
            pausas = _status_pausa_sql(conn)
            ph_pausa = ", ".join("?" * len(pausas)) if pausas else "''"
            params_pausa: list[Any] = list(pausas) if pausas else []
            rows = conn.execute(
                f"""
                SELECT numero_os, cliente_nome, status, mecanico_id, mecanico_nome,
                       atualizado_em, dados_json
                FROM ordens_servico
                WHERE COALESCE(status, 'aberto') NOT IN ('fechado', 'cancelado', 'concluido'"""
                + (f", {ph_pausa})" if pausas else ")")
                + """
                ORDER BY numero_os DESC
                LIMIT 100
                """,
                params_pausa,
            ).fetchall()
            itens = []
            for row in rows:
                st = resolver_status_exibicao_lista_os(
                    conn,
                    numero_os=int(row["numero_os"]),
                    status_os=row["status"],
                    mecanico_id=row["mecanico_id"],
                    dados_json=row["dados_json"],
                )
                itens.append({
                    "numero_os": row["numero_os"],
                    "cliente_nome": row["cliente_nome"] or "",
                    "status": row["status"] or "aberto",
                    "mecanico_id": row["mecanico_id"],
                    "mecanico_nome": row["mecanico_nome"] or "",
                    "atualizado_em": row["atualizado_em"] or "",
                    "status_exibicao": st,
                })
        return jsonify({"sucesso": True, "itens": itens})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


def _resumo_os_de_dados_json(dados_json: str | None) -> dict[str, str]:
    try:
        dados = json.loads(dados_json or "{}")
    except json.JSONDecodeError:
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    fabricante = (dados.get("fabricante") or "").strip()
    modelo = (dados.get("modelo") or "").strip()
    motor = f"{fabricante} {modelo}".strip()
    return {
        "embarcacao_nome": (dados.get("embarcacao_nome") or "").strip(),
        "entregue_por": (dados.get("entregue_por") or "").strip(),
        "motor": motor,
        "alegacoes_cliente": (dados.get("alegacoes_cliente") or "").strip(),
        "horas_uso": (dados.get("horas_uso") or "").strip(),
    }


def _garantir_historico_controle_os_tabela(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mecanico_historico_controle_os (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            servico_id INTEGER NOT NULL UNIQUE,
            mecanico_cadastro_id INTEGER NOT NULL,
            usuario_mecanico_id INTEGER,
            data_entrada TEXT,
            motor TEXT,
            cliente_primeiro_nome TEXT,
            responsavel TEXT,
            valor_servico REAL NOT NULL DEFAULT 0,
            finalizado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_mhcos_usuario_mecanico
        ON mecanico_historico_controle_os (usuario_mecanico_id, finalizado_em DESC)
        """
    )


def _primeiro_nome_cliente_historico(nome: str | None) -> str:
    partes = str(nome or "").strip().split()
    return partes[0] if partes else "—"


def _valor_servico_controle_os(
    mo: Any,
    valor_comissao_revisao: Any,
) -> float:
    valor = round(float(mo or 0), 2)
    if valor <= 0:
        valor = round(float(valor_comissao_revisao or 0), 2)
    return valor


def _ids_mecanico_cadastro_usuario(
    conn: sqlite3.Connection,
    usuario_mecanico_id: int,
) -> set[int]:
    """IDs da tabela mecanicos vinculados ao usuário mecânico do app."""
    urow = conn.execute(
        "SELECT id, nome_exibicao, mecanico_cadastro_id FROM usuarios WHERE id = ?",
        (int(usuario_mecanico_id),),
    ).fetchone()
    if urow is None:
        return set()
    ids: set[int] = set()
    if urow["mecanico_cadastro_id"] is not None:
        ids.add(int(urow["mecanico_cadastro_id"]))
    nome_u = str(urow["nome_exibicao"] or "").strip().upper()
    if not nome_u:
        return ids
    for row in conn.execute("SELECT id, nome FROM mecanicos").fetchall():
        nome_m = str(row["nome"] or "").strip().upper()
        if not nome_m:
            continue
        if (
            nome_m == nome_u
            or nome_m.startswith(nome_u + " ")
            or nome_u.startswith(nome_m.split()[0] + " ")
            or nome_m.split()[0] == nome_u
        ):
            ids.add(int(row["id"]))
    return ids


def _servico_controle_os_finalizado_row(row: sqlite3.Row) -> bool:
    sit = str(row["situacao"] or "").strip().casefold()
    if sit in {"entregue", "pronto"}:
        return True
    try:
        return int(row["pago"] or 0) == 1
    except (TypeError, ValueError):
        return False


def _listar_controle_os_mecanico_perfil(
    conn: sqlite3.Connection,
    usuario_mecanico_id: int,
) -> list[dict[str, Any]]:
    """Notas do Controle de O.S. (servicos) vinculadas à O.S. digital do mecânico."""
    cadastro_ids = _ids_mecanico_cadastro_usuario(conn, int(usuario_mecanico_id))
    if not cadastro_ids:
        return []
    placeholders = ", ".join("?" * len(cadastro_ids))
    rows = conn.execute(
        f"""
        SELECT s.id, s.entrada, s.responsavel, s.mo, s.valor_comissao_revisao,
               s.situacao, s.pago, s.numero_os_digital, s.itens_json,
               m.marca_modelo, c.nome AS cliente_nome
        FROM servicos s
        JOIN motores m ON m.id = s.motor_id
        JOIN clientes c ON c.id = m.cliente_id
        WHERE s.numero_os_digital IS NOT NULL
          AND UPPER(COALESCE(s.tipo_documento, '')) = 'NOTA'
          AND s.mecanico_id IN ({placeholders})
        ORDER BY COALESCE(s.entrada, s.criado_em, '') DESC, s.id DESC
        LIMIT 100
        """,
        tuple(cadastro_ids),
    ).fetchall()
    itens: list[dict[str, Any]] = []
    for row in rows:
        if not _servico_controle_os_finalizado_row(row):
            continue
        valor = _valor_servico_controle_os(row["mo"], row["valor_comissao_revisao"])
        itens.append(
            {
                "servico_id": int(row["id"]),
                "numero_os": int(row["numero_os_digital"]),
                "data_entrada": str(row["entrada"] or "").strip(),
                "motor": str(row["marca_modelo"] or "").strip() or "—",
                "cliente_primeiro_nome": _primeiro_nome_cliente_historico(row["cliente_nome"]),
                "responsavel": str(row["responsavel"] or "").strip() or "—",
                "valor_servico": valor,
                "finalizado_em": "",
                "situacao": str(row["situacao"] or "").strip(),
                "origem": "controle_os",
            }
        )
    return itens


def _historico_controle_os_mecanico(
    conn: sqlite3.Connection,
    usuario_mecanico_id: int,
) -> dict[str, Any]:
    _garantir_historico_controle_os_tabela(conn)
    uid = int(usuario_mecanico_id)
    cadastro_ids = _ids_mecanico_cadastro_usuario(conn, uid)
    params: list[Any] = [uid]
    where_parts = ["h.usuario_mecanico_id = ?"]
    if cadastro_ids:
        ph = ", ".join("?" * len(cadastro_ids))
        where_parts.append(f"h.mecanico_cadastro_id IN ({ph})")
        params.extend(sorted(cadastro_ids))
    where_sql = " OR ".join(where_parts)
    rows = conn.execute(
        f"""
        SELECT h.servico_id, h.data_entrada, h.motor, h.cliente_primeiro_nome,
               h.responsavel, h.valor_servico, h.finalizado_em
        FROM mecanico_historico_controle_os h
        WHERE {where_sql}
        ORDER BY COALESCE(h.data_entrada, h.finalizado_em) DESC, h.id DESC
        """,
        params,
    ).fetchall()
    itens: list[dict[str, Any]] = []
    total_valor = 0.0
    for r in rows:
        valor = round(float(r["valor_servico"] or 0), 2)
        total_valor += valor
        itens.append(
            {
                "servico_id": int(r["servico_id"]),
                "data_entrada": r["data_entrada"] or "",
                "motor": r["motor"] or "—",
                "cliente_primeiro_nome": r["cliente_primeiro_nome"] or "—",
                "responsavel": r["responsavel"] or "—",
                "valor_servico": valor,
                "finalizado_em": r["finalizado_em"] or "",
                "origem": "historico",
            }
        )
    return {
        "itens": itens,
        "total_qtd": len(itens),
        "total_valor": round(total_valor, 2),
    }


def _ordens_abertas_mecanico(
    conn: sqlite3.Connection,
    mecanico_id: int,
    *,
    visao_requisicao: str = "mecanico",
) -> list[dict[str, Any]]:
    pausas_cfg = _status_pausa_sql(conn)
    excluir = tuple(_OS_STATUS_INATIVOS_MECANICO | frozenset(pausas_cfg))
    placeholders = ", ".join("?" * len(excluir))
    rows = conn.execute(
        f"""
        SELECT numero_os, cliente_nome, status, mecanico_id, mecanico_nome,
               dados_json, atualizado_em, data_entrada
        FROM ordens_servico
        WHERE mecanico_id = ?
          AND COALESCE(status, 'aberto') NOT IN ({placeholders})
        ORDER BY numero_os DESC
        """,
        (int(mecanico_id), *excluir),
    ).fetchall()
    return [
        _row_para_item_os_perfil(conn, row, visao_requisicao=visao_requisicao)
        for row in rows
    ]


def _ordens_pausa_mecanico(
    conn: sqlite3.Connection,
    mecanico_id: int,
    *,
    visao_requisicao: str = "mecanico",
) -> list[dict[str, Any]]:
    pausas = _status_pausa_sql(conn)
    if not pausas:
        return []
    placeholders = ", ".join("?" * len(pausas))
    rows = conn.execute(
        f"""
        SELECT numero_os, cliente_nome, status, mecanico_id, mecanico_nome,
               dados_json, atualizado_em, data_entrada
        FROM ordens_servico
        WHERE mecanico_id = ?
          AND COALESCE(status, 'aberto') IN ({placeholders})
        ORDER BY numero_os DESC
        """,
        (int(mecanico_id), *pausas),
    ).fetchall()
    return [
        _row_para_item_os_perfil(conn, row, visao_requisicao=visao_requisicao)
        for row in rows
    ]


def _contagens_pausa_os(conn: sqlite3.Connection) -> dict[str, int]:
    pausas_cfg = carregar_pausas_tipos(conn)
    pausas = _status_pausa_sql(conn)
    contagem: dict[str, int] = {"total": 0}
    slug_por_status = {status_pausa_de_slug(str(p["slug"])): str(p["slug"]) for p in pausas_cfg if p.get("slug")}
    for p in pausas_cfg:
        slug = str(p.get("slug") or "")
        if slug:
            contagem[slug] = 0
    if not pausas:
        return contagem
    placeholders = ", ".join("?" * len(pausas))
    rows = conn.execute(
        f"""
        SELECT status, COUNT(*) AS qtd
        FROM ordens_servico
        WHERE COALESCE(status, 'aberto') IN ({placeholders})
        GROUP BY status
        """,
        pausas,
    ).fetchall()
    for row in rows:
        st = str(row["status"] or "").strip()
        qtd = int(row["qtd"] or 0)
        contagem["total"] += qtd
        chave = slug_por_status.get(st) or slug_de_status_pausa(st) or ""
        if chave and chave in contagem:
            contagem[chave] = qtd
    return contagem


def _listar_os_pausadas(
    conn: sqlite3.Connection,
    *,
    filtro: str = "geral",
    limite: int = 50,
) -> list[dict[str, Any]]:
    pausas = _status_pausa_sql(conn)
    if not pausas:
        return []
    placeholders = ", ".join("?" * len(pausas))
    params: list[Any] = list(pausas)
    sql = f"""
        SELECT numero_os, data_entrada, cliente_nome, cliente_cpf_cnpj,
               status, criado_em, mecanico_id, mecanico_nome, dados_json, atualizado_em
        FROM ordens_servico
        WHERE COALESCE(status, 'aberto') IN ({placeholders})
    """
    filtro_norm = str(filtro or "geral").strip().lower()
    mapa_filtro = mapa_filtro_pausa(carregar_pausas_tipos(conn))
    if filtro_norm in mapa_filtro:
        sql += " AND status = ?"
        params.append(mapa_filtro[filtro_norm])
    sql += " ORDER BY numero_os DESC LIMIT ?"
    params.append(int(limite))
    rows = conn.execute(sql, params).fetchall()
    ordens: list[dict[str, Any]] = []
    for row in rows:
        st = resolver_status_exibicao_lista_os(
            conn,
            numero_os=int(row["numero_os"]),
            status_os=row["status"],
            mecanico_id=row["mecanico_id"],
            dados_json=row["dados_json"],
        )
        ordens.append({
            "numero_os": row["numero_os"],
            "data_entrada": row["data_entrada"] or "",
            "cliente_nome": row["cliente_nome"] or "",
            "cliente_cpf_cnpj": row["cliente_cpf_cnpj"] or "",
            "status": row["status"] or "",
            "criado_em": row["criado_em"] or "",
            "atualizado_em": row["atualizado_em"] or "",
            "mecanico_id": row["mecanico_id"],
            "mecanico_nome": row["mecanico_nome"] or "",
            "status_exibicao": st,
            "em_pausa": True,
            **_enriquecer_info_lista_os(conn, row["dados_json"]),
        })
    return ordens


def _listar_os_canceladas(
    conn: sqlite3.Connection,
    *,
    limite: int = 50,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT numero_os, data_entrada, cliente_nome, cliente_cpf_cnpj,
               status, criado_em, mecanico_id, mecanico_nome, dados_json, atualizado_em
        FROM ordens_servico
        WHERE COALESCE(status, '') = ?
        ORDER BY numero_os DESC
        LIMIT ?
        """,
        (_OS_STATUS_CANCELADO, int(limite)),
    ).fetchall()
    ordens: list[dict[str, Any]] = []
    for row in rows:
        st = resolver_status_exibicao_lista_os(
            conn,
            numero_os=int(row["numero_os"]),
            status_os=row["status"],
            mecanico_id=row["mecanico_id"],
            dados_json=row["dados_json"],
        )
        cancelado_em = ""
        cancelado_por = ""
        try:
            dados = json.loads(row["dados_json"] or "{}")
            if isinstance(dados, dict):
                cancelado_em = str(dados.get("cancelado_em") or "")
                cancelado_por = str(dados.get("cancelado_por") or "")
        except json.JSONDecodeError:
            pass
        ordens.append({
            "numero_os": row["numero_os"],
            "data_entrada": row["data_entrada"] or "",
            "cliente_nome": row["cliente_nome"] or "",
            "cliente_cpf_cnpj": row["cliente_cpf_cnpj"] or "",
            "status": row["status"] or "",
            "criado_em": row["criado_em"] or "",
            "atualizado_em": row["atualizado_em"] or "",
            "mecanico_id": row["mecanico_id"],
            "mecanico_nome": row["mecanico_nome"] or "",
            "status_exibicao": st,
            "cancelado_em": cancelado_em,
            "cancelado_por": cancelado_por,
            **_enriquecer_info_lista_os(conn, row["dados_json"]),
        })
    return ordens


def _cancelar_os(
    conn: sqlite3.Connection,
    numero_os: int,
    *,
    usuario: dict[str, Any] | None,
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT numero_os, status, dados_json, mecanico_id, mecanico_nome
        FROM ordens_servico WHERE numero_os = ?
        """,
        (int(numero_os),),
    ).fetchone()
    if row is None:
        raise ValueError(f"O.S. nº {numero_os} não encontrada.")
    status_atual = str(row["status"] or "aberto").strip()
    if status_atual in _OS_STATUS_NAO_CANCELAVEL:
        raise ValueError(
            "Esta O.S. não pode ser cancelada neste status "
            f"({status_atual.replace('_', ' ')})."
        )
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        dados = json.loads(row["dados_json"] or "{}")
    except json.JSONDecodeError:
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    dados["status_anterior_cancelamento"] = status_atual
    dados["cancelado_em"] = agora
    nome_usuario = ""
    if usuario:
        nome_usuario = str(
            usuario.get("nome_exibicao") or usuario.get("nome") or usuario.get("usuario") or ""
        ).strip()
    dados["cancelado_por"] = nome_usuario
    conn.execute(
        """
        UPDATE ordens_servico
        SET status = ?, dados_json = ?, atualizado_em = ?
        WHERE numero_os = ?
        """,
        (
            _OS_STATUS_CANCELADO,
            json.dumps(dados, ensure_ascii=False),
            agora,
            int(numero_os),
        ),
    )
    init_fluxo_tabelas(conn)
    conn.execute(
        """
        UPDATE requisicoes_material
        SET status = 'finalizada', atualizado_em = ?
        WHERE numero_os = ? AND COALESCE(tipo_requisicao, 'os') = 'os'
          AND status NOT IN ('finalizada')
        """,
        (agora, int(numero_os)),
    )
    return {
        "numero_os": int(numero_os),
        "status": _OS_STATUS_CANCELADO,
        "mecanico_id": row["mecanico_id"],
        "mecanico_nome": row["mecanico_nome"] or "",
    }


def _reativar_os_cancelada(conn: sqlite3.Connection, numero_os: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT numero_os, status, dados_json, mecanico_id, mecanico_nome
        FROM ordens_servico WHERE numero_os = ?
        """,
        (int(numero_os),),
    ).fetchone()
    if row is None:
        raise ValueError(f"O.S. nº {numero_os} não encontrada.")
    status_atual = str(row["status"] or "").strip()
    if status_atual != _OS_STATUS_CANCELADO:
        raise ValueError("Somente O.S. canceladas podem ser reativadas.")
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        dados = json.loads(row["dados_json"] or "{}")
    except json.JSONDecodeError:
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    status_restaurar = str(dados.pop("status_anterior_cancelamento", "") or "").strip()
    dados.pop("cancelado_em", None)
    dados.pop("cancelado_por", None)
    if not status_restaurar or status_restaurar == _OS_STATUS_CANCELADO:
        status_restaurar = "em_servico" if row["mecanico_id"] else "aberto"
    conn.execute(
        """
        UPDATE ordens_servico
        SET status = ?, dados_json = ?, atualizado_em = ?
        WHERE numero_os = ?
        """,
        (
            status_restaurar,
            json.dumps(dados, ensure_ascii=False),
            agora,
            int(numero_os),
        ),
    )
    return {
        "numero_os": int(numero_os),
        "status": status_restaurar,
        "mecanico_id": row["mecanico_id"],
        "mecanico_nome": row["mecanico_nome"] or "",
    }


def _excluir_os_cancelada_definitiva(conn: sqlite3.Connection, numero_os: int) -> None:
    row = conn.execute(
        "SELECT status FROM ordens_servico WHERE numero_os = ?",
        (int(numero_os),),
    ).fetchone()
    if row is None:
        raise ValueError(f"O.S. nº {numero_os} não encontrada.")
    if str(row["status"] or "").strip() != _OS_STATUS_CANCELADO:
        raise ValueError("Exclusão definitiva permitida apenas para O.S. canceladas.")
    init_fluxo_tabelas(conn)
    init_checklist_tabelas(conn)
    init_os_fotos_tabelas(conn)
    conn.execute(
        "DELETE FROM requisicoes_material WHERE numero_os = ?",
        (int(numero_os),),
    )
    conn.execute(
        "DELETE FROM checklists_revisao WHERE numero_os = ?",
        (int(numero_os),),
    )
    envios = conn.execute(
        "SELECT id FROM os_fotos_envio WHERE numero_os = ?",
        (int(numero_os),),
    ).fetchall()
    for env in envios:
        conn.execute(
            "DELETE FROM os_fotos_item WHERE envio_id = ?",
            (int(env["id"]),),
        )
    conn.execute(
        "DELETE FROM os_fotos_envio WHERE numero_os = ?",
        (int(numero_os),),
    )
    conn.execute(
        "DELETE FROM ordens_servico WHERE numero_os = ?",
        (int(numero_os),),
    )


def _historico_perfil_mecanico_completo(
    conn_app: sqlite3.Connection,
    conn_principal: sqlite3.Connection,
    usuario_mecanico_id: int,
) -> dict[str, Any]:
    """Lista Controle de O.S. a partir das notas vinculadas no Sistema Oficina."""
    del conn_app  # fonte principal: servicos + histórico no banco da oficina
    controle = _listar_controle_os_mecanico_perfil(conn_principal, usuario_mecanico_id)
    historico = _historico_controle_os_mecanico(conn_principal, usuario_mecanico_id)
    vistos: set[int] = set()
    itens: list[dict[str, Any]] = []
    for item in controle:
        sid = item.get("servico_id")
        if sid is not None:
            vistos.add(int(sid))
        itens.append(item)
    for item in historico.get("itens") or []:
        sid = item.get("servico_id")
        if sid is not None and int(sid) in vistos:
            continue
        if sid is not None:
            vistos.add(int(sid))
        itens.append(item)
    total_valor = round(sum(float(i.get("valor_servico") or 0) for i in itens), 2)
    return {
        "itens": itens,
        "total_qtd": len(itens),
        "total_valor": total_valor,
    }


def _perfil_mecanico_payload(
    conn_app: sqlite3.Connection,
    conn_principal: sqlite3.Connection,
    mecanico_id: int,
    *,
    visao_requisicao: str = "mecanico",
    usuario_logado: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    row = conn_principal.execute(
        """
        SELECT id, usuario, nome_exibicao, perfil, foto_perfil
        FROM usuarios
        WHERE id = ? AND perfil = 'mecanico' AND ativo = 1
        """,
        (int(mecanico_id),),
    ).fetchone()
    if row is None:
        return None
    foto = (row["foto_perfil"] or "").strip() if "foto_perfil" in row.keys() else ""
    ordens = _ordens_abertas_mecanico(conn_app, int(row["id"]), visao_requisicao=visao_requisicao)
    ordens_pausa = _ordens_pausa_mecanico(conn_app, int(row["id"]), visao_requisicao=visao_requisicao)
    pode_ver_historico = _usuario_pode_ver_historico_perfil_mecanico(
        usuario_logado, int(row["id"])
    )
    historico = (
        _historico_perfil_mecanico_completo(conn_app, conn_principal, int(row["id"]))
        if pode_ver_historico
        else {"itens": [], "total_qtd": 0, "total_valor": 0}
    )
    pausa_contagem = _contagens_pausa_os(conn_app)
    return {
        "id": row["id"],
        "usuario": row["usuario"],
        "nome_exibicao": row["nome_exibicao"] or row["usuario"],
        "perfil": row["perfil"],
        "foto_perfil": foto or None,
        "ordens": ordens,
        "ordens_pausa": ordens_pausa,
        "pausa_contagem": pausa_contagem,
        "pausas_tipos": carregar_pausas_tipos(conn_app),
        "marcadores_lista": carregar_marcadores_lista(conn_app),
        "total_os": len(ordens),
        "pode_ver_historico_perfil": pode_ver_historico,
        "historico_controle_os": historico,
        "indicador_sidebar": indicador_sidebar_mecanico(conn_app, int(row["id"])),
    }


def _usuario_pode_ver_perfil_mecanico(
    usuario: dict[str, Any] | None,
    mecanico_id: int,
) -> bool:
    if usuario is None:
        return not _exigir_login_efetivo()
    if _usuario_e_mecanico(usuario):
        try:
            return int(usuario.get("id") or 0) == int(mecanico_id)
        except (TypeError, ValueError):
            return False
    return _usuario_pode_atribuir_mecanico(usuario) or _usuario_e_admin(usuario)


def _usuario_pode_ver_historico_perfil_mecanico(
    usuario: dict[str, Any] | None,
    mecanico_id: int,
) -> bool:
    """Histórico de serviços e Controle de O.S. no perfil: só o próprio mecânico ou quem tem permissão."""
    if usuario is None:
        return not _exigir_login_efetivo()
    if _usuario_e_mecanico(usuario):
        try:
            return int(usuario.get("id") or 0) == int(mecanico_id)
        except (TypeError, ValueError):
            return False
    return _usuario_tem_permissao(usuario, "perfil_mecanico_ver_historico")


@app.route("/api/mecanicos-ativos")
def api_mecanicos_ativos():
    usuario = _usuario_logado()
    if _usuario_e_mecanico(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_ordens_servico()
        with conexao_principal() as conn_pr, conexao_banco() as conn_app:
            _init_usuarios(conn_pr)
            mecanicos_rows = conn_pr.execute(
                """
                SELECT id, usuario, nome_exibicao, foto_perfil
                FROM usuarios
                WHERE perfil = 'mecanico' AND ativo = 1
                ORDER BY nome_exibicao COLLATE NOCASE, usuario COLLATE NOCASE
                """
            ).fetchall()
            mecanicos = []
            for m in mecanicos_rows:
                ordens = _ordens_abertas_mecanico(
                    conn_app, int(m["id"]), visao_requisicao="responsavel"
                )
                if not ordens:
                    continue
                foto = (m["foto_perfil"] or "").strip() if "foto_perfil" in m.keys() else ""
                mecanicos.append({
                    "id": m["id"],
                    "usuario": m["usuario"],
                    "nome_exibicao": m["nome_exibicao"] or m["usuario"],
                    "foto_perfil": foto or None,
                    "ordens": ordens,
                    "total_os": len(ordens),
                    "indicador_sidebar": indicador_sidebar_mecanico(conn_app, int(m["id"])),
                })
        return jsonify({"sucesso": True, "mecanicos": mecanicos})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/perfil-mecanico/foto", methods=["POST"])
def api_salvar_foto_perfil():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login para alterar a foto."}), 401
    payload = request.get_json(silent=True) or {}
    foto = str(payload.get("foto") or "").strip()
    if not foto:
        return jsonify({"sucesso": False, "mensagem": "Envie a imagem da foto."}), 400
    if not foto.startswith("data:image/"):
        return jsonify({"sucesso": False, "mensagem": "Formato de imagem inválido."}), 400
    if len(foto) > 280_000:
        return jsonify({
            "sucesso": False,
            "mensagem": "Imagem muito grande. Use uma foto menor (até ~200 KB).",
        }), 400
    try:
        uid = int(usuario["id"])
    except (TypeError, ValueError, KeyError):
        return jsonify({"sucesso": False, "mensagem": "Sessão inválida."}), 401
    alvo_id = uid
    if payload.get("usuario_id") is not None and _usuario_e_admin(usuario):
        alvo_id = int(payload["usuario_id"])
    elif _usuario_e_mecanico(usuario):
        alvo_id = uid
    try:
        with conexao_principal() as conn:
            _init_usuarios(conn)
            row = conn.execute(
                "SELECT id FROM usuarios WHERE id = ? AND ativo = 1",
                (alvo_id,),
            ).fetchone()
            if row is None:
                return jsonify({"sucesso": False, "mensagem": "Usuário não encontrado."}), 404
            conn.execute(
                "UPDATE usuarios SET foto_perfil = ? WHERE id = ?",
                (foto, alvo_id),
            )
        return jsonify({"sucesso": True, "mensagem": "Foto atualizada.", "foto_perfil": foto})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/perfil-mecanico/<int:mecanico_id>")
def api_perfil_mecanico(mecanico_id: int):
    usuario = _usuario_logado()
    if not _usuario_pode_ver_perfil_mecanico(usuario, mecanico_id):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_ordens_servico()
        visao_req = "mecanico" if _usuario_e_mecanico(usuario) else "responsavel"
        with conexao_principal() as conn_pr, conexao_banco() as conn_app:
            _init_usuarios(conn_pr)
            perfil = _perfil_mecanico_payload(
                conn_app, conn_pr, mecanico_id,
                visao_requisicao=visao_req,
                usuario_logado=usuario,
            )
        if perfil is None:
            return jsonify({"sucesso": False, "mensagem": "Mecânico não encontrado."}), 404
        return jsonify({"sucesso": True, "perfil": perfil})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


def _parse_filtro_int(val: str | None) -> int | None:
    s = str(val or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


@app.route("/api/perfil-mecanico/<int:mecanico_id>/historico-servicos")
def api_perfil_historico_servicos(mecanico_id: int):
    usuario = _usuario_logado()
    if not _usuario_pode_ver_historico_perfil_mecanico(usuario, mecanico_id):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    ano = _parse_filtro_int(request.args.get("ano"))
    mes = _parse_filtro_int(request.args.get("mes"))
    cliente = str(request.args.get("cliente") or "").strip()
    servico = str(request.args.get("servico") or "").strip()
    incluir_antigos = str(request.args.get("incluir_antigos") or "").strip().lower() in {
        "1", "true", "sim", "yes",
    }
    try:
        init_ordens_servico()
        with conexao_principal() as conn_pr, conexao_banco() as conn_app:
            _init_usuarios(conn_pr)
            payload = listar_historico_servicos_mecanico(
                conn_app,
                conn_pr,
                int(mecanico_id),
                ano=ano,
                mes=mes,
                cliente=cliente,
                servico=servico,
                incluir_antigos=incluir_antigos,
            )
        return jsonify({"sucesso": True, **payload})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route(
    "/api/perfil-mecanico/<int:mecanico_id>/historico-servicos/"
    "<int:numero_os>/servico-realizado",
    methods=["PUT"],
)
def api_perfil_historico_servico_realizado(mecanico_id: int, numero_os: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if not _usuario_e_mecanico(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Somente o mecânico pode editar o serviço realizado.",
        }), 403
    try:
        if int(usuario.get("id") or 0) != int(mecanico_id):
            return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    except (TypeError, ValueError):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    payload = request.get_json(silent=True) or {}
    texto = str(payload.get("servico_realizado") or "")
    servico_id = payload.get("servico_id")
    sid: int | None
    try:
        sid = int(servico_id) if servico_id not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        sid = None
    try:
        init_ordens_servico()
        with conexao_principal() as conn_pr, conexao_banco() as conn_app:
            _init_usuarios(conn_pr)
            resultado = atualizar_servico_realizado_mecanico(
                conn_app,
                conn_pr,
                int(mecanico_id),
                numero_os=int(numero_os),
                servico_id=sid,
                texto=texto,
            )
            conn_app.commit()
            conn_pr.commit()
        return jsonify({"sucesso": True, **resultado, "mensagem": "Serviço realizado salvo."})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/fotos", methods=["POST"])
def api_os_fotos_enviar(numero_os: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if not _usuario_e_mecanico(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Apenas mecânicos podem enviar fotos da O.S.",
        }), 403
    negado = _negar_sem_permissao(usuario, "fotos_os_geral_enviar")
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    fotos = payload.get("fotos")
    if not isinstance(fotos, list):
        return jsonify({"sucesso": False, "mensagem": "Envie a lista de fotos."}), 400
    try:
        init_ordens_servico()
        lim = _limites_envio_fotos_os()
        with conexao_banco() as conn:
            resultado = salvar_fotos_os(
                conn,
                numero_os=int(numero_os),
                mecanico_id=int(usuario["id"]),
                fotos=fotos,
                max_fotos_por_envio=int(lim.get("max_fotos_por_envio") or 20),
                max_bytes_por_foto=int(lim.get("max_bytes_por_foto") or 10485760),
            )
            conn.commit()
        _registrar_acao_rastreio(
            usuario,
            "Fotos O.S.",
            "Enviar fotos ao responsável",
            f"O.S. nº {numero_os} — {resultado.get('total_fotos', len(fotos))} foto(s)",
        )
        return jsonify({"sucesso": True, **resultado, "mensagem": "Fotos enviadas ao responsável."})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/pre-requisicao")
def api_os_pre_requisicao_status(numero_os: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco não encontrado."}), 500
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            row = conn.execute(
                "SELECT mecanico_id FROM ordens_servico WHERE numero_os = ?",
                (int(numero_os),),
            ).fetchone()
            if row is None:
                return jsonify({"sucesso": False, "mensagem": "O.S. não encontrada."}), 404
            if _usuario_e_mecanico(usuario):
                if int(row["mecanico_id"] or 0) != int(usuario["id"]):
                    return jsonify({"sucesso": False, "mensagem": "O.S. não atribuída a você."}), 403
            elif not _usuario_pode_atribuir_mecanico(usuario):
                return jsonify({"sucesso": False, "mensagem": "Sem permissão."}), 403
            status = status_pre_requisicao(
                conn,
                int(numero_os),
                mecanico_id=int(row["mecanico_id"] or 0),
            )
        return jsonify({"sucesso": True, **status})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/pre-requisicao/pular", methods=["POST"])
def api_os_pre_requisicao_pular(numero_os: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if not _usuario_e_mecanico(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Apenas mecânicos podem confirmar esta ação.",
        }), 403
    payload = request.get_json(silent=True) or {}
    senha = str(payload.get("senha") or "")
    ok, msg = _validar_senha_usuario_logado(usuario, senha)
    if not ok:
        return jsonify({"sucesso": False, "mensagem": msg}), 403
    pulou_fotos = bool(payload.get("pulou_fotos"))
    pulou_checklist = bool(payload.get("pulou_checklist"))
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco não encontrado."}), 500
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            status = registrar_pulo_pre_requisicao(
                conn,
                numero_os=int(numero_os),
                mecanico_id=int(usuario["id"]),
                pulou_fotos=pulou_fotos,
                pulou_checklist=pulou_checklist,
            )
            conn.commit()
        return jsonify({"sucesso": True, **status, "mensagem": "Confirmação registrada."})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/fotos-os/pendentes/contagem")
def api_fotos_os_pendentes_contagem():
    usuario = _usuario_logado()
    if not _usuario_pode_ver_fotos_os(usuario):
        return jsonify({"sucesso": True, "total": 0})
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco não encontrado."}), 500
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            total = contar_os_fotos_pendentes(conn)
        return jsonify({"sucesso": True, "total": total})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/fotos-os/pendentes")
def api_fotos_os_pendentes_lista():
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "fotos_os")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "fotos_os_geral_visualizar")
    if negado:
        return negado
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco não encontrado."}), 500
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            itens = listar_os_fotos_pendentes(conn)
        return jsonify({
            "sucesso": True,
            "itens": itens,
            "total": len(itens),
            "pode_gerar_pdf": _usuario_pode_gerar_pdf_fotos_os(usuario),
            "pode_baixar": _usuario_pode_baixar_fotos_os(usuario),
            "pode_marcar_enviado": _usuario_pode_marcar_enviado_fotos_os(usuario),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/fotos/pendentes")
def api_os_fotos_pendentes_detalhe(numero_os: int):
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "fotos_os")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "fotos_os_geral_visualizar")
    if negado:
        return negado
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco não encontrado."}), 500
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            dados = obter_fotos_pendentes_os(conn, int(numero_os))
        if dados is None:
            return jsonify({
                "sucesso": False,
                "mensagem": "Não há fotos pendentes para esta O.S.",
            }), 404
        return jsonify({"sucesso": True, **dados})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/fotos/pdf")
def api_os_fotos_pdf(numero_os: int):
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "fotos_os")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "fotos_os_geral_gerar_pdf")
    if negado:
        return negado
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco não encontrado."}), 500
    try:
        init_ordens_servico()
        with conexao_banco() as conn_app, conexao_principal() as conn_pr:
            dados = obter_fotos_pendentes_os(conn_app, int(numero_os))
            if dados is None:
                return jsonify({"sucesso": False, "mensagem": "Sem fotos pendentes."}), 404
            empresa = _obter_empresa_config(conn_pr)
            logo = _obter_logo_empresa(conn_pr)
            fotos = [str(f["foto"]) for f in dados.get("fotos") or []]
            pdf_bytes = gerar_pdf_fotos_os(dados, fotos, logo_dataurl=logo, empresa=empresa)
        _registrar_acao_rastreio(
            usuario,
            "Fotos O.S.",
            "Gerar PDF de fotos",
            f"O.S. nº {numero_os}",
        )
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500
    except Exception as exc:
        return jsonify({"sucesso": False, "mensagem": f"Erro ao gerar PDF: {exc}"}), 500
    nome = nome_pasta_cliente(dados.get("cliente_nome") or "", numero_os)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{nome}_fotos.pdf",
    )


@app.route("/api/os/<int:numero_os>/fotos/zip")
def api_os_fotos_zip(numero_os: int):
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "fotos_os")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "fotos_os_geral_baixar")
    if negado:
        return negado
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco não encontrado."}), 500
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            dados = obter_fotos_pendentes_os(conn, int(numero_os))
            if dados is None:
                return jsonify({"sucesso": False, "mensagem": "Sem fotos pendentes."}), 404
            arquivos = fotos_para_zip([str(f["foto"]) for f in dados.get("fotos") or []])
        if not arquivos:
            return jsonify({"sucesso": False, "mensagem": "Nenhuma foto válida."}), 400
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for nome_arq, conteudo in arquivos:
                zf.writestr(nome_arq, conteudo)
        buf.seek(0)
        _registrar_acao_rastreio(
            usuario,
            "Fotos O.S.",
            "Baixar fotos (ZIP)",
            f"O.S. nº {numero_os}",
        )
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500
    pasta = nome_pasta_cliente(dados.get("cliente_nome") or "", numero_os)
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{pasta}_fotos.zip",
    )


@app.route("/api/os/<int:numero_os>/fotos/marcar-enviado", methods=["POST"])
def api_os_fotos_marcar_enviado(numero_os: int):
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "fotos_os")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "fotos_os_geral_marcar_enviado")
    if negado:
        return negado
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco não encontrado."}), 500
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            alterados = marcar_fotos_os_enviadas(
                conn,
                numero_os=int(numero_os),
                usuario_id=int(usuario["id"]),
            )
            conn.commit()
            total_restante = contar_os_fotos_pendentes(conn)
        if alterados <= 0:
            return jsonify({
                "sucesso": False,
                "mensagem": "Não há fotos pendentes nesta O.S.",
            }), 404
        _registrar_acao_rastreio(
            usuario,
            "Fotos O.S.",
            "Marcar fotos enviadas ao cliente",
            f"O.S. nº {numero_os}",
        )
        return jsonify({
            "sucesso": True,
            "mensagem": "Fotos marcadas como enviadas ao cliente.",
            "total_os_pendentes": total_restante,
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/atribuir", methods=["POST", "PUT"])
def api_atribuir_os(numero_os: int):
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "lista")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "lista_os_geral_atribuir_mecanico")
    if negado:
        return negado
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    payload = request.get_json(silent=True) or {}
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            row = conn.execute(
                "SELECT numero_os FROM ordens_servico WHERE numero_os = ?",
                (numero_os,),
            ).fetchone()
            if row is None:
                return jsonify({
                    "sucesso": False,
                    "mensagem": f"O.S. nº {numero_os} não encontrada.",
                }), 404
            mecanico_id, mecanico_nome = _resolver_mecanico_os(conn, payload, usuario=usuario)
            row_st = conn.execute(
                """
                SELECT status, mecanico_id, mecanico_nome
                FROM ordens_servico WHERE numero_os = ?
                """,
                (numero_os,),
            ).fetchone()
            status_atual = str(row_st["status"] or "aberto") if row_st else "aberto"
            if status_atual in _STATUS_BLOQUEIA_TROCA_MECANICO:
                return jsonify({
                    "sucesso": False,
                    "mensagem": (
                        "Não é possível alterar o mecânico neste status. "
                        "Use «Devolver ao mecânico» para reabrir o serviço."
                    ),
                }), 400
            novo_status = status_atual
            if mecanico_id and status_atual in ("aberto", ""):
                novo_status = "em_servico"
            elif not mecanico_id and status_atual == "em_servico":
                novo_status = "aberto"
            conn.execute(
                """
                UPDATE ordens_servico
                SET mecanico_id = ?, mecanico_nome = ?, status = ?, atualizado_em = ?
                WHERE numero_os = ?
                """,
                (mecanico_id, mecanico_nome, novo_status, agora, numero_os),
            )
            if mecanico_id:
                row_dados = conn.execute(
                    "SELECT dados_json FROM ordens_servico WHERE numero_os = ?",
                    (numero_os,),
                ).fetchone()
                if row_dados and row_dados["dados_json"]:
                    try:
                        payload_os = json.loads(row_dados["dados_json"])
                        if isinstance(payload_os, dict) and payload_os.get(
                            "pre_orcamento_itens_requisicao"
                        ):
                            payload_os = _tentar_criar_requisicao_pre_orcamento(
                                conn,
                                numero_os=int(numero_os),
                                mecanico_id=int(mecanico_id),
                                mecanico_nome=mecanico_nome,
                                payload_os=payload_os,
                            )
                            conn.execute(
                                "UPDATE ordens_servico SET dados_json = ? WHERE numero_os = ?",
                                (
                                    json.dumps(payload_os, ensure_ascii=False),
                                    int(numero_os),
                                ),
                            )
                    except json.JSONDecodeError:
                        pass
        detalhe_rastreio = f"O.S. nº {numero_os}"
        if mecanico_id:
            detalhe_rastreio += f" — {mecanico_nome or 'mecânico'}"
        else:
            detalhe_rastreio += " — atribuição removida"
        _registrar_acao_rastreio(
            usuario,
            "Lista de O.S.",
            "Atribuir mecânico" if mecanico_id else "Remover atribuição de mecânico",
            detalhe_rastreio,
        )
        return jsonify({
            "sucesso": True,
            "mensagem": "Mecânico atribuído com sucesso." if mecanico_id else "Atribuição removida.",
            "numero_os": numero_os,
            "mecanico_id": mecanico_id,
            "mecanico_nome": mecanico_nome or "",
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


def _visao_fluxo_usuario(usuario: dict[str, Any] | None) -> str:
    return "mecanico" if _usuario_e_mecanico(usuario) else "responsavel"


@app.route("/api/pecas/buscar")
def api_pecas_buscar():
    usuario = _usuario_logado()
    if not _usuario_pode_usar_catalogo_pecas(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    termo = (request.args.get("termo") or "").strip()
    if len(termo) < 2:
        return jsonify({"sucesso": True, "pecas": []})
    incluir_preco = (
        _usuario_pode_editar_requisicoes_os(usuario)
        or _usuario_pode_responder_requisicoes_os(usuario)
        or _usuario_pode_editar_requisicoes_interna(usuario)
        or _usuario_pode_ver_preco_catalogo_pre_orcamentos(usuario)
    )
    try:
        with conexao_principal() as conn:
            pecas = buscar_pecas_catalogo(conn, termo, limite=12, incluir_preco=incluir_preco)
        return jsonify({"sucesso": True, "pecas": pecas})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/pecas", methods=["POST"])
def api_pecas_cadastrar():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    via_req = (
        _usuario_pode_editar_requisicoes_os(usuario)
        or _usuario_pode_editar_requisicoes_interna(usuario)
        or _usuario_pode_responder_requisicoes_os(usuario)
        or _usuario_pode_criar_requisicoes_os(usuario)
        or _usuario_pode_criar_requisicoes_interna(usuario)
    )
    via_estoque_mov = _usuario_pode_movimentar_estoque(usuario)
    via_cadastros = _usuario_pode_criar_cadastros_pecas(usuario)
    if not via_req and not via_estoque_mov and not via_cadastros:
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    if via_req:
        negado = _negar_sem_permissao(usuario, "cadastros_pecas_criar")
        if negado:
            return negado
    elif via_estoque_mov:
        negado = _negar_sem_permissao_estoque_movimentar(usuario)
        if negado:
            return negado
    else:
        negado = _negar_sem_permissao(usuario, "cadastros_pecas_criar")
        if negado:
            return negado
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    payload = request.get_json(silent=True) or {}
    descricao = str(payload.get("descricao") or "").strip()
    codigo = str(payload.get("codigo_barras") or "").strip()
    try:
        valor = parse_valor_moeda_br(str(payload.get("valor_unitario") or ""))
    except ValueError:
        return jsonify({"sucesso": False, "mensagem": "Valor unitário inválido."}), 400
    estoque_minimo = parse_quantidade(payload.get("estoque_minimo"))
    estoque_inicial = parse_quantidade(payload.get("estoque_inicial"))
    fornecedor = str(payload.get("fornecedor") or "").strip()
    try:
        with conexao_principal() as conn:
            init_estoque_schema(conn)
            novo_id = inserir_peca_catalogo(
                conn,
                descricao=descricao,
                valor_unitario=valor,
                codigo_barras=codigo,
            )
            definir_estoque_minimo(conn, novo_id, estoque_minimo)
            if fornecedor:
                definir_fornecedor_peca(conn, novo_id, fornecedor)
            if estoque_inicial > 0:
                movimentar_estoque(
                    conn,
                    catalogo_id=novo_id,
                    tipo="entrada_manual",
                    quantidade=estoque_inicial,
                    observacao="Saldo inicial no cadastro",
                    usuario_id=int(usuario["id"]) if usuario else None,
                    usuario_nome=str(usuario.get("nome_exibicao") or "") if usuario else "",
                )
            peca = obter_peca_estoque(conn, novo_id) or obter_peca_catalogo(
                conn, novo_id, incluir_preco=True
            )
        if via_estoque_mov and not via_req:
            _registrar_acao_rastreio(
                usuario,
                "Estoque",
                "Nova peça",
                descricao or f"Peça #{novo_id}",
            )
        elif via_req or via_cadastros:
            _registrar_acao_rastreio(
                usuario,
                "Cadastros",
                "Nova peça",
                descricao or f"Peça #{novo_id}",
            )
        return jsonify({
            "sucesso": True,
            "mensagem": "Peça cadastrada no cadastro da oficina.",
            "peca": peca,
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/pecas/<int:catalogo_id>", methods=["PUT"])
def api_pecas_atualizar(catalogo_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    via_req = (
        _usuario_pode_editar_requisicoes_os(usuario)
        or _usuario_pode_editar_requisicoes_interna(usuario)
        or _usuario_pode_responder_requisicoes_os(usuario)
    )
    via_estoque_mov = _usuario_pode_movimentar_estoque(usuario)
    via_cadastros = _usuario_pode_editar_cadastros_pecas(usuario)
    if not via_req and not via_estoque_mov and not via_cadastros:
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    if via_req:
        negado = _negar_sem_permissao(usuario, "cadastros_pecas_editar")
        if negado:
            return negado
    elif via_estoque_mov:
        negado = _negar_sem_permissao_estoque_movimentar(usuario)
        if negado:
            return negado
    else:
        negado = _negar_sem_permissao(usuario, "cadastros_pecas_editar")
        if negado:
            return negado
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    payload = request.get_json(silent=True) or {}
    descricao = str(payload.get("descricao") or "").strip()
    codigo = str(payload.get("codigo_barras") or "").strip()
    try:
        valor = parse_valor_moeda_br(str(payload.get("valor_unitario") or ""))
    except ValueError:
        return jsonify({"sucesso": False, "mensagem": "Valor unitário inválido."}), 400
    estoque_minimo = payload.get("estoque_minimo")
    fornecedor = payload.get("fornecedor")
    try:
        with conexao_principal() as conn:
            init_estoque_schema(conn)
            atualizar_peca_catalogo(
                conn,
                catalogo_id,
                descricao=descricao,
                valor_unitario=valor,
                codigo_barras=codigo,
            )
            if estoque_minimo is not None:
                definir_estoque_minimo(conn, catalogo_id, parse_quantidade(estoque_minimo))
            if fornecedor is not None:
                definir_fornecedor_peca(conn, catalogo_id, str(fornecedor))
            peca = obter_peca_estoque(conn, catalogo_id) or obter_peca_catalogo(
                conn, catalogo_id, incluir_preco=True
            )
        if via_estoque_mov and not via_req:
            _registrar_acao_rastreio(
                usuario,
                "Estoque",
                "Editar peça",
                descricao or f"Peça #{catalogo_id}",
            )
        elif via_req or via_cadastros:
            _registrar_acao_rastreio(
                usuario,
                "Cadastros",
                "Editar peça",
                descricao or f"Peça #{catalogo_id}",
            )
        return jsonify({
            "sucesso": True,
            "mensagem": "Cadastro de peças da oficina atualizado.",
            "peca": peca,
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/servicos/buscar")
def api_servicos_buscar():
    usuario = _usuario_logado()
    if not _usuario_pode_usar_catalogo_servicos(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    termo = (request.args.get("termo") or "").strip()
    if len(termo) < 2:
        return jsonify({"sucesso": True, "servicos": []})
    try:
        with conexao_principal() as conn:
            servicos = buscar_servicos_catalogo(conn, termo, limite=12, incluir_preco=True)
        return jsonify({"sucesso": True, "servicos": servicos})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/servicos", methods=["POST"])
def api_servicos_cadastrar():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    via_req = (
        _usuario_pode_editar_requisicoes_os(usuario)
        or _usuario_pode_editar_requisicoes_interna(usuario)
        or _usuario_pode_responder_requisicoes_os(usuario)
        or _usuario_pode_criar_requisicoes_os(usuario)
        or _usuario_pode_criar_requisicoes_interna(usuario)
    )
    via_cadastros = _usuario_pode_criar_cadastros_servicos(usuario)
    if not via_req and not via_cadastros:
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    negado = _negar_sem_permissao(usuario, "cadastros_servicos_criar")
    if negado:
        return negado
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    payload = request.get_json(silent=True) or {}
    descricao = str(payload.get("descricao") or "").strip()
    try:
        valor = parse_valor_moeda_br(str(payload.get("valor_unitario") or ""))
    except ValueError:
        return jsonify({"sucesso": False, "mensagem": "Valor unitário inválido."}), 400
    gera_comissao = _config_bool(payload.get("gera_comissao"), padrao=True)
    try:
        with conexao_principal() as conn:
            novo_id = inserir_servico_catalogo(
                conn,
                descricao=descricao,
                valor_unitario=valor,
                gera_comissao=gera_comissao,
            )
            servico = obter_servico_catalogo(conn, novo_id, incluir_preco=True)
        _registrar_acao_rastreio(
            usuario,
            "Cadastros",
            "Novo serviço",
            descricao or f"Serviço #{novo_id}",
        )
        return jsonify({
            "sucesso": True,
            "mensagem": "Serviço cadastrado no catálogo da oficina.",
            "servico": servico,
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/servicos/<int:catalogo_id>", methods=["PUT"])
def api_servicos_atualizar(catalogo_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    via_req = (
        _usuario_pode_editar_requisicoes_os(usuario)
        or _usuario_pode_editar_requisicoes_interna(usuario)
        or _usuario_pode_responder_requisicoes_os(usuario)
    )
    via_cadastros = _usuario_pode_editar_cadastros_servicos(usuario)
    if not via_req and not via_cadastros:
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    negado = _negar_sem_permissao(usuario, "cadastros_servicos_editar")
    if negado:
        return negado
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    payload = request.get_json(silent=True) or {}
    descricao = str(payload.get("descricao") or "").strip()
    try:
        valor = parse_valor_moeda_br(str(payload.get("valor_unitario") or ""))
    except ValueError:
        return jsonify({"sucesso": False, "mensagem": "Valor unitário inválido."}), 400
    gera_comissao = _config_bool(payload.get("gera_comissao"), padrao=True)
    try:
        with conexao_principal() as conn:
            atualizar_servico_catalogo(
                conn,
                catalogo_id,
                descricao=descricao,
                valor_unitario=valor,
                gera_comissao=gera_comissao,
            )
            servico = obter_servico_catalogo(conn, catalogo_id, incluir_preco=True)
        _registrar_acao_rastreio(
            usuario,
            "Cadastros",
            "Editar serviço",
            descricao or f"Serviço #{catalogo_id}",
        )
        return jsonify({
            "sucesso": True,
            "mensagem": "Cadastro de serviços da oficina atualizado.",
            "servico": servico,
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/requisicoes", methods=["GET"])
def api_requisicoes_listar():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    numero_os = request.args.get("numero_os")
    aba = (request.args.get("aba") or "").strip().lower() or None
    negado = _negar_sem_modulo(usuario, "requisicao")
    if negado:
        return negado
    if not _usuario_pode_listar_requisicoes_aba(usuario, aba):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    try:
        os_filtro = int(numero_os) if numero_os not in (None, "") else None
    except ValueError:
        os_filtro = None
    visao = _visao_fluxo_usuario(usuario)
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            if _usuario_e_mecanico(usuario):
                lista = listar_requisicoes(
                    conn, visao=visao, numero_os=os_filtro,
                    mecanico_id=int(usuario["id"]), aba=aba,
                )
                _enriquecer_pre_requisicao_mecanico(
                    conn, lista, mecanico_id=int(usuario["id"])
                )
            else:
                lista = listar_requisicoes(conn, visao=visao, numero_os=os_filtro, aba=aba)
        for req in lista:
            _enriquecer_requisicao_catalogo(req, visao=visao)
        return jsonify({
            "sucesso": True,
            "requisicoes": lista,
            "permissoes": _permissoes_payload_requisicoes(usuario),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/requisicoes/<int:req_id>", methods=["GET"])
def api_requisicoes_obter(req_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    visao = _visao_fluxo_usuario(usuario)
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            if _usuario_e_mecanico(usuario):
                row = conn.execute(
                    """
                    SELECT id FROM requisicoes_material
                    WHERE id = ? AND mecanico_id = ?
                    """,
                    (req_id, int(usuario["id"])),
                ).fetchone()
                if row is None:
                    return jsonify({"sucesso": False, "mensagem": "Requisição não encontrada."}), 404
            req = obter_requisicao(conn, req_id, visao=visao)
            if req is None:
                return jsonify({"sucesso": False, "mensagem": "Requisição não encontrada."}), 404
            tipo_req = str(req.get("tipo_requisicao") or "os").strip().lower()
            if not _usuario_e_mecanico(usuario) and not _usuario_pode_ver_requisicao(
                usuario, tipo_requisicao=tipo_req
            ):
                return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
            if _usuario_e_mecanico(usuario):
                if int(req.get("mecanico_id") or 0) != int(usuario["id"]):
                    return jsonify({"sucesso": False, "mensagem": "Requisição não encontrada."}), 404
                pre_st, msg = _bloquear_requisicao_os_mecanico_pre(
                    conn, req, mecanico_id=int(usuario["id"])
                )
                if msg:
                    return jsonify({
                        "sucesso": False,
                        "mensagem": msg,
                        "pre_requisicao": pre_st,
                        "numero_os": int(req.get("numero_os") or 0),
                        "requisicao_id": req_id,
                    }), 403
            _enriquecer_requisicao_catalogo(req, visao=visao)
        return jsonify({
            "sucesso": True,
            "requisicao": req,
            "permissoes": _permissoes_payload_requisicoes(usuario),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/requisicoes", methods=["POST"])
def api_requisicoes_salvar():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    payload = request.get_json(silent=True) or {}
    tipo_requisicao = str(payload.get("tipo_requisicao") or "os").strip().lower()
    try:
        numero_os = int(payload.get("numero_os") or 0)
    except (TypeError, ValueError):
        return jsonify({"sucesso": False, "mensagem": "Número da O.S. inválido."}), 400
    if tipo_requisicao == "interna":
        numero_os = 0
    elif not numero_os:
        return jsonify({"sucesso": False, "mensagem": "Informe o número da O.S."}), 400
    itens = payload.get("itens") or []
    if not isinstance(itens, list):
        return jsonify({"sucesso": False, "mensagem": "Lista de itens inválida."}), 400
    observacao = str(payload.get("observacao") or "")
    titulo = str(payload.get("titulo") or "").strip()
    req_id = payload.get("id")
    try:
        req_id_int = int(req_id) if req_id not in (None, "") else None
    except (TypeError, ValueError):
        req_id_int = None
    como_responsavel = bool(payload.get("como_responsavel"))
    negado = _negar_sem_modulo(usuario, "requisicao")
    if negado:
        return negado
    if not _usuario_pode_salvar_requisicao(
        usuario,
        tipo_requisicao=tipo_requisicao,
        req_id=req_id_int,
        como_responsavel=como_responsavel,
    ):
        return jsonify({"sucesso": False, "mensagem": "Sem permissão para salvar requisição."}), 403
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            if como_responsavel and not _usuario_e_mecanico(usuario):
                salvo = salvar_requisicao(
                    conn,
                    numero_os=numero_os,
                    mecanico_id=int(payload.get("mecanico_id") or 0),
                    mecanico_nome=str(payload.get("mecanico_nome") or ""),
                    itens=itens,
                    observacao=observacao,
                    req_id=req_id_int,
                    como_responsavel=True,
                    tipo_requisicao=tipo_requisicao,
                    titulo=titulo,
                )
            elif _usuario_e_mecanico(usuario):
                if tipo_requisicao == "interna" and como_responsavel:
                    return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
                if tipo_requisicao != "interna" and numero_os:
                    exigir_pode_abrir_requisicao_mecanico(
                        conn, numero_os, mecanico_id=int(usuario["id"])
                    )
                salvo = salvar_requisicao(
                    conn,
                    numero_os=numero_os,
                    mecanico_id=int(usuario["id"]),
                    mecanico_nome=str(usuario.get("nome_exibicao") or ""),
                    itens=itens,
                    observacao=observacao,
                    req_id=req_id_int,
                    como_responsavel=False,
                    tipo_requisicao=tipo_requisicao,
                    titulo=titulo,
                )
            else:
                return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
        visao = _visao_fluxo_usuario(usuario)
        _enriquecer_requisicao_catalogo(salvo, visao=visao)
        sub_req = "Envio de requisição" if salvo.get("status") == "enviada" else "Salvar requisição"
        modulo_rast = "Requisições internas" if tipo_requisicao == "interna" else "Requisições de O.S."
        _registrar_acao_rastreio(
            usuario,
            modulo_rast,
            sub_req,
            f"Req. #{salvo.get('id') or req_id_int or '—'}"
            + (f" · O.S. {numero_os}" if numero_os else ""),
        )
        return jsonify({
            "sucesso": True,
            "requisicao": salvo,
            "permissoes": _permissoes_payload_requisicoes(usuario),
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/requisicoes/<int:req_id>/enviar", methods=["POST"])
def api_requisicoes_enviar(req_id: int):
    usuario = _usuario_logado()
    if not _usuario_e_mecanico(usuario):
        return jsonify({"sucesso": False, "mensagem": "Apenas mecânicos enviam requisições."}), 403
    negado = _negar_sem_permissao(usuario, "requisicoes_os_enviar")
    if negado:
        return negado
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            row = conn.execute(
                """
                SELECT numero_os, tipo_requisicao FROM requisicoes_material
                WHERE id = ? AND mecanico_id = ?
                """,
                (int(req_id), int(usuario["id"])),
            ).fetchone()
            if row is None:
                return jsonify({"sucesso": False, "mensagem": "Requisição não encontrada."}), 404
            tipo_req = str(row["tipo_requisicao"] or "os").strip().lower()
            numero_os = int(row["numero_os"] or 0)
            if tipo_req != "interna" and numero_os:
                exigir_pode_abrir_requisicao_mecanico(
                    conn, numero_os, mecanico_id=int(usuario["id"])
                )
            salvo = enviar_requisicao_mecanico(conn, req_id, int(usuario["id"]))
        _enriquecer_requisicao_catalogo(salvo, visao="mecanico")
        _registrar_acao_rastreio(
            usuario,
            "Requisições de O.S.",
            "Enviar requisição",
            f"Req. #{req_id}" + (f" · O.S. {numero_os}" if numero_os else ""),
        )
        return jsonify({"sucesso": True, "requisicao": salvo, "mensagem": "Requisição enviada."})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/requisicoes/<int:req_id>/responder", methods=["POST"])
def api_requisicoes_responder(req_id: int):
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "requisicao")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "requisicoes_os_responder")
    if negado:
        return negado
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            salvo = enviar_resposta_responsavel(conn, req_id)
        _enriquecer_requisicao_catalogo(salvo, visao="responsavel")
        _registrar_acao_rastreio(
            usuario,
            "Requisições de O.S.",
            "Enviar resposta (preços)",
            f"Req. #{req_id}",
        )
        return jsonify({
            "sucesso": True,
            "requisicao": salvo,
            "mensagem": "Resposta enviada ao mecânico.",
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/requisicoes/<int:req_id>/finalizar-interna", methods=["POST"])
def api_requisicoes_finalizar_interna(req_id: int):
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "requisicao")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "requisicoes_interna_finalizar_interna")
    if negado:
        return negado
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            salvo = finalizar_requisicao_interna(conn, req_id)
        _enriquecer_requisicao_catalogo(salvo, visao="responsavel")
        _registrar_acao_rastreio(
            usuario,
            "Requisições internas",
            "Finalizar requisição",
            f"Req. #{req_id}",
        )
        return jsonify({
            "sucesso": True,
            "requisicao": salvo,
            "mensagem": "Requisição interna finalizada.",
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/requisicoes/<int:req_id>/publicar-oficina", methods=["POST"])
def api_requisicoes_publicar_oficina(req_id: int):
    usuario = _usuario_logado()
    if not _usuario_e_admin(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Somente administradores podem enviar requisições internas à oficina.",
        }), 403
    with conexao_principal() as conn_cfg:
        cfg = _obter_app_os_config(conn_cfg)
    if not cfg.get("interna_publicar_oficina"):
        return jsonify({
            "sucesso": False,
            "mensagem": (
                "Envio de requisições internas à oficina está desativado. "
                "Ative em Configurações → Configuração do app."
            ),
        }), 403
    payload = request.get_json(silent=True) or {}
    senha = str(payload.get("senha") or "")
    ok, msg = _validar_senha_usuario_logado(usuario, senha)
    if not ok:
        return jsonify({"sucesso": False, "mensagem": msg}), 400
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            salvo = publicar_requisicao_interna_oficina(conn, req_id)
        _enriquecer_requisicao_catalogo(salvo, visao="responsavel")
        _registrar_acao_rastreio(
            usuario,
            "Requisições internas",
            "Enviar à oficina",
            f"Req. #{req_id}",
        )
        return jsonify({
            "sucesso": True,
            "requisicao": salvo,
            "mensagem": "Requisição interna enviada ao Sistema Oficina.",
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/requisicoes/<int:req_id>/marcar-vista", methods=["POST"])
def api_requisicoes_marcar_vista(req_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            marcar_requisicao_vista(
                conn,
                req_id,
                como_responsavel=(
                    _usuario_pode_ver_requisicoes_os_responsavel(usuario)
                    or _usuario_pode_ver_requisicoes_interna(usuario)
                ),
            )
        return jsonify({"sucesso": True})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/requisicoes/<int:req_id>/liberar-estoque", methods=["POST"])
def api_requisicoes_liberar_estoque(req_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "requisicao")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "requisicoes_os_liberar_estoque")
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    senha = str(payload.get("senha") or "")
    ok, msg = _validar_senha_usuario_logado(usuario, senha)
    if not ok:
        return jsonify({"sucesso": False, "mensagem": msg}), 400
    liberacoes = payload.get("itens") or []
    if not isinstance(liberacoes, list):
        return jsonify({"sucesso": False, "mensagem": "Lista de itens inválida."}), 400
    permitir_sem_estoque = payload.get("permitir_sem_estoque") in (True, 1, "1", "true", "sim")
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            salvo = liberar_itens_requisicao(
                conn,
                req_id=req_id,
                liberacoes=liberacoes,
                usuario_id=int(usuario["id"]),
                usuario_nome=str(usuario.get("nome_exibicao") or usuario.get("usuario") or ""),
                permitir_sem_estoque=permitir_sem_estoque,
            )
        _enriquecer_requisicao_catalogo(salvo, visao="responsavel")
        _registrar_acao_rastreio(
            usuario,
            "Requisições de O.S.",
            "Liberar peças do estoque",
            f"Req. #{req_id}",
        )
        return jsonify({"sucesso": True, "requisicao": salvo})
    except EstoqueInsuficienteError as exc:
        return jsonify({
            "sucesso": False,
            "codigo": "estoque_insuficiente",
            "mensagem": str(exc),
            "itens": exc.itens,
        }), 400
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque", methods=["GET"])
def api_estoque_listar():
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_estoque_visualizar(usuario)
    if negado:
        return negado
    termo = str(request.args.get("q") or "")
    apenas_baixo = request.args.get("baixo") in ("1", "true", "sim")
    try:
        limite = int(request.args.get("limite") or 2000)
    except ValueError:
        limite = 2000
    try:
        with conexao_principal() as conn:
            integracao = integrar_catalogo_ao_estoque(conn)
            itens, total = listar_estoque(
                conn, termo=termo, apenas_baixo=apenas_baixo, limite=limite
            )
        return jsonify({
            "sucesso": True,
            "itens": itens,
            "total": total,
            "integracao": integracao,
            "permissoes": _permissoes_payload_estoque(usuario),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque/pendencias-atualizar", methods=["GET"])
def api_estoque_pendencias_atualizar():
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_estoque_visualizar(usuario)
    if negado:
        return negado
    try:
        with conexao_principal() as conn:
            integrar_catalogo_ao_estoque(conn)
            itens = listar_pendencias_atualizar_estoque(conn)
        return jsonify({"sucesso": True, "itens": itens, "total": len(itens)})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque/pecas/<int:catalogo_id>", methods=["GET"])
def api_estoque_peca_obter(catalogo_id: int):
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_estoque_visualizar(usuario)
    if negado:
        return negado
    try:
        with conexao_principal() as conn:
            integrar_catalogo_ao_estoque(conn)
            peca = obter_peca_estoque(conn, catalogo_id)
        if peca is None:
            return jsonify({"sucesso": False, "mensagem": "Peça não encontrada."}), 404
        return jsonify({"sucesso": True, "peca": peca})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque/ordens/marcadores", methods=["GET"])
def api_estoque_ordens_marcadores_listar():
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_estoque_pedidos(usuario)
    if negado:
        return negado
    try:
        with conexao_principal() as conn:
            integrar_catalogo_ao_estoque(conn)
            marcadores = listar_marcadores_ordens(conn)
        return jsonify({
            "sucesso": True,
            "marcadores": marcadores,
            "permissoes": _permissoes_payload_estoque(usuario),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque/ordens/marcadores", methods=["POST"])
def api_estoque_ordens_marcadores_criar():
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_estoque_pedidos(usuario)
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    nome = str(payload.get("nome") or "").strip()
    try:
        with conexao_principal() as conn:
            marcador = criar_marcador_ordem(
                conn,
                nome=nome,
                fornecedor_ref=str(payload.get("fornecedor_ref") or ""),
                cor_orelha=str(payload.get("cor_orelha") or "#64748b"),
            )
        _registrar_acao_rastreio(
            usuario,
            "Estoque",
            "Criar marcador de pedido",
            nome or f"Marcador #{marcador.get('id')}",
        )
        return jsonify({"sucesso": True, "marcador": marcador})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque/ordens/marcadores/<int:marcador_id>", methods=["PUT"])
def api_estoque_ordens_marcadores_atualizar(marcador_id: int):
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_estoque_pedidos(usuario)
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    try:
        with conexao_principal() as conn:
            marcador = atualizar_marcador_ordem(
                conn,
                marcador_id,
                nome=payload.get("nome") if "nome" in payload else None,
                fornecedor_ref=payload.get("fornecedor_ref") if "fornecedor_ref" in payload else None,
                cor_orelha=payload.get("cor_orelha") if "cor_orelha" in payload else None,
            )
        _registrar_acao_rastreio(
            usuario,
            "Estoque",
            "Editar marcador de pedido",
            str(marcador.get("nome") or marcador_id),
        )
        return jsonify({"sucesso": True, "marcador": marcador})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque/ordens/marcadores/<int:marcador_id>", methods=["DELETE"])
def api_estoque_ordens_marcadores_remover(marcador_id: int):
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_estoque_pedidos(usuario)
    if negado:
        return negado
    try:
        with conexao_principal() as conn:
            remover_marcador_ordem(conn, marcador_id)
        _registrar_acao_rastreio(
            usuario,
            "Estoque",
            "Remover marcador de pedido",
            f"Marcador #{marcador_id}",
        )
        return jsonify({"sucesso": True})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque/ordens/marcadores/<int:marcador_id>/pecas-baixo", methods=["GET"])
def api_estoque_ordens_pecas_baixo(marcador_id: int):
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_estoque_pedidos(usuario)
    if negado:
        return negado
    try:
        with conexao_principal() as conn:
            marcadores = {m["id"]: m for m in listar_marcadores_ordens(conn)}
            marcador = marcadores.get(int(marcador_id))
            if marcador is None:
                return jsonify({"sucesso": False, "mensagem": "Marcador não encontrado."}), 404
            pecas = listar_pecas_baixo_fornecedor(conn, marcador.get("fornecedor_ref") or "")
        return jsonify({"sucesso": True, "marcador": marcador, "pecas": pecas})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque/ordens/marcadores/<int:marcador_id>/itens", methods=["GET"])
def api_estoque_ordens_itens_listar(marcador_id: int):
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_estoque_pedidos(usuario)
    if negado:
        return negado
    origem = request.args.get("origem")
    try:
        with conexao_principal() as conn:
            itens = listar_itens_pedido_marcador(
                conn, marcador_id, origem=origem if origem else None
            )
        return jsonify({"sucesso": True, "itens": itens})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque/ordens/marcadores/<int:marcador_id>/itens", methods=["POST"])
def api_estoque_ordens_itens_criar(marcador_id: int):
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_estoque_pedidos(usuario)
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    try:
        with conexao_principal() as conn:
            item = adicionar_item_pedido_marcador(
                conn,
                marcador_id,
                catalogo_id=int(payload.get("catalogo_id") or 0),
                quantidade=payload.get("quantidade") or 1,
                origem=str(payload.get("origem") or "loja"),
                observacao=str(payload.get("observacao") or ""),
            )
        _registrar_acao_rastreio(
            usuario,
            "Estoque",
            "Adicionar item ao pedido",
            f"Marcador #{marcador_id} · peça #{item.get('catalogo_id') or payload.get('catalogo_id')}",
        )
        return jsonify({"sucesso": True, "item": item})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque/ordens/marcadores/<int:marcador_id>/importar-sugestoes", methods=["POST"])
def api_estoque_ordens_importar_sugestoes(marcador_id: int):
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_estoque_pedidos(usuario)
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    try:
        with conexao_principal() as conn:
            itens = importar_sugestoes_pedido_marcador(
                conn,
                marcador_id,
                origem=str(payload.get("origem") or "loja"),
            )
        _registrar_acao_rastreio(
            usuario,
            "Estoque",
            "Importar sugestões no pedido",
            f"Marcador #{marcador_id} · {len(itens)} item(ns)",
        )
        return jsonify({"sucesso": True, "itens": itens})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque/ordens/itens/<int:item_id>", methods=["PUT"])
def api_estoque_ordens_itens_atualizar(item_id: int):
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_estoque_pedidos(usuario)
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    try:
        with conexao_principal() as conn:
            item = atualizar_item_pedido_marcador(
                conn,
                item_id,
                quantidade=payload.get("quantidade") if "quantidade" in payload else None,
                observacao=payload.get("observacao") if "observacao" in payload else None,
            )
        _registrar_acao_rastreio(
            usuario,
            "Estoque",
            "Editar item do pedido",
            f"Item #{item_id}",
        )
        return jsonify({"sucesso": True, "item": item})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque/ordens/itens/<int:item_id>", methods=["DELETE"])
def api_estoque_ordens_itens_remover(item_id: int):
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_estoque_pedidos(usuario)
    if negado:
        return negado
    try:
        with conexao_principal() as conn:
            remover_item_pedido_marcador(conn, item_id)
        _registrar_acao_rastreio(
            usuario,
            "Estoque",
            "Remover item do pedido",
            f"Item #{item_id}",
        )
        return jsonify({"sucesso": True})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque/movimentos", methods=["GET"])
def api_estoque_movimentos():
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_estoque_visualizar(usuario)
    if negado:
        return negado
    cat_id = request.args.get("catalogo_id")
    try:
        cid = int(cat_id) if cat_id not in (None, "") else None
    except ValueError:
        cid = None
    try:
        with conexao_principal() as conn:
            init_estoque_schema(conn)
            movs = listar_movimentos(conn, catalogo_id=cid)
        return jsonify({"sucesso": True, "movimentos": movs})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/estoque/movimentar", methods=["POST"])
def api_estoque_movimentar():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_permissao_estoque_movimentar(usuario)
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    senha = str(payload.get("senha") or "")
    ok, msg = _validar_senha_usuario_logado(usuario, senha)
    if not ok:
        return jsonify({"sucesso": False, "mensagem": msg}), 400
    try:
        catalogo_id = int(payload.get("catalogo_id"))
        tipo = str(payload.get("tipo") or "").strip()
        quantidade = parse_quantidade(payload.get("quantidade"))
        observacao = str(payload.get("observacao") or "").strip()
    except (TypeError, ValueError):
        return jsonify({"sucesso": False, "mensagem": "Dados inválidos."}), 400
    try:
        with conexao_principal() as conn:
            init_estoque_schema(conn)
            saldo = movimentar_estoque(
                conn,
                catalogo_id=catalogo_id,
                tipo=tipo,
                quantidade=quantidade,
                observacao=observacao,
                usuario_id=int(usuario["id"]),
                usuario_nome=str(usuario.get("nome_exibicao") or ""),
            )
            if payload.get("estoque_minimo") is not None:
                definir_estoque_minimo(
                    conn, catalogo_id, parse_quantidade(payload.get("estoque_minimo"))
                )
            if payload.get("fornecedor") is not None:
                definir_fornecedor_peca(conn, catalogo_id, str(payload.get("fornecedor") or ""))
            remover_pendencia_atualizar_estoque(conn, catalogo_id)
        tipo_rotulo = {
            "entrada_manual": "Entrada manual",
            "entrada_devolucao": "Devolução",
            "saida_manual": "Saída manual",
            "ajuste": "Ajuste",
        }.get(tipo, tipo or "Movimentação")
        _registrar_acao_rastreio(
            usuario,
            "Estoque",
            tipo_rotulo,
            f"Peça #{catalogo_id} · qtd {quantidade}",
        )
        return jsonify({"sucesso": True, "saldo": saldo})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/notificacoes")
def api_notificacoes():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": True, "notificacoes": []})
    visao = _visao_fluxo_usuario(usuario)
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            uid = int(usuario["id"]) if _usuario_e_mecanico(usuario) else None
            if not _usuario_e_mecanico(usuario) and not (
                _usuario_pode_ver_requisicoes_os_responsavel(usuario)
                or _usuario_pode_ver_requisicoes_interna(usuario)
            ):
                return jsonify({"sucesso": True, "notificacoes": []})
            notifs = listar_notificacoes(conn, visao=visao, usuario_id=uid)
        return jsonify({"sucesso": True, "notificacoes": notifs})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/finalizar-servico", methods=["POST"])
def api_finalizar_servico(numero_os: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login para finalizar o serviço."}), 401
    payload = request.get_json(silent=True) or {}
    senha = str(payload.get("senha") or "")
    ok, msg = _validar_senha_usuario_logado(usuario, senha)
    if not ok:
        return jsonify({"sucesso": False, "mensagem": msg}), 400
    try:
        init_ordens_servico()
        with conexao_banco() as conn_app:
            row = conn_app.execute(
                """
                SELECT mecanico_id, mecanico_nome, status
                FROM ordens_servico WHERE numero_os = ?
                """,
                (numero_os,),
            ).fetchone()
            if row is None:
                return jsonify({"sucesso": False, "mensagem": "O.S. não encontrada."}), 404
            if _mecanico_bloqueado_por_pausa(usuario, row["status"], row["mecanico_id"]):
                return jsonify({
                    "sucesso": False,
                    "mensagem": (
                        "Esta O.S. está em pausa (garantia, retífica ou peças). "
                        "Aguarde o responsável liberar para continuar."
                    ),
                }), 403
            if row["mecanico_id"] is None:
                return jsonify({
                    "sucesso": False,
                    "mensagem": "Atribua um mecânico à O.S. antes de finalizar.",
                }), 400
            try:
                uid = int(usuario["id"])
                mid = int(row["mecanico_id"])
            except (TypeError, ValueError):
                return jsonify({"sucesso": False, "mensagem": "Erro ao verificar permissão."}), 403
            if uid != mid:
                nome_mec = (row["mecanico_nome"] or "o mecânico atribuído").strip()
                return jsonify({
                    "sucesso": False,
                    "mensagem": (
                        f"Somente {nome_mec} pode finalizar esta O.S. "
                        "Entre com o login desse mecânico e finalize pelo perfil dele."
                    ),
                }), 403
            finalizar_servico_mecanico(
                conn_app,
                numero_os,
                uid,
            )
        _sync_oficina_status_os(numero_os, "pronto_mecanico")
        _registrar_acao_rastreio(
            usuario,
            "Ordem de Serviço",
            "Finalizar serviço (mecânico)",
            f"O.S. nº {numero_os}",
        )
        return jsonify({
            "sucesso": True,
            "mensagem": f"Serviço da O.S. nº {numero_os} marcado como pronto.",
            "status": "pronto_mecanico",
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/cliente-avisado", methods=["POST"])
def api_marcar_cliente_avisado(numero_os: int):
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "lista")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "lista_os_geral_cliente_avisado")
    if negado:
        return negado
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            marcar_cliente_avisado_os(conn, numero_os)
        _sync_oficina_status_os(numero_os, "cliente_avisado")
        _registrar_acao_rastreio(
            usuario,
            "Lista de O.S.",
            "Marcar cliente avisado",
            f"O.S. nº {numero_os}",
        )
        return jsonify({
            "sucesso": True,
            "mensagem": f"O.S. nº {numero_os}: cliente marcado como avisado.",
            "status": "cliente_avisado",
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/devolver-mecanico", methods=["POST"])
def api_devolver_os_mecanico(numero_os: int):
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "lista")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "lista_os_geral_retomar")
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    senha = str(payload.get("senha") or "")
    ok, msg = _validar_senha_usuario_logado(usuario, senha)
    if not ok:
        return jsonify({"sucesso": False, "mensagem": msg}), 400
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            info = devolver_os_ao_mecanico(conn, numero_os)
        _registrar_acao_rastreio(
            usuario,
            "Lista de O.S.",
            "Devolver ao mecânico",
            f"O.S. nº {numero_os} — {info.get('mecanico_nome') or ''}".strip(),
        )
        return jsonify({
            "sucesso": True,
            "mensagem": (
                f"O.S. nº {numero_os} devolvida ao mecânico "
                f"{info.get('mecanico_nome') or ''} para continuar o serviço."
            ).strip(),
            "status": info.get("status"),
            "mecanico_id": info.get("mecanico_id"),
            "mecanico_nome": info.get("mecanico_nome") or "",
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/pausadas", methods=["GET"])
def api_os_pausadas():
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "lista")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "lista_os_geral_visualizar")
    if negado:
        return negado
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    filtro = (request.args.get("filtro") or "geral").strip().lower()
    limite = request.args.get("limite", "50")
    try:
        limite_int = max(1, min(int(limite), 100))
    except ValueError:
        limite_int = 50
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            init_fluxo_tabelas(conn)
            ordens = _listar_os_pausadas(conn, filtro=filtro, limite=limite_int)
            contagem = _contagens_pausa_os(conn)
            pausas_tipos = carregar_pausas_tipos(conn)
        return jsonify({
            "sucesso": True,
            "filtro": filtro,
            "contagem": contagem,
            "pausas_tipos": pausas_tipos,
            "ordens": ordens,
            "pode_retomar_os": _usuario_pode_retomar_lista_os(usuario),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/pausa", methods=["POST"])
def api_definir_pausa_os(numero_os: int):
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "lista")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "lista_os_geral_pausar")
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    tipo_raw = str(payload.get("tipo") or payload.get("pausa") or "").strip().lower()
    if not tipo_raw:
        return jsonify({
            "sucesso": False,
            "mensagem": "Informe o tipo de pausa.",
        }), 400
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            info = definir_pausa_os(conn, numero_os, tipo_raw)
        _sync_oficina_status_os(numero_os, info.get("status") or "")
        _registrar_acao_rastreio(
            usuario,
            "Lista de O.S.",
            "Marcar pausa",
            f"O.S. nº {numero_os} — {info.get('pausa_rotulo') or tipo_raw}",
        )
        return jsonify({
            "sucesso": True,
            "mensagem": f"O.S. nº {numero_os} marcada como {info.get('pausa_rotulo') or tipo_raw}.",
            "status": info.get("status"),
            "mecanico_id": info.get("mecanico_id"),
            "mecanico_nome": info.get("mecanico_nome") or "",
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/retomar", methods=["POST"])
def api_retomar_os_pausa(numero_os: int):
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "lista")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "lista_os_geral_retomar")
    if negado:
        return negado
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            info = retomar_os_de_pausa(conn, numero_os)
        _sync_oficina_status_os(numero_os, "em_servico")
        _registrar_acao_rastreio(
            usuario,
            "Lista de O.S.",
            "Retomar O.S. pausada",
            f"O.S. nº {numero_os} — mecânico {info.get('mecanico_nome') or ''}".strip(),
        )
        return jsonify({
            "sucesso": True,
            "mensagem": (
                f"O.S. nº {numero_os} devolvida ao mecânico "
                f"{info.get('mecanico_nome') or ''}."
            ).strip(),
            "status": info.get("status"),
            "mecanico_id": info.get("mecanico_id"),
            "mecanico_nome": info.get("mecanico_nome") or "",
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/canceladas", methods=["GET"])
def api_os_canceladas():
    usuario = _usuario_logado()
    negado = _negar_sem_modulo(usuario, "lista")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "lista_os_geral_visualizar")
    if negado:
        return negado
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    limite = request.args.get("limite", "50")
    try:
        limite_int = max(1, min(int(limite), 100))
    except ValueError:
        limite_int = 50
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            ordens = _listar_os_canceladas(conn, limite=limite_int)
        return jsonify({
            "sucesso": True,
            "total": len(ordens),
            "ordens": ordens,
            "pode_reativar_os": _usuario_pode_reativar_os_lista(usuario),
            "pode_excluir_os_cancelada": _usuario_pode_excluir_os_cancelada(usuario),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/cancelar", methods=["POST"])
def api_cancelar_os(numero_os: int):
    usuario = _usuario_logado()
    if not _usuario_pode_cancelar_os_lista(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Sem permissão para cancelar O.S.",
        }), 403
    payload = request.get_json(silent=True) or {}
    motivo = str(payload.get("motivo") or "").strip()
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            info = _cancelar_os(conn, numero_os, usuario=usuario)
            if motivo:
                row = conn.execute(
                    "SELECT dados_json FROM ordens_servico WHERE numero_os = ?",
                    (int(numero_os),),
                ).fetchone()
                if row and row["dados_json"]:
                    try:
                        dados = json.loads(row["dados_json"])
                        if isinstance(dados, dict):
                            dados["motivo_cancelamento"] = motivo
                            conn.execute(
                                "UPDATE ordens_servico SET dados_json = ? WHERE numero_os = ?",
                                (
                                    json.dumps(dados, ensure_ascii=False),
                                    int(numero_os),
                                ),
                            )
                    except json.JSONDecodeError:
                        pass
        _sync_oficina_status_os(numero_os, _OS_STATUS_CANCELADO)
        _registrar_acao_rastreio(
            usuario,
            "Lista de O.S.",
            "Cancelar O.S.",
            f"O.S. nº {numero_os}" + (f" — {motivo}" if motivo else ""),
        )
        return jsonify({
            "sucesso": True,
            "mensagem": f"O.S. nº {numero_os} cancelada. Ela saiu da lista ativa.",
            **info,
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/reativar", methods=["POST"])
def api_reativar_os_cancelada(numero_os: int):
    usuario = _usuario_logado()
    if not _usuario_pode_reativar_os_lista(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Sem permissão para reativar O.S. cancelada.",
        }), 403
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            info = _reativar_os_cancelada(conn, numero_os)
            row_dados = conn.execute(
                "SELECT dados_json FROM ordens_servico WHERE numero_os = ?",
                (int(numero_os),),
            ).fetchone()
            if row_dados and row_dados["dados_json"]:
                try:
                    payload_os = json.loads(row_dados["dados_json"])
                    if isinstance(payload_os, dict) and payload_os.get(
                        "pre_orcamento_itens_requisicao"
                    ):
                        payload_os = _tentar_criar_requisicao_pre_orcamento(
                            conn,
                            numero_os=int(numero_os),
                            mecanico_id=info.get("mecanico_id"),
                            mecanico_nome=info.get("mecanico_nome"),
                            payload_os=payload_os,
                        )
                        conn.execute(
                            "UPDATE ordens_servico SET dados_json = ? WHERE numero_os = ?",
                            (
                                json.dumps(payload_os, ensure_ascii=False),
                                int(numero_os),
                            ),
                        )
                except json.JSONDecodeError:
                    pass
        _sync_oficina_status_os(numero_os, info.get("status") or "aberto")
        _registrar_acao_rastreio(
            usuario,
            "Lista de O.S.",
            "Reativar O.S. cancelada",
            f"O.S. nº {numero_os}",
        )
        return jsonify({
            "sucesso": True,
            "mensagem": f"O.S. nº {numero_os} reativada e devolvida à lista principal.",
            **info,
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/excluir-definitiva", methods=["DELETE"])
def api_excluir_os_cancelada(numero_os: int):
    usuario = _usuario_logado()
    if not _usuario_pode_excluir_os_cancelada(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Sem permissão para excluir O.S. cancelada.",
        }), 403
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            _excluir_os_cancelada_definitiva(conn, int(numero_os))
        _registrar_acao_rastreio(
            usuario,
            "Lista de O.S.",
            "Exclusão definitiva de O.S.",
            f"O.S. nº {numero_os}",
        )
        return jsonify({
            "sucesso": True,
            "mensagem": f"O.S. nº {numero_os} excluída permanentemente.",
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/copiar-retorno", methods=["GET"])
def api_copiar_os_retorno(numero_os: int):
    """Retorna dados de cliente/motor para nova O.S. (retorno do cliente)."""
    usuario = _usuario_logado()
    if not _usuario_pode_copiar_os(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Sem permissão para criar O.S. a partir de outra.",
        }), 403
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            row = conn.execute(
                """
                SELECT numero_os, cliente_id, assinatura_tecnico, assinatura_cliente, dados_json
                FROM ordens_servico WHERE numero_os = ?
                """,
                (numero_os,),
            ).fetchone()
            if row is None:
                return jsonify({"sucesso": False, "mensagem": "O.S. não encontrada."}), 404
            dados, _ = dados_os_de_registro(
                row,
                assinatura_tecnico=row["assinatura_tecnico"],
                assinatura_cliente=row["assinatura_cliente"],
            )
            nome_atendente = str(usuario.get("nome_exibicao") or usuario.get("usuario") or "").strip()
            dados_novo = _dados_os_para_retorno(
                dados,
                numero_os_origem=numero_os,
                nome_atendente=nome_atendente or None,
            )
        _registrar_acao_rastreio(
            usuario,
            "Lista de O.S.",
            "Copiar para retorno",
            f"O.S. nº {numero_os}",
        )
        return jsonify({
            "sucesso": True,
            "numero_os_origem": numero_os,
            "cliente_id": row["cliente_id"],
            "dados": dados_novo,
            "mensagem": (
                f"Dados da O.S. nº {numero_os} copiados. Preencha entrega, alegações e assinaturas da nova visita."
            ),
        })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


def _usuario_pode_ver_checklist_os(
    usuario: dict[str, Any] | None,
    mecanico_id: int | None,
) -> bool:
    if _usuario_pode_ver_todas_os(usuario):
        return True
    if not usuario or mecanico_id is None:
        return False
    try:
        return int(usuario.get("id") or 0) == int(mecanico_id)
    except (TypeError, ValueError):
        return False


@app.route("/api/os/<int:numero_os>/checklist-revisao", methods=["GET"])
def api_checklist_revisao_obter(numero_os: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            row_os = conn.execute(
                "SELECT mecanico_id, mecanico_nome FROM ordens_servico WHERE numero_os = ?",
                (numero_os,),
            ).fetchone()
            if row_os is None:
                return jsonify({"sucesso": False, "mensagem": "O.S. não encontrada."}), 404
            if not _usuario_pode_ver_checklist_os(usuario, row_os["mecanico_id"]):
                return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
            if _usuario_e_mecanico(usuario):
                checklist = obter_ou_rascunho_checklist(
                    conn,
                    numero_os,
                    mecanico_id=int(usuario["id"]),
                    mecanico_nome=str(usuario.get("nome_exibicao") or usuario.get("usuario") or ""),
                )
            else:
                checklist = obter_checklist_leitura(conn, numero_os)
        return jsonify({"sucesso": True, "checklist": checklist})
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/os/<int:numero_os>/checklist-revisao", methods=["POST"])
def api_checklist_revisao_salvar(numero_os: int):
    usuario = _usuario_logado()
    if not _usuario_e_mecanico(usuario):
        return jsonify({"sucesso": False, "mensagem": "Apenas o mecânico atribuído pode salvar o checklist."}), 403
    payload = request.get_json(silent=True) or {}
    cabecalho = payload.get("cabecalho") or {}
    itens = payload.get("itens") or []
    if not isinstance(cabecalho, dict):
        return jsonify({"sucesso": False, "mensagem": "Cabeçalho inválido."}), 400
    if not isinstance(itens, list):
        return jsonify({"sucesso": False, "mensagem": "Lista de itens inválida."}), 400
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            salvo = salvar_checklist(
                conn,
                numero_os,
                mecanico_id=int(usuario["id"]),
                cabecalho=cabecalho,
                itens=itens,
            )
        _registrar_acao_rastreio(
            usuario,
            "Ordem de Serviço",
            "Checklist de revisão",
            f"O.S. nº {numero_os}",
        )
        return jsonify({
            "sucesso": True,
            "mensagem": "Checklist salvo. Horas e campos da O.S. atualizados.",
            "checklist": salvo,
        })
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/pdf_checklist/<int:numero_os>")
def pdf_checklist(numero_os: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            row_os = conn.execute(
                "SELECT mecanico_id FROM ordens_servico WHERE numero_os = ?",
                (numero_os,),
            ).fetchone()
            if row_os is None:
                return jsonify({"sucesso": False, "mensagem": "O.S. não encontrada."}), 404
            if not _usuario_pode_ver_checklist_os(usuario, row_os["mecanico_id"]):
                return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
            if _usuario_e_mecanico(usuario):
                checklist = obter_ou_rascunho_checklist(
                    conn,
                    numero_os,
                    mecanico_id=int(usuario["id"]),
                    mecanico_nome=str(usuario.get("nome_exibicao") or usuario.get("usuario") or ""),
                )
            else:
                checklist = obter_checklist_leitura(conn, numero_os)
            if checklist is None:
                return jsonify({"sucesso": False, "mensagem": "Checklist não encontrado."}), 404
            pdf_bytes = gerar_pdf_checklist_revisao(
                cabecalho=checklist.get("cabecalho") or {},
                itens=checklist.get("itens") or [],
            )
        from flask import Response
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="checklist_os_{numero_os}.pdf"',
            },
        )
    except ValueError as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/listar_os")
def listar_os():
    limite = request.args.get("limite", "15")
    try:
        limite = max(1, min(int(limite), 50))
    except ValueError:
        limite = 15

    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500

    usuario = _usuario_logado()
    if not _usuario_e_mecanico(usuario):
        negado = _negar_sem_modulo(usuario, "lista")
        if negado:
            return negado
        negado = _negar_sem_permissao(usuario, "lista_os_geral_visualizar")
        if negado:
            return negado
    ordens: list[dict[str, Any]] = []
    marcadores_cfg: list[dict[str, Any]] = []
    pausas_cfg: list[dict[str, Any]] = []
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            init_fluxo_tabelas(conn)
            pausas_cfg = carregar_pausas_tipos(conn)
            marcadores_cfg = carregar_marcadores_lista(conn)
            excluir = _status_excluidos_lista_os_ativa(conn)
            ph_excl = ", ".join("?" * len(excluir)) if excluir else None
            if _usuario_e_mecanico(usuario):
                if ph_excl:
                    rows = conn.execute(
                        f"""
                        SELECT numero_os, data_entrada, cliente_nome, cliente_cpf_cnpj,
                               status, criado_em, mecanico_id, mecanico_nome, dados_json
                        FROM ordens_servico
                        WHERE mecanico_id = ?
                          AND COALESCE(status, 'aberto') NOT IN ({ph_excl})
                        ORDER BY numero_os DESC
                        LIMIT ?
                        """,
                        (int(usuario["id"]), *excluir, limite),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT numero_os, data_entrada, cliente_nome, cliente_cpf_cnpj,
                               status, criado_em, mecanico_id, mecanico_nome, dados_json
                        FROM ordens_servico
                        WHERE mecanico_id = ?
                        ORDER BY numero_os DESC
                        LIMIT ?
                        """,
                        (int(usuario["id"]), limite),
                    ).fetchall()
            elif ph_excl:
                rows = conn.execute(
                    f"""
                    SELECT numero_os, data_entrada, cliente_nome, cliente_cpf_cnpj,
                           status, criado_em, mecanico_id, mecanico_nome, dados_json
                    FROM ordens_servico
                    WHERE COALESCE(status, 'aberto') NOT IN ({ph_excl})
                    ORDER BY numero_os DESC
                    LIMIT ?
                    """,
                    (*excluir, limite),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT numero_os, data_entrada, cliente_nome, cliente_cpf_cnpj,
                           status, criado_em, mecanico_id, mecanico_nome, dados_json
                    FROM ordens_servico
                    ORDER BY numero_os DESC
                    LIMIT ?
                    """,
                    (limite,),
                ).fetchall()
            ordens = []
            for row in rows:
                st = resolver_status_exibicao_lista_os(
                    conn,
                    numero_os=int(row["numero_os"]),
                    status_os=row["status"],
                    mecanico_id=row["mecanico_id"],
                    dados_json=row["dados_json"],
                )
                ordens.append({
                    "numero_os": row["numero_os"],
                    "data_entrada": row["data_entrada"] or "",
                    "cliente_nome": row["cliente_nome"] or "",
                    "cliente_cpf_cnpj": row["cliente_cpf_cnpj"] or "",
                    "status": row["status"] or "",
                    "criado_em": row["criado_em"] or "",
                    "mecanico_id": row["mecanico_id"],
                    "mecanico_nome": row["mecanico_nome"] or "",
                    "status_exibicao": st,
                    "pode_devolver_mecanico": _pode_devolver_os_ao_mecanico(
                        row["status"], row["mecanico_id"], usuario
                    ),
                    **_enriquecer_info_lista_os(conn, row["dados_json"]),
                })
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500

    return jsonify({
        "sucesso": True,
        "total": len(ordens),
        "ordens": ordens,
        "pode_marcar_cliente_avisado": _usuario_pode_marcar_cliente_avisado_lista(usuario),
        "pode_atribuir_mecanico_lista": _usuario_pode_atribuir_mecanico_lista_os(usuario),
        "pode_copiar_os": _usuario_pode_copiar_os(usuario),
        "pode_editar_info_lista": _usuario_pode_editar_info_lista_os(usuario),
        "pode_pausar_os": _usuario_pode_pausar_lista_os(usuario),
        "pode_retomar_os": _usuario_pode_retomar_lista_os(usuario),
        "pode_cancelar_os": _usuario_pode_cancelar_os_lista(usuario),
        "pode_reativar_os": _usuario_pode_reativar_os_lista(usuario),
        "pode_excluir_os_cancelada": _usuario_pode_excluir_os_cancelada(usuario),
        "marcadores": marcadores_cfg if _usuario_pode_editar_info_lista_os(usuario) else [],
        "pausas_tipos": pausas_cfg if _usuario_pode_pausar_lista_os(usuario) else [],
    })


@app.route("/obter_os/<int:numero_os>")
def obter_os(numero_os: int):
    """Retorna os dados completos de uma O.S. para reabrir no formulário."""
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500

    carga_restrita = False
    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            row = conn.execute(
                """
                SELECT numero_os, data_entrada, nome_atendente, cliente_id,
                       cliente_nome, cliente_cpf_cnpj, status,
                       assinatura_tecnico, assinatura_cliente,
                       mecanico_id, mecanico_nome,
                       dados_json, criado_em, atualizado_em
                FROM ordens_servico WHERE numero_os = ?
                """,
                (numero_os,),
            ).fetchone()
            if row is None:
                return jsonify({"sucesso": False, "mensagem": "O.S. não encontrada."}), 404
            usuario = _usuario_logado()
            if _mecanico_bloqueado_por_pausa(usuario, row["status"], row["mecanico_id"]):
                return jsonify({
                    "sucesso": False,
                    "mensagem": (
                        "Esta O.S. está em pausa. O mecânico não pode editar "
                        "até o responsável retomar o serviço."
                    ),
                }), 403
            if not _usuario_pode_editar_os(usuario, row["mecanico_id"]):
                return jsonify({
                    "sucesso": False,
                    "mensagem": "Você não tem permissão para abrir esta O.S.",
                }), 403
            dados, num = dados_os_de_registro(
                row,
                assinatura_tecnico=row["assinatura_tecnico"],
                assinatura_cliente=row["assinatura_cliente"],
            )
            dados["numero_os"] = num
            itens_chk = carregar_itens_checklist_os(conn, numero_os)
            dados = preparar_campos_diagnostico_os_para_impressao(dados, itens=itens_chk)
            origem = (request.args.get("origem") or "modulo").strip().lower()
            if (_usuario_e_mecanico(usuario) and not _mecanico_pode_editar_os_existente(usuario)
                    and origem != "perfil"):
                dados = _filtrar_dados_os_resumo_mecanico(dados)
                carga_restrita = True
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500
    except json.JSONDecodeError:
        return jsonify({"sucesso": False, "mensagem": "Dados da O.S. estão corrompidos."}), 500

    usuario = _usuario_logado()
    return jsonify({
        "sucesso": True,
        "numero_os": num,
        "status": row["status"] or "",
        "cliente_id": None if carga_restrita else row["cliente_id"],
        "mecanico_id": row["mecanico_id"],
        "mecanico_nome": row["mecanico_nome"] or "",
        "criado_em": row["criado_em"] or "",
        "atualizado_em": row["atualizado_em"] or "",
        "dados": dados,
        "carga_restrita": carga_restrita,
        "permissoes_os": _permissoes_formulario_os(usuario),
    })


@app.route("/api/assinatura/config")
def api_assinatura_config():
    return jsonify({
        "sucesso": True,
        "url_base": _obter_url_publica_base(),
        "duracao_qr_horas": _ASSINATURA_DURACAO_HORAS["qr"],
        "duracao_link_horas": _ASSINATURA_DURACAO_HORAS["link"],
    })


@app.route("/api/assinatura/sessao", methods=["POST"])
def api_assinatura_criar_sessao():
    if _exigir_login_efetivo() and not _usuario_logado():
        return jsonify({"sucesso": False, "requer_login": True, "mensagem": "Faça login para gerar links."}), 401

    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return jsonify({"sucesso": False, "mensagem": "Dados inválidos."}), 400

    tipo = (payload.get("tipo") or "").strip()
    if tipo not in _ASSINATURA_TIPOS_VALIDOS:
        return jsonify({"sucesso": False, "mensagem": "Tipo de assinatura inválido."}), 400

    modo = (payload.get("modo") or "qr").strip().lower()
    if modo not in ("qr", "link"):
        modo = "qr"

    titulo = (payload.get("titulo") or _ASSINATURA_TITULOS.get(tipo) or tipo).strip()
    canvas_id = (payload.get("canvas_id") or "").strip() or None
    cliente_nome = (payload.get("cliente_nome") or "").strip() or None

    numero_os = payload.get("numero_os")
    if numero_os in ("", None):
        numero_os = None
    else:
        try:
            numero_os = int(numero_os)
        except (TypeError, ValueError):
            numero_os = None

    token = secrets.token_urlsafe(24)
    pin = f"{secrets.randbelow(10000):04d}" if modo == "link" else None
    agora_dt = datetime.now()
    agora = agora_dt.strftime("%Y-%m-%d %H:%M:%S")
    horas = _ASSINATURA_DURACAO_HORAS["link" if modo == "link" else "qr"]
    expira_em = (agora_dt + timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        init_assinaturas_remotas()
        with conexao_banco() as conn:
            _limpar_assinaturas_expiradas(conn)
            conn.execute(
                """
                INSERT INTO assinaturas_remotas (
                    token, tipo, canvas_id, numero_os, cliente_nome, titulo,
                    status, criado_em, expira_em, pin
                ) VALUES (?, ?, ?, ?, ?, ?, 'pendente', ?, ?, ?)
                """,
                (token, tipo, canvas_id, numero_os, cliente_nome, titulo, agora, expira_em, pin),
            )
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500

    url = f"{_obter_url_publica_base()}/assinar/{token}"
    resposta: dict[str, Any] = {
        "sucesso": True,
        "token": token,
        "url": url,
        "modo": modo,
        "tipo": tipo,
        "titulo": titulo,
        "expira_em": expira_em,
    }
    if pin:
        resposta["pin"] = pin
    return jsonify(resposta)


@app.route("/assinar/<token>")
def pagina_assinar(token: str):
    try:
        init_assinaturas_remotas()
        with conexao_banco() as conn:
            _limpar_assinaturas_expiradas(conn)
            row = conn.execute(
                "SELECT * FROM assinaturas_remotas WHERE token = ?",
                (token,),
            ).fetchone()
    except sqlite3.Error as exc:
        return render_template(
            "assinar.html",
            erro=f"Erro ao carregar: {exc}",
            sessao=None,
            app_version=APP_VERSION,
        ), 500

    if row is None:
        return render_template(
            "assinar.html",
            erro="Link de assinatura inválido ou não encontrado.",
            sessao=None,
            app_version=APP_VERSION,
        ), 404

    sessao = _assinatura_row_para_json(row)
    if sessao["status"] == "expirado":
        return render_template(
            "assinar.html",
            erro="Este link de assinatura expirou. Solicite um novo à oficina.",
            sessao=sessao,
            app_version=APP_VERSION,
        ), 410

    if sessao["status"] == "assinado":
        return render_template(
            "assinar.html",
            erro=None,
            sessao=sessao,
            ja_assinado=True,
            app_version=APP_VERSION,
        )

    return render_template(
        "assinar.html",
        erro=None,
        sessao=sessao,
        ja_assinado=False,
        app_version=APP_VERSION,
    )


@app.route("/api/assinatura/<token>", methods=["GET"])
def api_assinatura_status(token: str):
    try:
        init_assinaturas_remotas()
        with conexao_banco() as conn:
            _limpar_assinaturas_expiradas(conn)
            row = conn.execute(
                "SELECT * FROM assinaturas_remotas WHERE token = ?",
                (token,),
            ).fetchone()
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500

    if row is None:
        return jsonify({"sucesso": False, "mensagem": "Sessão não encontrada."}), 404

    dados = _assinatura_row_para_json(row)
    if dados.get("assinado_em"):
        dados["data_assinatura"] = str(dados["assinado_em"])[:10]
    return jsonify({"sucesso": True, **dados})


@app.route("/api/assinatura/<token>", methods=["POST"])
def api_assinatura_enviar(token: str):
    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return jsonify({"sucesso": False, "mensagem": "Dados inválidos."}), 400

    imagem = _extrair_assinatura(payload, "imagem")
    if not imagem:
        return jsonify({"sucesso": False, "mensagem": "Desenhe a assinatura antes de enviar."}), 400

    assinante_nome = (payload.get("assinante_nome") or "").strip()
    if not assinante_nome:
        return jsonify({
            "sucesso": False,
            "mensagem": "Informe o nome completo de quem está assinando.",
        }), 400

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        init_assinaturas_remotas()
        with conexao_banco() as conn:
            _limpar_assinaturas_expiradas(conn)
            row = conn.execute(
                "SELECT status, expira_em, pin FROM assinaturas_remotas WHERE token = ?",
                (token,),
            ).fetchone()
            if row is None:
                return jsonify({"sucesso": False, "mensagem": "Sessão não encontrada."}), 404
            pin_esperado = (row["pin"] or "").strip()
            if pin_esperado:
                pin_informado = str(payload.get("pin") or "").strip()
                if pin_informado != pin_esperado:
                    return jsonify({
                        "sucesso": False,
                        "mensagem": "Código de segurança incorreto. Peça o PIN à oficina.",
                    }), 403
            if row["status"] == "expirado" or (row["expira_em"] or "") < agora:
                conn.execute(
                    "UPDATE assinaturas_remotas SET status = 'expirado' WHERE token = ?",
                    (token,),
                )
                return jsonify({"sucesso": False, "mensagem": "Link de assinatura expirado."}), 410
            if row["status"] == "assinado":
                return jsonify({"sucesso": True, "mensagem": "Assinatura já registrada."})

            sessao = conn.execute(
                "SELECT numero_os, tipo FROM assinaturas_remotas WHERE token = ?",
                (token,),
            ).fetchone()
            conn.execute(
                """
                UPDATE assinaturas_remotas
                SET imagem = ?, status = 'assinado', assinado_em = ?, assinante_nome = ?
                WHERE token = ?
                """,
                (imagem, agora, assinante_nome, token),
            )
            if sessao and sessao["numero_os"] is not None:
                _aplicar_assinatura_remota_na_os(
                    conn,
                    int(sessao["numero_os"]),
                    str(sessao["tipo"] or ""),
                    imagem,
                    assinante_nome=assinante_nome,
                )
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500

    return jsonify({"sucesso": True, "mensagem": "Assinatura enviada com sucesso. Obrigado!"})


def _data_ag_iso_para_br(iso: str) -> str:
    texto = str(iso or "").strip()[:10]
    if len(texto) == 10 and texto[4] == "-":
        return f"{texto[8:10]}/{texto[5:7]}/{texto[0:4]}"
    return texto


def _detalhe_rastreio_agendamento(ag: dict[str, Any], *, sufixo: str = "") -> str:
    partes: list[str] = []
    ag_id = ag.get("id")
    if ag_id:
        partes.append(f"Agend. #{ag_id}")
    cliente = str(ag.get("cliente_nome") or "").strip()
    if cliente:
        partes.append(cliente)
    data = str(ag.get("data_agendamento") or "")[:10]
    if data:
        partes.append(_data_ag_iso_para_br(data))
    motor = str(ag.get("motor_rotulo") or "").strip()
    if motor:
        partes.append(motor)
    if sufixo:
        partes.append(sufixo)
    return " · ".join(partes) if partes else "—"


def _registrar_rastreio_agendamento(
    usuario: dict[str, Any] | None,
    subcategoria: str,
    ag: dict[str, Any],
    *,
    sufixo: str = "",
) -> None:
    _registrar_acao_rastreio(
        usuario,
        "Agendamentos",
        subcategoria,
        _detalhe_rastreio_agendamento(ag, sufixo=sufixo),
    )


def _detalhe_rastreio_pre_orcamento(pre: dict[str, Any], *, sufixo: str = "") -> str:
    partes: list[str] = []
    numero = str(pre.get("numero") or "").strip()
    if numero:
        partes.append(numero)
    elif pre.get("id"):
        partes.append(f"#{pre['id']}")
    cliente = str(pre.get("cliente_nome") or "").strip()
    if cliente:
        partes.append(cliente)
    motor = str(pre.get("motor") or "").strip()
    if motor:
        partes.append(motor)
    if sufixo:
        partes.append(sufixo)
    return " · ".join(partes) if partes else "—"


def _detalhe_rastreio_kit_motor(kit: dict[str, Any], *, sufixo: str = "") -> str:
    partes: list[str] = []
    modelo = str(kit.get("modelo_motor") or "").strip()
    if modelo:
        partes.append(modelo)
    if kit.get("id"):
        partes.append(f"#{kit['id']}")
    if sufixo:
        partes.append(sufixo)
    return " · ".join(partes) if partes else "—"


def _registrar_rastreio_pre_orcamento(
    usuario: dict[str, Any] | None,
    subcategoria: str,
    pre: dict[str, Any],
    *,
    sufixo: str = "",
) -> None:
    _registrar_acao_rastreio(
        usuario,
        "Pré-Orçamentos",
        subcategoria,
        _detalhe_rastreio_pre_orcamento(pre, sufixo=sufixo),
    )


def _registrar_rastreio_kit_motor(
    usuario: dict[str, Any] | None,
    subcategoria: str,
    kit: dict[str, Any],
    *,
    sufixo: str = "",
) -> None:
    _registrar_acao_rastreio(
        usuario,
        "Pré-Orçamentos",
        subcategoria,
        _detalhe_rastreio_kit_motor(kit, sufixo=sufixo),
    )


@app.route("/api/agendamentos/calendario", methods=["GET"])
def api_agendamentos_calendario():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "agendamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "agendamentos_geral_visualizar")
    if negado:
        return negado
    try:
        ano = int(request.args.get("ano") or date.today().year)
        mes = int(request.args.get("mes") or date.today().month)
    except (TypeError, ValueError):
        return jsonify({"sucesso": False, "mensagem": "Ano ou mês inválido."}), 400
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_agendamentos()
        with conexao_principal() as conn:
            dias = resumo_calendario_mes(conn, ano=ano, mes=mes)
            meta = metadados_mes(ano, mes)
        return jsonify({"sucesso": True, "dias": dias, "calendario": meta})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/agendamentos/dia", methods=["GET"])
def api_agendamentos_dia():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "agendamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "agendamentos_geral_visualizar")
    if negado:
        return negado
    data = (request.args.get("data") or "").strip()
    if not data:
        return jsonify({"sucesso": False, "mensagem": "Informe a data."}), 400
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_agendamentos()
        with conexao_principal() as conn:
            with conexao_banco() as conn_os:
                lista = listar_agendamentos_dia(conn, data=data, conn_os=conn_os)
        return jsonify({"sucesso": True, "agendamentos": lista, "data": data[:10]})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/agendamentos", methods=["POST"])
def api_agendamentos_criar():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "agendamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "agendamentos_geral_criar")
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    try:
        id_cliente = int(payload.get("id_cliente") or 0)
        id_motor = payload.get("id_motor")
        id_motor_int = int(id_motor) if id_motor not in (None, "", 0) else None
    except (TypeError, ValueError):
        return jsonify({"sucesso": False, "mensagem": "Cliente ou motor inválido."}), 400
    if id_cliente <= 0:
        return jsonify({"sucesso": False, "mensagem": "Selecione um cliente."}), 400
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_agendamentos()
        with conexao_principal() as conn:
            _garantir_colunas_motores(conn)
            item = criar_agendamento(
                conn,
                id_cliente=id_cliente,
                id_motor=id_motor_int,
                data_agendamento=str(payload.get("data_agendamento") or ""),
                alegacao_cliente=str(payload.get("alegacao_cliente") or ""),
                status=str(payload.get("status") or "Agendado"),
                tipo_local=str(payload.get("tipo_local") or "Interno"),
            )
        sub_rastreio = (
            "Agendamento de emergência"
            if str(item.get("status") or "") == STATUS_EMERGENCIA
            else "Novo agendamento"
        )
        _registrar_rastreio_agendamento(usuario, sub_rastreio, item)
        return jsonify({"sucesso": True, "agendamento": item})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/agendamentos/<int:ag_id>", methods=["GET"])
def api_agendamentos_obter(ag_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "agendamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "agendamentos_geral_visualizar")
    if negado:
        return negado
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_agendamentos()
        with conexao_principal() as conn:
            item = obter_agendamento(conn, ag_id)
        if item is None:
            return jsonify({"sucesso": False, "mensagem": "Agendamento não encontrado."}), 404
        return jsonify({"sucesso": True, "agendamento": item})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/agendamentos/<int:ag_id>/reagendar", methods=["POST"])
def api_agendamentos_reagendar(ag_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "agendamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "agendamentos_geral_editar")
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    try:
        id_motor = payload.get("id_motor")
        id_motor_int = int(id_motor) if id_motor not in (None, "", 0) else None
    except (TypeError, ValueError):
        return jsonify({"sucesso": False, "mensagem": "Motor inválido."}), 400
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_agendamentos()
        with conexao_principal() as conn:
            _garantir_colunas_motores(conn)
            anterior = obter_agendamento(conn, ag_id)
            item = reagendar_agendamento(
                conn,
                ag_id,
                data_agendamento=str(payload.get("data_agendamento") or ""),
                id_motor=id_motor_int,
                alegacao_cliente=payload.get("alegacao_cliente"),
                tipo_local=payload.get("tipo_local"),
            )
        sufixo = ""
        if anterior:
            data_ant = str(anterior.get("data_agendamento") or "")[:10]
            data_nova = str(item.get("data_agendamento") or "")[:10]
            if data_ant and data_nova and data_ant != data_nova:
                sufixo = (
                    f"de {_data_ag_iso_para_br(data_ant)} "
                    f"para {_data_ag_iso_para_br(data_nova)}"
                )
        _registrar_rastreio_agendamento(usuario, "Reagendar", item, sufixo=sufixo)
        return jsonify({"sucesso": True, "agendamento": item})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/agendamentos/<int:ag_id>/cancelar", methods=["POST"])
def api_agendamentos_cancelar(ag_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "agendamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "agendamentos_geral_excluir")
    if negado:
        return negado
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_agendamentos()
        with conexao_principal() as conn:
            item = cancelar_agendamento(conn, ag_id)
        _registrar_rastreio_agendamento(usuario, "Cancelar agendamento", item)
        return jsonify({"sucesso": True, "agendamento": item})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/agendamentos/<int:ag_id>/emergencia", methods=["POST"])
def api_agendamentos_emergencia(ag_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "agendamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "agendamentos_geral_editar")
    if negado:
        return negado
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_agendamentos()
        with conexao_principal() as conn:
            item = marcar_emergencia(conn, ag_id)
        _registrar_rastreio_agendamento(usuario, "Marcar emergência", item)
        return jsonify({"sucesso": True, "agendamento": item})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/agendamentos/<int:ag_id>/remover-emergencia", methods=["POST"])
def api_agendamentos_remover_emergencia(ag_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "agendamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "agendamentos_geral_editar")
    if negado:
        return negado
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_agendamentos()
        with conexao_principal() as conn:
            item = remover_emergencia(conn, ag_id)
        _registrar_rastreio_agendamento(usuario, "Remover emergência", item)
        return jsonify({"sucesso": True, "agendamento": item})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/agendamentos/<int:ag_id>/gerar-os", methods=["POST"])
def api_agendamentos_gerar_os(ag_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "agendamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "agendamentos_geral_gerar_os")
    if negado:
        return negado
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        init_agendamentos()
        with conexao_principal() as conn:
            _garantir_colunas_clientes(conn)
            _garantir_colunas_motores(conn)
            with conexao_banco() as conn_os:
                ag = validar_agendamento_para_gerar_os(conn, conn_os, ag_id)
            row_cli = conn.execute(
                f"SELECT {_COLUNAS_CLIENTE} FROM clientes WHERE id = ?",
                (int(ag["id_cliente"]),),
            ).fetchone()
            if row_cli is None:
                return jsonify({"sucesso": False, "mensagem": "Cliente não encontrado."}), 404
            motor_json = None
            if ag.get("id_motor"):
                emb_sql = sql_embarcacao_motor("motores")
                row_m = conn.execute(
                    f"""
                    SELECT id, cliente_id, chassi, horas, marca_modelo,
                           {emb_sql} AS embarcacao, observacoes
                    FROM motores WHERE id = ?
                    """,
                    (int(ag["id_motor"]),),
                ).fetchone()
                if row_m is not None:
                    motor_json = _motor_para_json(row_m)
        _registrar_rastreio_agendamento(
            usuario,
            "Preparar O.S. a partir do agendamento",
            ag,
        )
        return jsonify({
            "sucesso": True,
            "agendamento_id": ag_id,
            "cliente": _cliente_para_json(row_cli),
            "motor": motor_json,
            "motor_id": ag.get("id_motor"),
            "alegacao_cliente": ag.get("alegacao_cliente") or "",
            "data_entrada": date.today().isoformat(),
        })
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/pre-orcamentos/kits", methods=["GET"])
def api_pre_orcamentos_kits_listar():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "pre_orcamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao_kits_visualizar(usuario)
    if negado:
        return negado
    termo = (request.args.get("termo") or request.args.get("q") or "").strip()
    modo = (request.args.get("modo") or "busca").strip()
    todos = request.args.get("todos") in ("1", "true", "sim", "yes")
    try:
        limite = int(request.args.get("limite") or (500 if todos else 25))
    except (TypeError, ValueError):
        limite = 500 if todos else 25
    try:
        with conexao_pre_orcamentos() as conn:
            if todos and not termo:
                kits = listar_todos_kits_motor(conn, limite=limite)
            else:
                kits = buscar_kits_motor(conn, termo=termo, limite=limite, modo=modo)
        return jsonify({"sucesso": True, "kits": kits})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/pre-orcamentos/kits/<int:kit_id>", methods=["GET"])
def api_pre_orcamentos_kits_obter(kit_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "pre_orcamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao_kits_visualizar(usuario)
    if negado:
        return negado
    try:
        with conexao_pre_orcamentos() as conn:
            kit = obter_kit_motor(conn, kit_id)
        if kit is None:
            return jsonify({"sucesso": False, "mensagem": "Kit não encontrado."}), 404
        return jsonify({"sucesso": True, "kit": kit})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/pre-orcamentos/kits/<int:kit_id>", methods=["DELETE"])
def api_pre_orcamentos_kits_excluir(kit_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "pre_orcamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "pre_orcamentos_kits_excluir")
    if negado:
        return negado
    try:
        with conexao_pre_orcamentos() as conn:
            kit = obter_kit_motor(conn, kit_id)
            excluir_kit_motor(conn, kit_id)
            conn.commit()
        if kit:
            _registrar_rastreio_kit_motor(usuario, "Excluir kit de motor", kit)
        return jsonify({"sucesso": True, "mensagem": "Kit excluído."})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/pre-orcamentos/kits/atualizar-precos", methods=["POST"])
def api_pre_orcamentos_kits_atualizar_precos():
    """Busca valores atuais no catálogo da oficina para uma lista de itens."""
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "pre_orcamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao_atualizar_precos_pre(usuario)
    if negado:
        return negado
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    payload = request.get_json(silent=True) or {}
    itens = payload.get("itens") or payload.get("lista_pecas") or []
    if not isinstance(itens, list):
        return jsonify({"sucesso": False, "mensagem": "Envie itens em formato de lista."}), 400
    try:
        with conexao_principal() as conn:
            atualizados, resumo = atualizar_precos_itens_do_catalogo(conn, itens)
        _registrar_acao_rastreio(
            usuario,
            "Pré-Orçamentos",
            "Atualizar preços do catálogo",
            f"{resumo.get('atualizados', 0)} item(ns)",
        )
        return jsonify({"sucesso": True, "itens": atualizados, "resumo": resumo})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/pre-orcamentos/kits", methods=["POST"])
def api_pre_orcamentos_kits_salvar():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "pre_orcamentos")
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    try:
        kit_id = payload.get("id")
        kit_id_int = int(kit_id) if kit_id not in (None, "", 0) else None
        if kit_id_int:
            negado = _negar_sem_permissao(usuario, "pre_orcamentos_kits_editar")
        else:
            negado = _negar_sem_permissao(usuario, "pre_orcamentos_kits_criar")
        if negado:
            return negado
        with conexao_pre_orcamentos() as conn:
            item = salvar_kit_motor(
                conn,
                modelo_motor=str(payload.get("modelo_motor") or ""),
                lista_pecas=payload.get("lista_pecas") or payload.get("lista_pecas_json") or [],
                preco_base=payload.get("preco_base"),
                kit_id=kit_id_int,
            )
            conn.commit()
        sub = "Alterar kit de motor" if kit_id_int else "Novo kit de motor"
        _registrar_rastreio_kit_motor(usuario, sub, item)
        return jsonify({"sucesso": True, "kit": item})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/pre-orcamentos/kits/importar", methods=["POST"])
def api_pre_orcamentos_kits_importar():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "pre_orcamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "pre_orcamentos_kits_criar")
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    kits = payload.get("kits") if isinstance(payload.get("kits"), list) else payload
    if not isinstance(kits, list) or not kits:
        return jsonify({"sucesso": False, "mensagem": "Envie uma lista em kits."}), 400
    try:
        with conexao_pre_orcamentos() as conn:
            resumo = importar_kits_motor_lote(conn, kits)
            conn.commit()
        det = (
            f"{resumo.get('criados', 0)} criado(s), "
            f"{resumo.get('atualizados', 0)} atualizado(s)"
        )
        _registrar_acao_rastreio(
            usuario,
            "Pré-Orçamentos",
            "Importar kits (lote)",
            det,
        )
        return jsonify({"sucesso": True, **resumo})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/pre-orcamentos", methods=["GET"])
def api_pre_orcamentos_listar():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "pre_orcamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "pre_orcamentos_geral_visualizar")
    if negado:
        return negado
    status = (request.args.get("status") or "").strip() or None
    try:
        with conexao_pre_orcamentos() as conn:
            lista = listar_pre_orcamentos(conn, status=status)
        return jsonify({"sucesso": True, "pre_orcamentos": lista})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/pre-orcamentos", methods=["POST"])
def api_pre_orcamentos_criar():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "pre_orcamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "pre_orcamentos_geral_criar")
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    try:
        cliente_id = payload.get("cliente_id")
        cliente_id_int = int(cliente_id) if cliente_id not in (None, "", 0) else None
        motor_id = payload.get("motor_id")
        motor_id_int = int(motor_id) if motor_id not in (None, "", 0) else None
        kit_id = payload.get("kit_motor_id")
        kit_id_int = int(kit_id) if kit_id not in (None, "", 0) else None
    except (TypeError, ValueError):
        return jsonify({"sucesso": False, "mensagem": "Cliente ou motor inválido."}), 400
    try:
        with conexao_pre_orcamentos() as conn:
            item = criar_pre_orcamento(
                conn,
                cliente_nome=str(payload.get("cliente_nome") or ""),
                motor=str(payload.get("motor") or ""),
                data=str(payload.get("data") or ""),
                itens=payload.get("itens") or [],
                cliente_id=cliente_id_int,
                motor_id=motor_id_int,
                kit_motor_id=kit_id_int,
                observacoes=str(payload.get("observacoes") or ""),
            )
            conn.commit()
        _registrar_rastreio_pre_orcamento(usuario, "Novo pré-orçamento", item)
        return jsonify({"sucesso": True, "pre_orcamento": item})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/pre-orcamentos/<int:pre_id>", methods=["GET"])
def api_pre_orcamentos_obter(pre_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "pre_orcamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "pre_orcamentos_geral_visualizar")
    if negado:
        return negado
    try:
        with conexao_pre_orcamentos() as conn:
            item = obter_pre_orcamento(conn, pre_id)
        if item is None:
            return jsonify({"sucesso": False, "mensagem": "Pré-orçamento não encontrado."}), 404
        return jsonify({"sucesso": True, "pre_orcamento": item})
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500


@app.route("/api/pre-orcamentos/<int:pre_id>", methods=["PUT"])
def api_pre_orcamentos_atualizar(pre_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "pre_orcamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "pre_orcamentos_geral_editar")
    if negado:
        return negado
    payload = request.get_json(silent=True) or {}
    try:
        cliente_id = payload.get("cliente_id")
        cliente_id_int = int(cliente_id) if cliente_id not in (None, "", 0) else None
        motor_id = payload.get("motor_id")
        motor_id_int = int(motor_id) if motor_id not in (None, "", 0) else None
    except (TypeError, ValueError):
        return jsonify({"sucesso": False, "mensagem": "Cliente ou motor inválido."}), 400
    try:
        with conexao_pre_orcamentos() as conn:
            item = atualizar_pre_orcamento(
                conn,
                pre_id,
                cliente_nome=payload.get("cliente_nome"),
                motor=payload.get("motor"),
                data=payload.get("data"),
                itens=payload.get("itens"),
                cliente_id=cliente_id_int,
                motor_id=motor_id_int,
                observacoes=payload.get("observacoes"),
            )
            conn.commit()
        _registrar_rastreio_pre_orcamento(usuario, "Alterar pré-orçamento", item)
        return jsonify({"sucesso": True, "pre_orcamento": item})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/pre-orcamentos/<int:pre_id>", methods=["DELETE"])
def api_pre_orcamentos_excluir(pre_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "pre_orcamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "pre_orcamentos_geral_excluir")
    if negado:
        return negado
    try:
        with conexao_pre_orcamentos() as conn:
            pre = obter_pre_orcamento(conn, pre_id)
            excluir_pre_orcamento(conn, pre_id)
            conn.commit()
        if pre:
            _registrar_rastreio_pre_orcamento(usuario, "Excluir pré-orçamento", pre)
        return jsonify({"sucesso": True, "mensagem": "Pré-orçamento excluído."})
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/api/pre-orcamentos/<int:pre_id>/converter-os", methods=["POST"])
def api_pre_orcamentos_converter_os(pre_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "pre_orcamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "pre_orcamentos_geral_gerar_os")
    if negado:
        return negado
    negado = _negar_sem_modulo(usuario, "ordem")
    if negado:
        return negado
    if _usuario_acesso_restrito(usuario):
        negado = _negar_sem_permissao(usuario, "ordem_os_geral_criar")
        if negado:
            return negado
    if _usuario_e_mecanico(usuario) and not _mecanico_pode_criar_os(usuario):
        return jsonify({
            "sucesso": False,
            "mensagem": "Você não tem permissão para criar novas O.S.",
        }), 403
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500
    try:
        with conexao_pre_orcamentos() as conn_pre:
            pre = obter_pre_orcamento(conn_pre, pre_id)
            if pre is None:
                return jsonify({"sucesso": False, "mensagem": "Pré-orçamento não encontrado."}), 404
            if pre.get("status") == STATUS_CONVERTIDO_OS:
                return jsonify({
                    "sucesso": False,
                    "mensagem": f"Já convertido na O.S. nº {pre.get('numero_os_gerado')}.",
                }), 400

        row_cli = None
        row_m = None
        with conexao_principal() as conn:
            _garantir_colunas_clientes(conn)
            _garantir_colunas_motores(conn)
            row_cli = _buscar_cliente_para_pre_orcamento(conn, pre)
            if pre.get("motor_id"):
                emb_sql = sql_embarcacao_motor("motores")
                row_m = conn.execute(
                    f"""
                    SELECT id, cliente_id, chassi, horas, marca_modelo,
                           {emb_sql} AS embarcacao, observacoes
                    FROM motores WHERE id = ?
                    """,
                    (int(pre["motor_id"]),),
                ).fetchone()

        nome_atendente = ""
        if usuario:
            nome_atendente = str(usuario.get("nome") or usuario.get("usuario") or "").strip()
        payload_os = montar_payload_os_de_pre_orcamento(
            pre,
            cliente_row=row_cli,
            motor_row=row_m,
            nome_atendente=nome_atendente,
        )
        corpo_conv = request.get_json(silent=True) or {}
        if corpo_conv.get("mecanico_id") not in (None, "", 0):
            payload_os["mecanico_id"] = corpo_conv.get("mecanico_id")

        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        init_ordens_servico()
        with conexao_banco() as conn:
            mecanico_id, mecanico_nome = _resolver_mecanico_os(conn, payload_os, usuario=usuario)
            if mecanico_id is None and usuario and _usuario_e_mecanico(usuario):
                try:
                    mecanico_id = int(usuario.get("id") or 0) or None
                except (TypeError, ValueError):
                    mecanico_id = None
                if mecanico_id:
                    mecanico_nome = str(
                        usuario.get("nome_exibicao") or usuario.get("usuario") or ""
                    ).strip() or None
            data_entrada = (payload_os.get("data_entrada") or "").strip() or None
            cliente_nome = (payload_os.get("cliente_nome") or "").strip() or None
            cliente_cpf_cnpj = (payload_os.get("cliente_cpf_cnpj") or "").strip() or None
            cliente_id_os = payload_os.get("cliente_id")
            if cliente_id_os in ("", None):
                cliente_id_os = None
            else:
                try:
                    cliente_id_os = int(cliente_id_os)
                except (TypeError, ValueError):
                    cliente_id_os = None
            numero_os = _proximo_numero_os(conn)
            dados_json = json.dumps(payload_os, ensure_ascii=False)
            conn.execute(
                """
                INSERT INTO ordens_servico (
                    numero_os, data_entrada, nome_atendente,
                    cliente_id, cliente_nome, cliente_cpf_cnpj,
                    status, assinatura_tecnico, assinatura_cliente,
                    mecanico_id, mecanico_nome,
                    dados_json, criado_em, atualizado_em
                ) VALUES (?, ?, ?, ?, ?, ?, 'aberto', NULL, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    numero_os,
                    data_entrada,
                    nome_atendente or None,
                    cliente_id_os,
                    cliente_nome,
                    cliente_cpf_cnpj,
                    mecanico_id,
                    mecanico_nome,
                    dados_json,
                    agora,
                    agora,
                ),
            )
            payload_os = _tentar_criar_requisicao_pre_orcamento(
                conn,
                numero_os=int(numero_os),
                mecanico_id=mecanico_id,
                mecanico_nome=mecanico_nome,
                payload_os=payload_os,
            )
            conn.execute(
                "UPDATE ordens_servico SET dados_json = ? WHERE numero_os = ?",
                (json.dumps(payload_os, ensure_ascii=False), int(numero_os)),
            )

        with conexao_pre_orcamentos() as conn_pre:
            pre_atualizado = marcar_pre_orcamento_convertido(
                conn_pre, pre_id, numero_os=int(numero_os)
            )

        _registrar_rastreio_pre_orcamento(
            usuario,
            "Converter em O.S.",
            pre_atualizado or pre,
            sufixo=f"O.S. nº {numero_os}",
        )
        return jsonify({
            "sucesso": True,
            "numero_os": numero_os,
            "pre_orcamento": pre_atualizado,
            "mensagem": f"O.S. nº {numero_os} criada a partir do {pre.get('numero')}.",
        })
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 400


@app.route("/pdf_pre_orcamento/<int:pre_id>")
def pdf_pre_orcamento(pre_id: int):
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401
    negado = _negar_sem_modulo(usuario, "pre_orcamentos")
    if negado:
        return negado
    negado = _negar_sem_permissao(usuario, "pre_orcamentos_geral_gerar_pdf")
    if negado:
        return negado
    try:
        with conexao_pre_orcamentos() as conn:
            pre = obter_pre_orcamento(conn, pre_id)
        if pre is None:
            return jsonify({"sucesso": False, "mensagem": "Pré-orçamento não encontrado."}), 404
        with conexao_principal() as conn_pr:
            empresa = _obter_empresa_config(conn_pr)
            logo = _obter_logo_empresa(conn_pr)
        pdf_bytes = gerar_pdf_pre_orcamento(pre, logo_dataurl=logo, empresa=empresa)
    except Exception as exc:
        return jsonify({"sucesso": False, "mensagem": f"Erro ao gerar PDF: {exc}"}), 500
    numero = str(pre.get("numero") or pre_id).replace("/", "-")
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"{numero}.pdf",
    )


@app.route("/buscar_cliente")
def buscar_cliente():
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_cadastros_clientes_busca(usuario)
    if negado:
        _, code = negado
        return jsonify({"encontrado": False, "mensagem": "Acesso negado."}), code
    termo = request.args.get("termo", request.args.get("q", "")).strip()
    if not termo:
        return jsonify({"encontrado": False, "mensagem": "Informe um nome ou CPF/CNPJ."}), 400

    if not DATABASE_PATH.is_file():
        return jsonify({"encontrado": False, "mensagem": "Banco de dados não encontrado."}), 500

    try:
        with conexao_principal() as conn:
            _garantir_colunas_clientes(conn)
            rows = _buscar_clientes_por_termo(conn, termo)
    except sqlite3.Error as exc:
        return jsonify({"encontrado": False, "mensagem": f"Erro ao consultar o banco: {exc}"}), 500

    if not rows:
        return jsonify({
            "encontrado": False,
            "mensagem": "Nenhum cliente encontrado com esse termo.",
        })

    clientes = [_cliente_para_json(row) for row in rows]
    resposta: dict[str, Any] = {
        "encontrado": True,
        "total": len(clientes),
        "clientes": clientes,
    }
    if len(clientes) == 1:
        resposta["cliente"] = clientes[0]
    return jsonify(resposta)


@app.route("/motores_cliente")
def motores_cliente():
    usuario = _usuario_logado()
    negado = _negar_sem_permissao_cadastros_motores_busca(usuario)
    if negado:
        _, code = negado
        return jsonify({"encontrado": False, "mensagem": "Acesso negado."}), code
    cliente_id = request.args.get("cliente_id", "").strip()
    if not cliente_id.isdigit():
        return jsonify({"encontrado": False, "mensagem": "Informe um cliente válido."}), 400

    if not DATABASE_PATH.is_file():
        return jsonify({"encontrado": False, "mensagem": "Banco de dados não encontrado."}), 500

    try:
        with conexao_principal() as conn:
            _garantir_colunas_motores(conn)
            emb_sql = sql_embarcacao_motor("motores")
            rows = conn.execute(
                f"""
                SELECT id, cliente_id, chassi, horas, marca_modelo, embarcacao, observacoes,
                       {emb_sql} AS embarcacao_exibir
                FROM motores
                WHERE cliente_id = ?
                ORDER BY marca_modelo, chassi, id
                """,
                (int(cliente_id),),
            ).fetchall()
    except sqlite3.Error as exc:
        return jsonify({"encontrado": False, "mensagem": f"Erro ao consultar motores: {exc}"}), 500

    motores = [_motor_para_json(row) for row in rows]
    return jsonify({
        "encontrado": True,
        "total": len(motores),
        "motores": motores,
    })


@app.route("/salvar_cliente", methods=["POST"])
def salvar_cliente():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401

    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500

    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return jsonify({"sucesso": False, "mensagem": "Dados inválidos."}), 400

    dados = _extrair_dados_cliente(payload)
    if not dados["nome"]:
        return jsonify({"sucesso": False, "mensagem": "Informe o nome do cliente."}), 400

    cliente_id = payload.get("cliente_id")
    if cliente_id in ("", None):
        cliente_id = None
    else:
        try:
            cliente_id = int(cliente_id)
        except (TypeError, ValueError):
            cliente_id = None

    if cliente_id:
        if not _usuario_pode_editar_cadastros_clientes(usuario):
            return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    elif not _usuario_pode_criar_cadastros_clientes(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403

    try:
        with conexao_principal() as conn:
            _garantir_colunas_clientes(conn)
            if cliente_id:
                cur = conn.execute(
                    """
                    UPDATE clientes
                    SET nome = ?, telefone = ?, celular = ?, email = ?, cpf_cnpj = ?, rg = ?,
                        endereco = ?, numero = ?, bairro = ?, cidade = ?, estado = ?, cep = ?
                    WHERE id = ?
                    """,
                    (
                        dados["nome"],
                        dados["telefone"],
                        dados["celular"],
                        dados["email"],
                        dados["cpf_cnpj"],
                        dados["rg"],
                        dados["endereco"],
                        dados["numero"],
                        dados["bairro"],
                        dados["cidade"],
                        dados["estado"],
                        dados["cep"],
                        cliente_id,
                    ),
                )
                if cur.rowcount == 0:
                    return jsonify({"sucesso": False, "mensagem": "Cliente não encontrado."}), 404
                novo_id = cliente_id
                acao = "atualizado"
            else:
                cur = conn.execute(
                    """
                    INSERT INTO clientes (
                        nome, telefone, celular, email, cpf_cnpj, rg,
                        endereco, numero, bairro, cidade, estado, cep
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dados["nome"],
                        dados["telefone"],
                        dados["celular"],
                        dados["email"],
                        dados["cpf_cnpj"],
                        dados["rg"],
                        dados["endereco"],
                        dados["numero"],
                        dados["bairro"],
                        dados["cidade"],
                        dados["estado"],
                        dados["cep"],
                    ),
                )
                novo_id = int(cur.lastrowid)
                acao = "cadastrado"
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": f"Erro ao salvar cliente: {exc}"}), 500

    _registrar_acao_rastreio(
        usuario,
        "Cadastros",
        "Editar cliente" if acao == "atualizado" else "Criar cliente",
        dados["nome"] or f"Cliente #{novo_id}",
    )

    return jsonify({
        "sucesso": True,
        "mensagem": f"Cliente {acao} com sucesso (ID {novo_id}).",
        "cliente_id": novo_id,
    })


@app.route("/salvar_motor", methods=["POST"])
def salvar_motor():
    usuario = _usuario_logado()
    if not usuario:
        return jsonify({"sucesso": False, "mensagem": "Faça login."}), 401

    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500

    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return jsonify({"sucesso": False, "mensagem": "Dados inválidos."}), 400

    cliente_id = payload.get("cliente_id")
    try:
        cliente_id = int(cliente_id)
    except (TypeError, ValueError):
        return jsonify({"sucesso": False, "mensagem": "Salve ou selecione um cliente antes do motor."}), 400

    chassi = (payload.get("num_chassi") or payload.get("chassi") or "").strip() or None
    horas = _parse_horas(payload.get("horas_uso") or payload.get("horas"))
    marca_modelo = _marca_modelo_de_form(payload)
    embarcacao = (
        (payload.get("embarcacao_nome") or payload.get("embarcacao") or "").strip() or None
    )
    observacoes = (payload.get("motor_observacoes") or "").strip() or None

    motor_id = payload.get("motor_id")
    if motor_id in ("", None):
        motor_id = None
    else:
        try:
            motor_id = int(motor_id)
        except (TypeError, ValueError):
            motor_id = None

    if motor_id:
        if not _usuario_pode_editar_cadastros_motores(usuario):
            return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403
    elif not _usuario_pode_criar_cadastros_motores(usuario):
        return jsonify({"sucesso": False, "mensagem": "Acesso negado."}), 403

    try:
        with conexao_principal() as conn:
            _garantir_colunas_motores(conn)
            existe = conn.execute(
                "SELECT id FROM clientes WHERE id = ?", (cliente_id,)
            ).fetchone()
            if not existe:
                return jsonify({"sucesso": False, "mensagem": "Cliente não encontrado."}), 404

            emb_sql = sql_embarcacao_motor("motores")
            if motor_id:
                cur = conn.execute(
                    """
                    UPDATE motores
                    SET cliente_id = ?, chassi = ?, horas = ?, marca_modelo = ?,
                        embarcacao = ?, observacoes = ?
                    WHERE id = ?
                    """,
                    (cliente_id, chassi, horas, marca_modelo, embarcacao, observacoes, motor_id),
                )
                if cur.rowcount == 0:
                    return jsonify({"sucesso": False, "mensagem": "Motor não encontrado."}), 404
                novo_id = motor_id
                acao = "atualizado"
            else:
                cur = conn.execute(
                    """
                    INSERT INTO motores (cliente_id, chassi, horas, marca_modelo, embarcacao, observacoes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (cliente_id, chassi, horas, marca_modelo, embarcacao, observacoes),
                )
                novo_id = int(cur.lastrowid)
                acao = "cadastrado"

            row = conn.execute(
                f"""
                SELECT id, cliente_id, chassi, horas, marca_modelo, embarcacao, observacoes,
                       {emb_sql} AS embarcacao_exibir
                FROM motores WHERE id = ?
                """,
                (novo_id,),
            ).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({
            "sucesso": False,
            "mensagem": "Já existe um motor com esse número de chassi.",
        }), 409
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": f"Erro ao salvar motor: {exc}"}), 500

    rotulo_motor = marca_modelo or chassi or f"Motor #{novo_id}"
    _registrar_acao_rastreio(
        usuario,
        "Cadastros",
        "Editar motor" if acao == "atualizado" else "Criar motor",
        rotulo_motor,
    )

    return jsonify({
        "sucesso": True,
        "mensagem": f"Motor {acao} com sucesso (ID {novo_id}).",
        "motor_id": novo_id,
        "motor": _motor_para_json(row) if row else None,
    })


@app.route("/salvar_os", methods=["POST"])
def salvar_os():
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500

    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return jsonify({"sucesso": False, "mensagem": "Dados inválidos."}), 400

    usuario = _usuario_logado()

    cliente_id = payload.get("cliente_id")
    if cliente_id in ("", None):
        cliente_id = None
    else:
        try:
            cliente_id = int(cliente_id)
        except (TypeError, ValueError):
            cliente_id = None

    numero_os_existente = payload.get("numero_os")
    if numero_os_existente in ("", None):
        numero_os_existente = None
    else:
        try:
            numero_os_existente = int(numero_os_existente)
        except (TypeError, ValueError):
            numero_os_existente = None

    negado = _negar_sem_modulo(usuario, "ordem")
    if negado:
        return negado
    if _usuario_acesso_restrito(usuario):
        if numero_os_existente is None:
            negado = _negar_sem_permissao(usuario, "ordem_os_geral_criar")
        else:
            negado = _negar_sem_permissao(usuario, "ordem_os_geral_editar")
        if negado:
            return negado

    if _usuario_e_mecanico(usuario) and numero_os_existente is None:
        if not _mecanico_pode_criar_os(usuario):
            return jsonify({
                "sucesso": False,
                "mensagem": "Você não tem permissão para criar novas O.S.",
            }), 403

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sync_status_oficina: str | None = None
    sync_dados_json_oficina: str | None = None

    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            if numero_os_existente is not None:
                row_existente = conn.execute(
                    """
                    SELECT numero_os, mecanico_id, mecanico_nome, dados_json,
                           assinatura_tecnico, assinatura_cliente, status
                    FROM ordens_servico WHERE numero_os = ?
                    """,
                    (numero_os_existente,),
                ).fetchone()
                if row_existente is None:
                    return jsonify({
                        "sucesso": False,
                        "mensagem": f"O.S. nº {numero_os_existente} não encontrada para atualizar.",
                    }), 404
                if _mecanico_bloqueado_por_pausa(
                    usuario, row_existente["status"], row_existente["mecanico_id"]
                ):
                    return jsonify({
                        "sucesso": False,
                        "mensagem": (
                            "Esta O.S. está em pausa. Aguarde o responsável retomar o serviço."
                        ),
                    }), 403
                if not _usuario_pode_editar_os(usuario, row_existente["mecanico_id"]):
                    return jsonify({
                        "sucesso": False,
                        "mensagem": "Você não tem permissão para editar esta O.S.",
                    }), 403

                mecanico_id, mecanico_nome = _resolver_mecanico_os(
                    conn,
                    payload,
                    usuario=usuario,
                    mecanico_atual_id=row_existente["mecanico_id"],
                    mecanico_atual_nome=row_existente["mecanico_nome"],
                )

                if _usuario_e_mecanico(usuario):
                    dados_antigos, _ = dados_os_de_registro(
                        row_existente,
                        assinatura_tecnico=row_existente["assinatura_tecnico"],
                        assinatura_cliente=row_existente["assinatura_cliente"],
                    )
                    if (not _mecanico_pode_editar_os_existente(usuario)
                            or _payload_salvo_parcial_mecanico(payload)):
                        payload = _mesclar_payload_mecanico(payload, dados_antigos)
                        if not _mecanico_pode_editar_os_existente(usuario):
                            mecanico_id = row_existente["mecanico_id"]
                            mecanico_nome = row_existente["mecanico_nome"]
                    dados_para_assinatura = dados_antigos
                else:
                    dados_para_assinatura, _ = dados_os_de_registro(
                        row_existente,
                        assinatura_tecnico=row_existente["assinatura_tecnico"],
                        assinatura_cliente=row_existente["assinatura_cliente"],
                    )

                payload = _preservar_metadados_os_payload(payload, dados_para_assinatura)

                _preservar_assinaturas_colunas_payload(
                    payload, row_existente, dados_para_assinatura
                )

                assinatura_tecnico = _extrair_assinatura(payload, "assinatura_tecnico")
                assinatura_cliente = _extrair_assinatura(payload, "assinatura_cliente")
                data_entrada = (payload.get("data_entrada") or "").strip() or None
                nome_atendente = (payload.get("nome_atendente") or "").strip() or None
                cliente_nome = (payload.get("cliente_nome") or "").strip() or None
                cliente_cpf_cnpj = (payload.get("cliente_cpf_cnpj") or "").strip() or None
                dados_json = json.dumps(payload, ensure_ascii=False)

                conn.execute(
                    """
                    UPDATE ordens_servico SET
                        data_entrada = ?, nome_atendente = ?,
                        cliente_id = ?, cliente_nome = ?, cliente_cpf_cnpj = ?,
                        assinatura_tecnico = ?, assinatura_cliente = ?,
                        mecanico_id = ?, mecanico_nome = ?,
                        dados_json = ?, atualizado_em = ?
                    WHERE numero_os = ?
                    """,
                    (
                        data_entrada,
                        nome_atendente,
                        cliente_id,
                        cliente_nome,
                        cliente_cpf_cnpj,
                        assinatura_tecnico,
                        assinatura_cliente,
                        mecanico_id,
                        mecanico_nome,
                        dados_json,
                        agora,
                        numero_os_existente,
                    ),
                )
                if mecanico_id:
                    payload = _tentar_criar_requisicao_pre_orcamento(
                        conn,
                        numero_os=int(numero_os_existente),
                        mecanico_id=mecanico_id,
                        mecanico_nome=mecanico_nome,
                        payload_os=payload,
                    )
                    conn.execute(
                        "UPDATE ordens_servico SET dados_json = ? WHERE numero_os = ?",
                        (
                            json.dumps(payload, ensure_ascii=False),
                            int(numero_os_existente),
                        ),
                    )
                marcar_os_entregue_se_assinada(conn, numero_os_existente, payload)
                marcar_requisicao_aprovada_se_assinada(conn, numero_os_existente, payload)
                if tem_assinatura_entrega_os(payload):
                    sync_status_oficina = "entregue"
                    sync_dados_json_oficina = dados_json
                numero_os = numero_os_existente
                mensagem = f"Ordem de Serviço nº {numero_os} atualizada com sucesso."
            else:
                mecanico_id, mecanico_nome = _resolver_mecanico_os(conn, payload, usuario=usuario)
                assinatura_tecnico = _extrair_assinatura(payload, "assinatura_tecnico")
                assinatura_cliente = _extrair_assinatura(payload, "assinatura_cliente")
                data_entrada = (payload.get("data_entrada") or "").strip() or None
                nome_atendente = (payload.get("nome_atendente") or "").strip() or None
                cliente_nome = (payload.get("cliente_nome") or "").strip() or None
                cliente_cpf_cnpj = (payload.get("cliente_cpf_cnpj") or "").strip() or None
                numero_os = _proximo_numero_os(conn)
                dados_json = json.dumps(payload, ensure_ascii=False)
                conn.execute(
                    """
                    INSERT INTO ordens_servico (
                        numero_os, data_entrada, nome_atendente,
                        cliente_id, cliente_nome, cliente_cpf_cnpj,
                        status, assinatura_tecnico, assinatura_cliente,
                        mecanico_id, mecanico_nome,
                        dados_json, criado_em, atualizado_em
                    ) VALUES (?, ?, ?, ?, ?, ?, 'aberto', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        numero_os,
                        data_entrada,
                        nome_atendente,
                        cliente_id,
                        cliente_nome,
                        cliente_cpf_cnpj,
                        assinatura_tecnico,
                        assinatura_cliente,
                        mecanico_id,
                        mecanico_nome,
                        dados_json,
                        agora,
                        agora,
                    ),
                )
                if mecanico_id:
                    payload = _tentar_criar_requisicao_pre_orcamento(
                        conn,
                        numero_os=int(numero_os),
                        mecanico_id=mecanico_id,
                        mecanico_nome=mecanico_nome,
                        payload_os=payload,
                    )
                    conn.execute(
                        "UPDATE ordens_servico SET dados_json = ? WHERE numero_os = ?",
                        (json.dumps(payload, ensure_ascii=False), int(numero_os)),
                    )
                mensagem = f"Ordem de Serviço nº {numero_os} salva com sucesso."
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": f"Erro ao salvar a O.S.: {exc}"}), 500

    if sync_status_oficina and numero_os:
        _sync_oficina_status_os(
            int(numero_os),
            sync_status_oficina,
            dados_json=sync_dados_json_oficina,
        )

    agendamento_id_raw = payload.get("agendamento_id")
    ag_convertido: dict[str, Any] | None = None
    if agendamento_id_raw not in (None, "", 0) and DATABASE_PRINCIPAL_PATH.is_file():
        try:
            ag_id = int(agendamento_id_raw)
            if ag_id > 0:
                init_agendamentos()
                with conexao_principal() as conn:
                    ag_convertido = marcar_virou_os(conn, ag_id)
        except (TypeError, ValueError, sqlite3.Error):
            pass

    ori_param = "horizontal" if _orientacao_pdf() == "L" else "vertical"
    acao_os = "Atualização de O.S." if numero_os_existente is not None else "Criação de O.S."
    _registrar_acao_rastreio(
        usuario,
        "Ordem de Serviço",
        acao_os,
        f"O.S. nº {numero_os}",
    )
    if ag_convertido:
        _registrar_rastreio_agendamento(
            usuario,
            "Conversão em O.S.",
            ag_convertido,
            sufixo=f"O.S. nº {numero_os}",
        )
    return jsonify({
        "sucesso": True,
        "mensagem": mensagem,
        "numero_os": numero_os,
        "pdf_url": f"/pdf_os/{numero_os}?orientacao={ori_param}",
        "atualizada": numero_os_existente is not None,
    })


@app.route("/pdf_os/<int:numero_os>")
def pdf_os(numero_os: int):
    """Gera e baixa o PDF de uma O.S. salva."""
    if not DATABASE_PATH.is_file():
        return jsonify({"sucesso": False, "mensagem": "Banco de dados não encontrado."}), 500

    try:
        init_ordens_servico()
        with conexao_banco() as conn:
            row = conn.execute(
                """
                SELECT numero_os, dados_json, assinatura_tecnico, assinatura_cliente
                FROM ordens_servico WHERE numero_os = ?
                """,
                (numero_os,),
            ).fetchone()
            if row is None:
                return jsonify({"sucesso": False, "mensagem": "O.S. não encontrada."}), 404
            empresa, app_cfg = _empresa_e_config_app()
            dados, num = dados_os_de_registro(
                row,
                assinatura_tecnico=row["assinatura_tecnico"],
                assinatura_cliente=row["assinatura_cliente"],
            )
            itens_chk = carregar_itens_checklist_os(conn, numero_os)
            pdf_bytes = gerar_pdf_ordem_servico(
                dados,
                numero_os=num,
                assinatura_tecnico=row["assinatura_tecnico"],
                assinatura_cliente=row["assinatura_cliente"],
                empresa=empresa,
                orientacao=_orientacao_pdf(),
                config=app_cfg,
                itens_checklist=itens_chk,
            )
    except sqlite3.Error as exc:
        return jsonify({"sucesso": False, "mensagem": str(exc)}), 500
    except Exception as exc:
        return jsonify({"sucesso": False, "mensagem": f"Erro ao gerar PDF: {exc}"}), 500

    ori_suffix = "H" if _orientacao_pdf() == "L" else "V"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"OS_{numero_os:04d}_{ori_suffix}.pdf",
    )


@app.route("/gerar_pdf", methods=["POST"])
def gerar_pdf():
    """Gera PDF a partir do formulário atual (sem exigir salvar antes)."""
    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return jsonify({"sucesso": False, "mensagem": "Dados inválidos."}), 400

    numero = payload.get("numero_os") or payload.get("orcamento_numero") or "RASCUNHO"
    try:
        empresa, app_cfg = _empresa_e_config_app()
        pdf_bytes = gerar_pdf_ordem_servico(
            payload,
            numero_os=numero,
            assinatura_tecnico=_extrair_assinatura(payload, "assinatura_tecnico"),
            assinatura_cliente=_extrair_assinatura(payload, "assinatura_cliente"),
            empresa=empresa,
            orientacao=_orientacao_pdf(),
            config=app_cfg,
            itens_checklist=None,
        )
    except Exception as exc:
        return jsonify({"sucesso": False, "mensagem": f"Erro ao gerar PDF: {exc}"}), 500

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"OS_{numero}.pdf",
    )


# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------

def init_agendamentos() -> None:
    """Garante tabela de agendamentos no banco principal (clientes/motores)."""
    if not DATABASE_PRINCIPAL_PATH.is_file():
        return
    with conexao_principal() as conn:
        init_agendamentos_tabelas(conn)


with app.app_context():
    if DATABASE_PRINCIPAL_PATH.is_file():
        with conexao_principal() as conn:
            _garantir_colunas_clientes(conn)
            _garantir_colunas_motores(conn)
            _init_usuarios(conn)
            _init_app_os_config(conn)
            init_agendamentos_tabelas(conn)
            init_atividade_log(conn)
        init_ordens_servico()
        init_assinaturas_remotas()
    garantir_banco_teste(DATABASE_TESTE_PATH)
    garantir_banco_sandbox(DATABASE_SANDBOX_TREINAMENTO_PATH)
    garantir_banco_pre_orcamentos(DATABASE_PRE_ORCAMENTOS_PATH)


if __name__ == "__main__":
    import logging
    from werkzeug.serving import WSGIRequestHandler

    class _HandlerSilenciosoAssinatura(WSGIRequestHandler):
        """Oculta logs repetitivos do polling de assinatura remota (a cada poucos segundos)."""

        def log_request(self, code: str = "-", size: str = "-") -> None:
            if (
                self.command == "GET"
                and str(code) == "200"
                and self.path.startswith("/api/assinatura/")
            ):
                return
            super().log_request(code, size)

    # host="0.0.0.0" = acesso pelo celular/tablet na mesma rede Wi-Fi
    # use_reloader=False evita queda de conexão no modo debug (comum no celular)
    app.run(
        debug=True,
        host=os.getenv("SERVIDOR_HOST", "0.0.0.0"),
        port=int(os.getenv("SERVIDOR_PORTA", "5000") or "5000"),
        use_reloader=False,
        request_handler=_HandlerSilenciosoAssinatura,
    )

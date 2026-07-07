"""Rastreio de atividade — histórico de ações no O.S. Digital (espelha Sistema Oficina)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Callable

ATIVIDADE_ORDEM_CATEGORIAS: tuple[str, ...] = (
    "Ordem de Serviço",
    "Requisições",
    "Lista de O.S.",
    "Controle de terceiro",
    "Agendamentos",
    "Estoque",
    "Cadastros",
    "Fotos O.S.",
    "Configurações",
    "Sistema",
    "Outros",
)

_CHAVE_RASTREIO_CONTROLE_TERCEIRO = "rastreio_controle_terceiro_ativo"
_ORIGEM_APP_OS = "app_os"

# Categorias típicas do Sistema Oficina (registros legados sem coluna origem).
_CATEGORIAS_SISTEMA_OFICINA: frozenset[str] = frozenset({
    "Dashboard",
    "Atendimento",
    "Gerenciador",
    "Novo Orçamento",
    "Controle de O.S.",
})


def init_atividade_log(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS atividade_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            usuario_login TEXT NOT NULL DEFAULT '',
            nome_exibicao TEXT NOT NULL DEFAULT '',
            acao TEXT NOT NULL,
            detalhe TEXT NOT NULL DEFAULT '',
            criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_atividade_log_criado_em
        ON atividade_log (criado_em DESC, id DESC)
        """
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(atividade_log)").fetchall()}
    if "categoria" not in cols:
        conn.execute("ALTER TABLE atividade_log ADD COLUMN categoria TEXT NOT NULL DEFAULT ''")
    if "subcategoria" not in cols:
        conn.execute("ALTER TABLE atividade_log ADD COLUMN subcategoria TEXT NOT NULL DEFAULT ''")
    if "origem" not in cols:
        conn.execute("ALTER TABLE atividade_log ADD COLUMN origem TEXT NOT NULL DEFAULT ''")


def _garantir_chave_rastreio_controle_terceiro(conn: sqlite3.Connection) -> None:
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
        (_CHAVE_RASTREIO_CONTROLE_TERCEIRO, "0"),
    )


def _formatar_data_hora(texto: str) -> str:
    raw = str(texto or "").strip()
    if not raw:
        return ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw[:19], fmt).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            continue
    return raw


def inferir_categoria_subcategoria_atividade(acao: str) -> tuple[str, str]:
    txt = (acao or "").strip().lower()
    if not txt:
        return "Outros", "Geral"
    if "login" in txt:
        return "Sistema", "Login"
    if "logout" in txt or "saiu" in txt:
        return "Sistema", "Logout"
    if "requis" in txt:
        return "Requisições", "Alteração"
    if "orçamento" in txt or "orcamento" in txt:
        return "Requisições", "Orçamento"
    if "pdf" in txt:
        return "Ordem de Serviço", "Geração de PDF"
    if any(x in txt for x in ("o.s.", "os ", "ordem")):
        return "Ordem de Serviço", "Alteração"
    if "config" in txt:
        return "Configurações", "Configuração"
    return "Outros", (acao or "Geral").strip()[:80]


def registrar_atividade(
    conn: sqlite3.Connection,
    *,
    usuario_id: int | None = None,
    usuario_login: str = "",
    nome_exibicao: str = "",
    categoria: str = "",
    subcategoria: str = "",
    detalhe: str = "",
    acao: str = "",
) -> None:
    init_atividade_log(conn)
    cat = (categoria or "").strip() or "Outros"
    sub = (subcategoria or "").strip() or "Geral"
    acao_txt = (acao or sub).strip() or sub
    detalhe_txt = (detalhe or "").strip()
    login = (usuario_login or "").strip()
    nome = (nome_exibicao or login or "—").strip().upper()
    uid = int(usuario_id) if usuario_id is not None and int(usuario_id) > 0 else None
    conn.execute(
        """
        INSERT INTO atividade_log (
            usuario_id, usuario_login, nome_exibicao,
            categoria, subcategoria, acao, detalhe, origem
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (uid, login, nome, cat, sub, acao_txt, detalhe_txt, _ORIGEM_APP_OS),
    )


def _registro_e_do_app_os(row: dict[str, Any]) -> bool:
    origem = str(row.get("origem") or "").strip().lower()
    if origem == _ORIGEM_APP_OS:
        return True
    if origem and origem != _ORIGEM_APP_OS:
        return False
    cat = str(row.get("categoria") or "").strip()
    if cat in _CATEGORIAS_SISTEMA_OFICINA:
        return False
    return True


def listar_atividades(
    conn: sqlite3.Connection,
    *,
    limite: int = 1000,
    apenas_app_os: bool = True,
) -> list[dict[str, Any]]:
    init_atividade_log(conn)
    n = max(1, min(int(limite), 5000))
    rows = conn.execute(
        """
        SELECT id, usuario_id, usuario_login, nome_exibicao,
               categoria, subcategoria, acao, detalhe, criado_em, origem
        FROM atividade_log
        ORDER BY criado_em DESC, id DESC
        LIMIT ?
        """,
        (n,),
    ).fetchall()
    saida: list[dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        if apenas_app_os and not _registro_e_do_app_os(d):
            continue
        cat = str(d.get("categoria") or "").strip()
        sub = str(d.get("subcategoria") or "").strip()
        if not cat or not sub:
            cat_inf, sub_inf = inferir_categoria_subcategoria_atividade(str(d.get("acao") or ""))
            cat = cat or cat_inf
            sub = sub or sub_inf
        d["categoria"] = cat
        d["subcategoria"] = sub
        d["quando"] = _formatar_data_hora(str(d.get("criado_em") or ""))
        saida.append(d)
    return saida


def excluir_atividade(conn: sqlite3.Connection, atividade_id: int) -> bool:
    init_atividade_log(conn)
    cur = conn.execute("DELETE FROM atividade_log WHERE id = ?", (int(atividade_id),))
    return cur.rowcount > 0


def limpar_atividades(conn: sqlite3.Connection) -> int:
    init_atividade_log(conn)
    cur = conn.execute("DELETE FROM atividade_log")
    return int(cur.rowcount or 0)


def rastreio_controle_terceiro_ativo(conn: sqlite3.Connection) -> bool:
    _garantir_chave_rastreio_controle_terceiro(conn)
    row = conn.execute(
        "SELECT valor FROM app_os_config WHERE chave = ?",
        (_CHAVE_RASTREIO_CONTROLE_TERCEIRO,),
    ).fetchone()
    if row is None:
        return False
    return str(row["valor"] or "").strip().lower() in ("1", "true", "sim", "yes", "on")


def definir_rastreio_controle_terceiro(conn: sqlite3.Connection, ativo: bool) -> None:
    _garantir_chave_rastreio_controle_terceiro(conn)
    conn.execute(
        "INSERT OR REPLACE INTO app_os_config (chave, valor) VALUES (?, ?)",
        (_CHAVE_RASTREIO_CONTROLE_TERCEIRO, "1" if ativo else "0"),
    )

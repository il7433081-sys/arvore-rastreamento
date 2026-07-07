"""Perfis de usuário do O.S. Digital — predefinidos e personalizados."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from permissoes_arvore_os import (
    normalizar_permissoes_granulares,
    permissoes_granulares_vazias,
    permissoes_template_por_modelo,
    serializar_permissoes_granulares,
)

MODELOS_BASE_VALIDOS: tuple[str, ...] = (
    "admin",
    "mecanico",
    "atendente",
    "operador",
    "personalizado",
)


def _normalizar_modelo_base(valor: Any) -> str:
    modelo = str(valor or "personalizado").strip().lower()
    if modelo not in MODELOS_BASE_VALIDOS:
        return "personalizado"
    return modelo


def init_perfis_app(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS perfis_app (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL COLLATE NOCASE UNIQUE,
            modelo_base TEXT NOT NULL DEFAULT 'personalizado',
            permissoes_granulares TEXT NOT NULL DEFAULT '{}',
            eh_sistema INTEGER NOT NULL DEFAULT 0 CHECK (eh_sistema IN (0, 1)),
            criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    _garantir_perfis_sistema(conn)


def _garantir_perfis_sistema(conn: sqlite3.Connection) -> None:
    sistema = (
        ("Administrador", "admin"),
        ("Mecânico", "mecanico"),
        ("Atendente / Estoque", "atendente"),
        ("Operador (legado)", "operador"),
    )
    for nome, modelo in sistema:
        gran = permissoes_template_por_modelo(modelo)
        conn.execute(
            """
            INSERT OR IGNORE INTO perfis_app (
                nome, modelo_base, permissoes_granulares, eh_sistema
            ) VALUES (?, ?, ?, 1)
            """,
            (nome, modelo, serializar_permissoes_granulares(gran)),
        )
        conn.execute(
            """
            UPDATE perfis_app
            SET modelo_base = ?, eh_sistema = 1
            WHERE nome = ? COLLATE NOCASE
            """,
            (modelo, nome),
        )


def _perfil_para_json(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    gran = normalizar_permissoes_granulares(d.get("permissoes_granulares"))
    modelo = _normalizar_modelo_base(d.get("modelo_base"))
    return {
        "id": int(d["id"]),
        "nome": str(d.get("nome") or "").strip(),
        "modelo_base": modelo,
        "permissoes_granulares": gran,
        "eh_sistema": bool(int(d.get("eh_sistema") or 0)),
        "criado_em": str(d.get("criado_em") or ""),
    }


def listar_perfis_app(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    init_perfis_app(conn)
    rows = conn.execute(
        """
        SELECT id, nome, modelo_base, permissoes_granulares, eh_sistema, criado_em
        FROM perfis_app
        ORDER BY eh_sistema DESC, nome COLLATE NOCASE ASC
        """
    ).fetchall()
    return [_perfil_para_json(row) for row in rows]


def buscar_perfil_app_por_id(
    conn: sqlite3.Connection,
    perfil_id: int,
) -> dict[str, Any] | None:
    init_perfis_app(conn)
    row = conn.execute(
        """
        SELECT id, nome, modelo_base, permissoes_granulares, eh_sistema, criado_em
        FROM perfis_app
        WHERE id = ?
        """,
        (int(perfil_id),),
    ).fetchone()
    return _perfil_para_json(row) if row else None


def buscar_perfil_app_por_modelo(
    conn: sqlite3.Connection,
    modelo_base: str,
) -> dict[str, Any] | None:
    init_perfis_app(conn)
    modelo = _normalizar_modelo_base(modelo_base)
    if modelo == "personalizado":
        return None
    row = conn.execute(
        """
        SELECT id, nome, modelo_base, permissoes_granulares, eh_sistema, criado_em
        FROM perfis_app
        WHERE modelo_base = ? AND eh_sistema = 1
        ORDER BY id ASC
        LIMIT 1
        """,
        (modelo,),
    ).fetchone()
    return _perfil_para_json(row) if row else None


def criar_perfil_app(
    conn: sqlite3.Connection,
    *,
    nome: str,
    modelo_base: str = "personalizado",
    permissoes_granulares: dict[str, bool] | None = None,
) -> int:
    init_perfis_app(conn)
    nome_norm = (nome or "").strip()
    if not nome_norm:
        raise ValueError("Informe o nome do perfil.")
    modelo = _normalizar_modelo_base(modelo_base)
    gran = normalizar_permissoes_granulares(permissoes_granulares or {})
    if modelo != "admin" and not any(gran.values()):
        raise ValueError("Marque ao menos uma permissão para o perfil.")
    try:
        cur = conn.execute(
            """
            INSERT INTO perfis_app (nome, modelo_base, permissoes_granulares, eh_sistema)
            VALUES (?, ?, ?, 0)
            """,
            (nome_norm, modelo, serializar_permissoes_granulares(gran)),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError(f'Já existe um perfil com o nome "{nome_norm}".') from exc
    return int(cur.lastrowid)


def atualizar_perfil_app(
    conn: sqlite3.Connection,
    perfil_id: int,
    *,
    nome: str | None = None,
    modelo_base: str | None = None,
    permissoes_granulares: dict[str, bool] | None = None,
) -> None:
    init_perfis_app(conn)
    atual = buscar_perfil_app_por_id(conn, perfil_id)
    if atual is None:
        raise ValueError("Perfil não encontrado.")
    if atual["eh_sistema"] and nome is not None:
        raise ValueError("Perfis predefinidos do sistema não podem ser renomeados.")
    campos: list[str] = []
    valores: list[Any] = []
    if nome is not None:
        nome_norm = nome.strip()
        if not nome_norm:
            raise ValueError("Informe o nome do perfil.")
        campos.append("nome = ?")
        valores.append(nome_norm)
    if modelo_base is not None:
        campos.append("modelo_base = ?")
        valores.append(_normalizar_modelo_base(modelo_base))
    if permissoes_granulares is not None:
        gran = normalizar_permissoes_granulares(permissoes_granulares)
        if not any(gran.values()) and atual["modelo_base"] != "admin":
            raise ValueError("Marque ao menos uma permissão para o perfil.")
        campos.append("permissoes_granulares = ?")
        valores.append(serializar_permissoes_granulares(gran))
    if not campos:
        return
    valores.append(int(perfil_id))
    try:
        conn.execute(
            f"UPDATE perfis_app SET {', '.join(campos)} WHERE id = ?",
            valores,
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("Já existe outro perfil com este nome.") from exc


def excluir_perfil_app(conn: sqlite3.Connection, perfil_id: int) -> None:
    init_perfis_app(conn)
    row = conn.execute(
        "SELECT id, eh_sistema FROM perfis_app WHERE id = ?",
        (int(perfil_id),),
    ).fetchone()
    if row is None:
        raise ValueError("Perfil não encontrado.")
    if int(row["eh_sistema"] or 0):
        raise ValueError("Perfis predefinidos do sistema não podem ser excluídos.")
    em_uso = conn.execute(
        "SELECT COUNT(*) FROM usuarios WHERE perfil_id = ?",
        (int(perfil_id),),
    ).fetchone()[0]
    if int(em_uso or 0) > 0:
        raise ValueError("Este perfil está em uso por usuários cadastrados.")
    conn.execute("DELETE FROM perfis_app WHERE id = ?", (int(perfil_id),))


def permissoes_do_perfil_app(perfil: dict[str, Any] | None) -> dict[str, bool]:
    if not perfil:
        return permissoes_granulares_vazias()
    gran = normalizar_permissoes_granulares(perfil.get("permissoes_granulares"))
    if any(gran.values()):
        return gran
    return permissoes_template_por_modelo(str(perfil.get("modelo_base") or ""))

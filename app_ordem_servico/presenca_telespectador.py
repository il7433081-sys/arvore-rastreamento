"""Presença em tempo real e permissão telespectador (acompanhar atividade de usuários)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

PRESENCA_TTL_SEGUNDOS = 12


def init_presenca_tabelas(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS presenca_usuario (
            usuario_id INTEGER PRIMARY KEY,
            modulo TEXT NOT NULL DEFAULT '',
            aba TEXT NOT NULL DEFAULT '',
            contexto TEXT NOT NULL DEFAULT '',
            detalhe TEXT NOT NULL DEFAULT '',
            perfil_observado_id INTEGER,
            perfil_observado_nome TEXT,
            numero_os INTEGER,
            atualizado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_presenca_atualizado ON presenca_usuario(atualizado_em);
        """
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(usuarios)").fetchall()}
    if "permissao_telespectador" not in cols:
        conn.execute(
            "ALTER TABLE usuarios ADD COLUMN permissao_telespectador INTEGER NOT NULL DEFAULT 0"
        )
    if "telespectador_alvos_json" not in cols:
        conn.execute("ALTER TABLE usuarios ADD COLUMN telespectador_alvos_json TEXT")
    pres_cols = {r[1] for r in conn.execute("PRAGMA table_info(presenca_usuario)").fetchall()}
    if pres_cols and "sandbox_treinamento_ativo" not in pres_cols:
        conn.execute(
            "ALTER TABLE presenca_usuario ADD COLUMN sandbox_treinamento_ativo INTEGER NOT NULL DEFAULT 0"
        )


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_alvos_json(raw: str | None) -> list[int] | None:
    if not raw or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    ids: list[int] = []
    for item in data:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return ids or None


def alvos_telespectador_de_usuario(usuario: dict[str, Any] | None) -> list[int] | None:
    if not usuario:
        return None
    return _parse_alvos_json(usuario.get("telespectador_alvos_json"))


def usuario_deve_ser_rastreado(usuario: dict[str, Any] | None) -> bool:
    """Administrador não é rastreado (por enquanto)."""
    if not usuario:
        return False
    return str(usuario.get("perfil") or "").strip().lower() != "admin"


def usuario_pode_telespectar(usuario: dict[str, Any] | None) -> bool:
    if not usuario:
        return False
    if str(usuario.get("perfil") or "").strip().lower() == "admin":
        return True
    return bool(usuario.get("permissao_telespectador"))


def espectador_pode_ver_alvo(
    espectador: dict[str, Any] | None,
    *,
    alvo_id: int,
    alvo_perfil: str,
) -> bool:
    if not usuario_pode_telespectar(espectador):
        return False
    if str(alvo_perfil or "").strip().lower() == "admin":
        return False
    if str(espectador.get("perfil") or "").strip().lower() == "admin":
        return True
    alvos = alvos_telespectador_de_usuario(espectador)
    if alvos:
        return int(alvo_id) in alvos
    return True


def remover_presenca_usuario(conn: sqlite3.Connection, usuario_id: int) -> None:
    """Remove registro de presença — usuário saiu do app ou perdeu foco da tela."""
    conn.execute(
        "DELETE FROM presenca_usuario WHERE usuario_id = ?",
        (int(usuario_id),),
    )


def atualizar_presenca_usuario(
    conn: sqlite3.Connection,
    usuario_id: int,
    *,
    modulo: str = "",
    aba: str = "",
    contexto: str = "",
    detalhe: str = "",
    perfil_observado_id: int | None = None,
    perfil_observado_nome: str = "",
    numero_os: int | None = None,
    sandbox_treinamento_ativo: bool = False,
) -> None:
    agora = _agora()
    os_val = int(numero_os) if numero_os not in (None, "", 0) else None
    perfil_id = int(perfil_observado_id) if perfil_observado_id not in (None, "", 0) else None
    conn.execute(
        """
        INSERT INTO presenca_usuario (
            usuario_id, modulo, aba, contexto, detalhe,
            perfil_observado_id, perfil_observado_nome, numero_os,
            sandbox_treinamento_ativo, atualizado_em
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(usuario_id) DO UPDATE SET
            modulo = excluded.modulo,
            aba = excluded.aba,
            contexto = excluded.contexto,
            detalhe = excluded.detalhe,
            perfil_observado_id = excluded.perfil_observado_id,
            perfil_observado_nome = excluded.perfil_observado_nome,
            numero_os = excluded.numero_os,
            sandbox_treinamento_ativo = excluded.sandbox_treinamento_ativo,
            atualizado_em = excluded.atualizado_em
        """,
        (
            int(usuario_id),
            (modulo or "").strip()[:120],
            (aba or "").strip()[:120],
            (contexto or "").strip()[:200],
            (detalhe or "").strip()[:400],
            perfil_id,
            (perfil_observado_nome or "").strip()[:120] or None,
            os_val,
            1 if sandbox_treinamento_ativo else 0,
            agora,
        ),
    )


def _limite_presenca_ativa() -> str:
    limite = datetime.now() - timedelta(seconds=PRESENCA_TTL_SEGUNDOS)
    return limite.strftime("%Y-%m-%d %H:%M:%S")


def _presenca_online(atualizado_em: str | None) -> bool:
    if not atualizado_em:
        return False
    try:
        dt = datetime.strptime(str(atualizado_em)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    return (datetime.now() - dt).total_seconds() <= PRESENCA_TTL_SEGUNDOS


def _montar_resumo(p: dict[str, Any]) -> str:
    partes: list[str] = []
    if p.get("sandbox_treinamento_ativo"):
        partes.append("🧪 Treinamento (sandbox)")
    if p.get("perfil_observado_nome"):
        partes.append(f"Perfil de {p['perfil_observado_nome']}")
    elif p.get("aba"):
        partes.append(str(p["aba"]))
    if p.get("contexto"):
        partes.append(str(p["contexto"]))
    if p.get("detalhe"):
        partes.append(str(p["detalhe"]))
    if not partes:
        return "No app"
    return " · ".join(partes)


def _rotulo_perfil(perfil: str | None) -> str:
    mapa = {
        "admin": "Administrador",
        "atendente": "Atendente",
        "mecanico": "Mecânico",
        "operador": "Operador",
    }
    return mapa.get(str(perfil or "").strip().lower(), str(perfil or "—"))


def listar_presenca_monitor(
    conn: sqlite3.Connection,
    espectador: dict[str, Any],
) -> list[dict[str, Any]]:
    """Lista todos os perfis visíveis ao espectador, com status online/offline."""
    rows = conn.execute(
        """
        SELECT u.id, u.usuario, u.nome_exibicao, u.perfil,
               p.modulo, p.aba, p.contexto, p.detalhe,
               p.perfil_observado_id, p.perfil_observado_nome, p.numero_os,
               p.sandbox_treinamento_ativo, p.atualizado_em
        FROM usuarios u
        LEFT JOIN presenca_usuario p ON p.usuario_id = u.id
        WHERE u.ativo = 1 AND u.perfil != 'admin'
        ORDER BY u.nome_exibicao COLLATE NOCASE, u.usuario COLLATE NOCASE
        """
    ).fetchall()
    saida: list[dict[str, Any]] = []
    espectador_id = int(espectador.get("id") or 0)
    for row in rows:
        uid = int(row["id"])
        if uid == espectador_id:
            continue
        if not espectador_pode_ver_alvo(
            espectador,
            alvo_id=uid,
            alvo_perfil=str(row["perfil"] or ""),
        ):
            continue
        online = _presenca_online(row["atualizado_em"])
        item: dict[str, Any] = {
            "usuario_id": uid,
            "usuario": row["usuario"] or "",
            "nome_exibicao": row["nome_exibicao"] or row["usuario"] or "",
            "perfil": row["perfil"] or "",
            "perfil_rotulo": _rotulo_perfil(row["perfil"]),
            "modulo": row["modulo"] or "" if online else "",
            "aba": row["aba"] or "" if online else "",
            "contexto": row["contexto"] or "" if online else "",
            "detalhe": row["detalhe"] or "" if online else "",
            "perfil_observado_id": row["perfil_observado_id"] if online else None,
            "perfil_observado_nome": row["perfil_observado_nome"] or "" if online else "",
            "numero_os": row["numero_os"] if online else None,
            "sandbox_treinamento_ativo": bool(row["sandbox_treinamento_ativo"]) if online else False,
            "atualizado_em": row["atualizado_em"] or "" if online else "",
            "online": online,
            "resumo": "",
            "resumo_curto": "",
        }
        if online:
            item["resumo"] = _montar_resumo(item)
            item["resumo_curto"] = item["resumo"]
        else:
            item["resumo"] = (
                "Offline — saiu do app, trocou de tela ou o app não está em primeiro plano."
            )
            item["resumo_curto"] = "Offline"
        saida.append(item)
    saida.sort(
        key=lambda x: (
            0 if x["online"] else 1,
            str(x["nome_exibicao"]).casefold(),
        )
    )
    return saida


def listar_usuarios_rastreaveis(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, usuario, nome_exibicao, perfil
        FROM usuarios
        WHERE ativo = 1 AND perfil != 'admin'
        ORDER BY nome_exibicao COLLATE NOCASE, usuario COLLATE NOCASE
        """
    ).fetchall()
    return [
        {
            "id": int(r["id"]),
            "usuario": r["usuario"] or "",
            "nome_exibicao": r["nome_exibicao"] or r["usuario"] or "",
            "perfil": r["perfil"] or "",
        }
        for r in rows
    ]

"""Agendamentos de serviço — calendário integrado ao cadastro de clientes e motores."""

from __future__ import annotations

import calendar
import sqlite3
from datetime import date, datetime
from typing import Any

STATUS_AGENDADO = "Agendado"
STATUS_CANCELADO = "Cancelado"
STATUS_EMERGENCIA = "Emergencia"
STATUS_VIRou_OS = "Virou O.S."

TIPO_LOCAL_INTERNO = "Interno"
TIPO_LOCAL_EXTERNO = "Externo"

_STATUS_ATIVOS_CALENDARIO = frozenset({STATUS_AGENDADO, STATUS_EMERGENCIA, STATUS_VIRou_OS})


def _normalizar_tipo_local(valor: str | None) -> str:
    texto = str(valor or TIPO_LOCAL_INTERNO).strip()
    if texto.lower() == TIPO_LOCAL_EXTERNO.lower():
        return TIPO_LOCAL_EXTERNO
    return TIPO_LOCAL_INTERNO


def _garantir_coluna_tipo_local(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(agendamentos)")}
    if "tipo_local" not in cols:
        conn.execute(
            "ALTER TABLE agendamentos ADD COLUMN tipo_local TEXT NOT NULL DEFAULT 'Interno'"
        )


def init_agendamentos_tabelas(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cliente INTEGER NOT NULL,
            id_motor INTEGER,
            data_agendamento TEXT NOT NULL,
            alegacao_cliente TEXT,
            status TEXT NOT NULL DEFAULT 'Agendado',
            tipo_local TEXT NOT NULL DEFAULT 'Interno',
            criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            atualizado_em TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_agendamentos_data ON agendamentos(data_agendamento);
        CREATE INDEX IF NOT EXISTS idx_agendamentos_cliente ON agendamentos(id_cliente);
        CREATE INDEX IF NOT EXISTS idx_agendamentos_status ON agendamentos(status);
        """
    )
    _garantir_coluna_tipo_local(conn)


def _normalizar_data(valor: str | None) -> str:
    texto = str(valor or "").strip()
    if len(texto) >= 10:
        return texto[:10]
    raise ValueError("Informe uma data válida (AAAA-MM-DD).")


def _agora_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _validar_cliente(conn: sqlite3.Connection, id_cliente: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT id, nome FROM clientes WHERE id = ?",
        (int(id_cliente),),
    ).fetchone()
    if row is None:
        raise ValueError("Cliente não encontrado.")
    return row


def _validar_motor_cliente(
    conn: sqlite3.Connection,
    id_motor: int | None,
    id_cliente: int,
) -> int | None:
    if id_motor is None or int(id_motor) <= 0:
        return None
    row = conn.execute(
        "SELECT id, cliente_id FROM motores WHERE id = ?",
        (int(id_motor),),
    ).fetchone()
    if row is None:
        raise ValueError("Motor não encontrado.")
    if int(row["cliente_id"]) != int(id_cliente):
        raise ValueError("O motor selecionado não pertence a este cliente.")
    return int(row["id"])


def _rotulo_motor_row(row: sqlite3.Row) -> str:
    marca = str(row["marca_modelo"] or "").strip() or "Motor"
    chassi = str(row["chassi"] or "").strip()
    if chassi:
        return f"{marca} — {chassi}"
    return marca


def _agendamento_para_json(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "id_cliente": int(row["id_cliente"]),
        "id_motor": int(row["id_motor"]) if row["id_motor"] else None,
        "data_agendamento": str(row["data_agendamento"] or "")[:10],
        "alegacao_cliente": str(row["alegacao_cliente"] or ""),
        "status": str(row["status"] or STATUS_AGENDADO),
        "tipo_local": _normalizar_tipo_local(
            row["tipo_local"] if "tipo_local" in row.keys() else TIPO_LOCAL_INTERNO
        ),
        "cliente_nome": str(row["cliente_nome"] or "") if "cliente_nome" in row.keys() else "",
        "motor_rotulo": str(row["motor_rotulo"] or "") if "motor_rotulo" in row.keys() else "",
        "criado_em": str(row["criado_em"] or ""),
        "atualizado_em": str(row["atualizado_em"] or ""),
    }


def _sql_agendamentos_base() -> str:
    return """
        SELECT
            a.*,
            c.nome AS cliente_nome,
            CASE
                WHEN m.id IS NULL THEN ''
                ELSE TRIM(
                    COALESCE(m.marca_modelo, '') ||
                    CASE WHEN COALESCE(m.chassi, '') != '' THEN ' — ' || m.chassi ELSE '' END
                )
            END AS motor_rotulo
        FROM agendamentos a
        JOIN clientes c ON c.id = a.id_cliente
        LEFT JOIN motores m ON m.id = a.id_motor
    """


def resumo_calendario_mes(
    conn: sqlite3.Connection,
    *,
    ano: int,
    mes: int,
) -> dict[str, dict[str, Any]]:
    """Contagem por dia para o mês (apenas status visíveis no calendário)."""
    if mes < 1 or mes > 12:
        raise ValueError("Mês inválido.")
    inicio = date(ano, mes, 1).isoformat()
    if mes == 12:
        fim = date(ano + 1, 1, 1).isoformat()
    else:
        fim = date(ano, mes + 1, 1).isoformat()

    placeholders = ",".join("?" * len(_STATUS_ATIVOS_CALENDARIO))
    sql = f"""
        SELECT
            data_agendamento,
            status,
            COALESCE(NULLIF(TRIM(tipo_local), ''), 'Interno') AS tipo_local,
            COUNT(*) AS qtd
        FROM agendamentos
        WHERE data_agendamento >= ? AND data_agendamento < ?
          AND status IN ({placeholders})
        GROUP BY data_agendamento, status, tipo_local
    """
    params: list[Any] = [inicio, fim, *_STATUS_ATIVOS_CALENDARIO]
    rows = conn.execute(sql, params).fetchall()

    dias: dict[str, dict[str, Any]] = {}
    for row in rows:
        dia = str(row["data_agendamento"] or "")[:10]
        if not dia:
            continue
        info = dias.setdefault(
            dia,
            {"total": 0, "qtd_normal": 0, "qtd_emergencia": 0, "qtd_externo": 0},
        )
        qtd = int(row["qtd"] or 0)
        info["total"] += qtd
        status = str(row["status"] or "")
        tipo_local = _normalizar_tipo_local(row["tipo_local"])
        if status == STATUS_EMERGENCIA:
            info["qtd_emergencia"] += qtd
        if tipo_local == TIPO_LOCAL_EXTERNO:
            info["qtd_externo"] += qtd
        if status != STATUS_EMERGENCIA and tipo_local != TIPO_LOCAL_EXTERNO:
            info["qtd_normal"] += qtd
    return dias


def agendamento_tem_os_vinculada(conn_os: sqlite3.Connection, ag_id: int) -> bool:
    try:
        row = conn_os.execute(
            """
            SELECT 1 FROM ordens_servico
            WHERE CAST(json_extract(dados_json, '$.agendamento_id') AS INTEGER) = ?
            LIMIT 1
            """,
            (int(ag_id),),
        ).fetchone()
    except sqlite3.Error:
        return False
    return row is not None


def corrigir_status_virou_os_orfao(
    conn: sqlite3.Connection,
    conn_os: sqlite3.Connection,
    ag_id: int,
) -> bool:
    """Reverte 'Virou O.S.' quando não há O.S. gravada vinculada ao agendamento."""
    atual = conn.execute(
        "SELECT id, status FROM agendamentos WHERE id = ?",
        (int(ag_id),),
    ).fetchone()
    if atual is None or str(atual["status"] or "") != STATUS_VIRou_OS:
        return False
    if agendamento_tem_os_vinculada(conn_os, ag_id):
        return False
    conn.execute(
        """
        UPDATE agendamentos
        SET status = ?, atualizado_em = ?
        WHERE id = ?
        """,
        (STATUS_AGENDADO, _agora_local(), int(ag_id)),
    )
    return True


def corrigir_orfaos_dia(
    conn: sqlite3.Connection,
    conn_os: sqlite3.Connection,
    data: str,
) -> None:
    data_norm = _normalizar_data(data)
    rows = conn.execute(
        "SELECT id FROM agendamentos WHERE data_agendamento = ? AND status = ?",
        (data_norm, STATUS_VIRou_OS),
    ).fetchall()
    for row in rows:
        corrigir_status_virou_os_orfao(conn, conn_os, int(row["id"]))


def validar_agendamento_para_gerar_os(
    conn: sqlite3.Connection,
    conn_os: sqlite3.Connection,
    ag_id: int,
) -> dict[str, Any]:
    corrigir_status_virou_os_orfao(conn, conn_os, ag_id)
    ag = obter_agendamento(conn, ag_id)
    if ag is None:
        raise ValueError("Agendamento não encontrado.")
    if str(ag["status"] or "") == STATUS_CANCELADO:
        raise ValueError("Agendamento cancelado.")
    if str(ag["status"] or "") == STATUS_VIRou_OS:
        raise ValueError("Este agendamento já foi convertido em O.S.")
    return ag


def listar_agendamentos_dia(
    conn: sqlite3.Connection,
    *,
    data: str,
    incluir_cancelados: bool = False,
    conn_os: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    data_norm = _normalizar_data(data)
    if conn_os is not None:
        corrigir_orfaos_dia(conn, conn_os, data_norm)
    sql = _sql_agendamentos_base() + " WHERE a.data_agendamento = ?"
    params: list[Any] = [data_norm]
    if not incluir_cancelados:
        sql += " AND a.status != ?"
        params.append(STATUS_CANCELADO)
    sql += """
        ORDER BY
            CASE a.status
                WHEN 'Emergencia' THEN 0
                WHEN 'Agendado' THEN 1
                WHEN 'Virou O.S.' THEN 2
                ELSE 3
            END,
            a.id DESC
    """
    rows = conn.execute(sql, params).fetchall()
    return [_agendamento_para_json(r) for r in rows]


def obter_agendamento(conn: sqlite3.Connection, ag_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        _sql_agendamentos_base() + " WHERE a.id = ?",
        (int(ag_id),),
    ).fetchone()
    if row is None:
        return None
    return _agendamento_para_json(row)


def criar_agendamento(
    conn: sqlite3.Connection,
    *,
    id_cliente: int,
    id_motor: int | None,
    data_agendamento: str,
    alegacao_cliente: str,
    status: str = STATUS_AGENDADO,
    tipo_local: str = TIPO_LOCAL_INTERNO,
) -> dict[str, Any]:
    _validar_cliente(conn, id_cliente)
    id_motor_ok = _validar_motor_cliente(conn, id_motor, id_cliente)
    data_norm = _normalizar_data(data_agendamento)
    st = str(status or STATUS_AGENDADO).strip()
    if st not in (STATUS_AGENDADO, STATUS_EMERGENCIA):
        st = STATUS_AGENDADO
    tipo = _normalizar_tipo_local(tipo_local)
    agora = _agora_local()
    cur = conn.execute(
        """
        INSERT INTO agendamentos (
            id_cliente, id_motor, data_agendamento, alegacao_cliente, status, tipo_local, criado_em
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(id_cliente),
            id_motor_ok,
            data_norm,
            str(alegacao_cliente or "").strip(),
            st,
            tipo,
            agora,
        ),
    )
    novo_id = int(cur.lastrowid)
    item = obter_agendamento(conn, novo_id)
    if item is None:
        raise RuntimeError("Falha ao criar agendamento.")
    return item


def reagendar_agendamento(
    conn: sqlite3.Connection,
    ag_id: int,
    *,
    data_agendamento: str,
    id_motor: int | None = None,
    alegacao_cliente: str | None = None,
    tipo_local: str | None = None,
) -> dict[str, Any]:
    atual = conn.execute(
        "SELECT * FROM agendamentos WHERE id = ?",
        (int(ag_id),),
    ).fetchone()
    if atual is None:
        raise ValueError("Agendamento não encontrado.")
    if str(atual["status"] or "") in (STATUS_CANCELADO, STATUS_VIRou_OS):
        raise ValueError("Este agendamento não pode ser reagendado.")

    data_norm = _normalizar_data(data_agendamento)
    motor_id = int(atual["id_motor"] or 0) or None
    if id_motor is not None:
        motor_id = _validar_motor_cliente(conn, id_motor, int(atual["id_cliente"]))
    alegacao = (
        str(alegacao_cliente).strip()
        if alegacao_cliente is not None
        else str(atual["alegacao_cliente"] or "")
    )
    tipo = (
        _normalizar_tipo_local(tipo_local)
        if tipo_local is not None
        else _normalizar_tipo_local(
            atual["tipo_local"] if "tipo_local" in atual.keys() else TIPO_LOCAL_INTERNO
        )
    )
    conn.execute(
        """
        UPDATE agendamentos
        SET data_agendamento = ?, id_motor = ?, alegacao_cliente = ?, tipo_local = ?, atualizado_em = ?
        WHERE id = ?
        """,
        (data_norm, motor_id, alegacao, tipo, _agora_local(), int(ag_id)),
    )
    item = obter_agendamento(conn, ag_id)
    if item is None:
        raise RuntimeError("Falha ao reagendar.")
    return item


def cancelar_agendamento(conn: sqlite3.Connection, ag_id: int) -> dict[str, Any]:
    atual = conn.execute(
        "SELECT id, status FROM agendamentos WHERE id = ?",
        (int(ag_id),),
    ).fetchone()
    if atual is None:
        raise ValueError("Agendamento não encontrado.")
    if str(atual["status"] or "") == STATUS_VIRou_OS:
        raise ValueError("Agendamento já convertido em O.S.")
    conn.execute(
        """
        UPDATE agendamentos
        SET status = ?, atualizado_em = ?
        WHERE id = ?
        """,
        (STATUS_CANCELADO, _agora_local(), int(ag_id)),
    )
    item = obter_agendamento(conn, ag_id)
    if item is None:
        raise RuntimeError("Falha ao cancelar agendamento.")
    return item


def marcar_emergencia(conn: sqlite3.Connection, ag_id: int) -> dict[str, Any]:
    atual = conn.execute(
        "SELECT id, status FROM agendamentos WHERE id = ?",
        (int(ag_id),),
    ).fetchone()
    if atual is None:
        raise ValueError("Agendamento não encontrado.")
    if str(atual["status"] or "") in (STATUS_CANCELADO, STATUS_VIRou_OS):
        raise ValueError("Este agendamento não pode ser marcado como emergência.")
    conn.execute(
        """
        UPDATE agendamentos
        SET status = ?, atualizado_em = ?
        WHERE id = ?
        """,
        (STATUS_EMERGENCIA, _agora_local(), int(ag_id)),
    )
    item = obter_agendamento(conn, ag_id)
    if item is None:
        raise RuntimeError("Falha ao marcar emergência.")
    return item


def remover_emergencia(conn: sqlite3.Connection, ag_id: int) -> dict[str, Any]:
    atual = conn.execute(
        "SELECT id, status FROM agendamentos WHERE id = ?",
        (int(ag_id),),
    ).fetchone()
    if atual is None:
        raise ValueError("Agendamento não encontrado.")
    if str(atual["status"] or "") != STATUS_EMERGENCIA:
        raise ValueError("Este agendamento não está marcado como emergência.")
    conn.execute(
        """
        UPDATE agendamentos
        SET status = ?, atualizado_em = ?
        WHERE id = ?
        """,
        (STATUS_AGENDADO, _agora_local(), int(ag_id)),
    )
    item = obter_agendamento(conn, ag_id)
    if item is None:
        raise RuntimeError("Falha ao remover emergência.")
    return item


def marcar_virou_os(conn: sqlite3.Connection, ag_id: int) -> dict[str, Any]:
    atual = conn.execute(
        "SELECT id, status FROM agendamentos WHERE id = ?",
        (int(ag_id),),
    ).fetchone()
    if atual is None:
        raise ValueError("Agendamento não encontrado.")
    if str(atual["status"] or "") == STATUS_CANCELADO:
        raise ValueError("Agendamento cancelado.")
    conn.execute(
        """
        UPDATE agendamentos
        SET status = ?, atualizado_em = ?
        WHERE id = ?
        """,
        (STATUS_VIRou_OS, _agora_local(), int(ag_id)),
    )
    item = obter_agendamento(conn, ag_id)
    if item is None:
        raise RuntimeError("Falha ao atualizar agendamento.")
    return item


def metadados_mes(ano: int, mes: int) -> dict[str, Any]:
    cal = calendar.Calendar(firstweekday=6)
    semanas = cal.monthdayscalendar(ano, mes)
    nomes = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
    return {
        "ano": ano,
        "mes": mes,
        "semanas": semanas,
        "dias_semana": nomes,
        "nome_mes": calendar.month_name[mes],
    }

"""
Árvore de permissões granulares do O.S. Digital (espelha o Sistema Oficina).

Somente módulos operacionais e configurações de acesso entram na árvore.
Configurações globais do app (tipo O.S., login, sandbox, ao vivo, etc.) ficam
exclusivas do administrador.
"""

from __future__ import annotations

import json
from typing import Any

_ROTULOS_ACAO: dict[str, str] = {
    "visualizar": "Visualizar",
    "criar": "Criar",
    "editar": "Editar",
    "excluir": "Excluir",
    "gerar_pdf": "Gerar PDF",
    "gerar_os": "Gerar O.S.",
    "atualizar_precos": "Atualizar preços do catálogo",
    "finalizar": "Finalizar serviço",
    "pausar": "Marcar pausa",
    "retomar": "Retomar mecânico",
    "cliente_avisado": "Cliente avisado",
    "copiar_retorno": "Copiar retorno",
    "enviar": "Enviar",
    "responder": "Responder",
    "liberar_estoque": "Liberar estoque",
    "finalizar_interna": "Finalizar interna",
    "movimentar": "Movimentar",
    "pedidos": "Pedidos de compra",
    "receber": "Receber avisos no aparelho",
    "ver_historico": "Ver histórico de serviços",
}


def _rotulo_acao(nome: str) -> str:
    return _ROTULOS_ACAO.get(nome, nome.replace("_", " ").capitalize())


def _acao(rotulo: str, chave: str) -> dict[str, Any]:
    return {"tipo": "acao", "rotulo": rotulo, "chave": chave}


def _modulo(rotulo: str, prefixo: str, acoes: tuple[str, ...]) -> dict[str, Any]:
    return {
        "tipo": "modulo",
        "rotulo": rotulo,
        "filhos": [_acao(_rotulo_acao(a), f"{prefixo}_{a}") for a in acoes],
    }


def _modulo_agendamentos() -> dict[str, Any]:
    return {
        "tipo": "modulo",
        "rotulo": "Agenda",
        "filhos": [
            _acao("Visualizar calendário e detalhes", "agendamentos_geral_visualizar"),
            _acao("Agendar (novo)", "agendamentos_geral_criar"),
            _acao("Reagendar e emergência", "agendamentos_geral_editar"),
            _acao("Cancelar agendamento", "agendamentos_geral_excluir"),
            _acao("Transformar em O.S.", "agendamentos_geral_gerar_os"),
        ],
    }


def _modulo_pre_orcamentos_lista() -> dict[str, Any]:
    return {
        "tipo": "modulo",
        "rotulo": "Pré-Orçamentos",
        "filhos": [
            _acao("Visualizar lista e detalhes", "pre_orcamentos_geral_visualizar"),
            _acao("Criar novo", "pre_orcamentos_geral_criar"),
            _acao("Editar", "pre_orcamentos_geral_editar"),
            _acao("Excluir", "pre_orcamentos_geral_excluir"),
            _acao("Imprimir PDF", "pre_orcamentos_geral_gerar_pdf"),
            _acao("Converter em O.S.", "pre_orcamentos_geral_gerar_os"),
        ],
    }


def _modulo_kits_motor() -> dict[str, Any]:
    return {
        "tipo": "modulo",
        "rotulo": "Kits de Motor",
        "filhos": [
            _acao("Visualizar kits", "pre_orcamentos_kits_visualizar"),
            _acao("Criar kit", "pre_orcamentos_kits_criar"),
            _acao("Editar kit", "pre_orcamentos_kits_editar"),
            _acao("Excluir kit", "pre_orcamentos_kits_excluir"),
            _acao("Atualizar preços do catálogo", "pre_orcamentos_kits_atualizar_precos"),
        ],
    }


def _aba(rotulo: str, modulos: list[dict[str, Any]]) -> dict[str, Any]:
    return {"tipo": "aba", "rotulo": rotulo, "filhos": modulos}


PERMISSOES_ARVORE_OS: tuple[dict[str, Any], ...] = (
    _aba(
        "Agendamentos",
        [
            _modulo_agendamentos(),
        ],
    ),
    _aba(
        "Pré-Orçamentos",
        [
            _modulo_pre_orcamentos_lista(),
            _modulo_kits_motor(),
        ],
    ),
    _aba(
        "Ordem de Serviço",
        [
            _modulo(
                "Formulário O.S.",
                "ordem_os_geral",
                ("visualizar", "criar", "editar", "gerar_pdf", "finalizar"),
            ),
        ],
    ),
    _aba(
        "Lista de O.S.",
        [
            _modulo(
                "Painel e ações",
                "lista_os_geral",
                (
                    "visualizar",
                    "atribuir_mecanico",
                    "pausar",
                    "retomar",
                    "cliente_avisado",
                    "copiar_retorno",
                    "cancelar",
                    "reativar",
                    "excluir",
                ),
            ),
            _modulo(
                "Perfil do mecânico",
                "perfil_mecanico",
                ("ver_historico",),
            ),
        ],
    ),
    _aba(
        "Fotos O.S.",
        [
            _modulo(
                "Envio e revisão",
                "fotos_os_geral",
                (
                    "visualizar",
                    "enviar",
                    "gerar_pdf",
                    "baixar",
                    "marcar_enviado",
                ),
            ),
        ],
    ),
    _aba(
        "Requisições",
        [
            _modulo(
                "Requisições de O.S.",
                "requisicoes_os",
                ("visualizar", "criar", "editar", "enviar", "responder", "liberar_estoque"),
            ),
            _modulo(
                "Requisições internas",
                "requisicoes_interna",
                ("visualizar", "criar", "editar", "finalizar_interna"),
            ),
        ],
    ),
    _aba(
        "Estoque",
        [
            _modulo(
                "Movimentação e pedidos",
                "estoque_geral",
                ("visualizar", "movimentar", "pedidos"),
            ),
        ],
    ),
    _aba(
        "Cadastros",
        [
            _modulo("Clientes", "cadastros_clientes", ("visualizar", "criar", "editar")),
            _modulo("Motores / embarcações", "cadastros_motores", ("visualizar", "criar", "editar")),
            _modulo("Peças (catálogo)", "cadastros_pecas", ("visualizar", "criar", "editar")),
            _modulo("Serviços (catálogo)", "cadastros_servicos", ("visualizar", "criar", "editar")),
        ],
    ),
    _aba(
        "Configurações",
        [
            _modulo("Meu perfil", "config_perfil", ("visualizar", "editar")),
            _modulo(
                "Usuários",
                "config_usuarios",
                ("visualizar", "criar", "editar", "excluir"),
            ),
            _modulo(
                "Rastreio de atividade",
                "config_atividade",
                ("visualizar", "excluir", "limpar"),
            ),
            _modulo(
                "Notificações no aparelho",
                "config_notificacoes",
                ("visualizar", "receber"),
            ),
        ],
    ),
)

_CHAVES_CONFIG_RESTRITAS: tuple[str, ...] = (
    "config_perfil_visualizar",
    "config_perfil_editar",
    "config_usuarios_visualizar",
    "config_usuarios_criar",
    "config_usuarios_editar",
    "config_usuarios_excluir",
    "config_atividade_visualizar",
    "config_atividade_excluir",
    "config_atividade_limpar",
)

_CHAVES_PERMISSAO_EXPLICITA: tuple[str, ...] = (
    "perfil_mecanico_ver_historico",
)

_PREFIXO_PRE_ORCAMENTOS = "pre_orcamentos_"


def _eh_chave_pre_orcamentos(chave: str) -> bool:
    return str(chave or "").startswith(_PREFIXO_PRE_ORCAMENTOS)


def _eh_chave_permissao_explicita(chave: str) -> bool:
    return chave in _CHAVES_PERMISSAO_EXPLICITA or _eh_chave_pre_orcamentos(chave)

MAPA_MODULO_PREFIXOS: dict[str, tuple[str, ...]] = {
    "agendamentos": ("agendamentos_",),
    "pre_orcamentos": ("pre_orcamentos_",),
    "ordem": ("ordem_os_",),
    "lista": ("lista_os_",),
    "fotos_os": ("fotos_os_",),
    "requisicao": ("requisicoes_",),
    "estoque": ("estoque_",),
    "config_perfil": ("config_perfil_",),
    "config_usuarios": ("config_usuarios_",),
    "config_atividade": ("config_atividade_",),
    "config_notificacoes": ("config_notificacoes_",),
    "config": ("config_",),
}

ORDEM_ABAS_OS: tuple[str, ...] = tuple(aba["rotulo"] for aba in PERMISSOES_ARVORE_OS)


def _coletar_chaves_folha(no: dict[str, Any]) -> list[str]:
    if no.get("tipo") == "acao":
        chave = str(no.get("chave") or "").strip()
        return [chave] if chave else []
    saida: list[str] = []
    for filho in no.get("filhos") or []:
        saida.extend(_coletar_chaves_folha(filho))
    return saida


def todas_chaves_permissao_os() -> tuple[str, ...]:
    chaves: list[str] = []
    for aba in PERMISSOES_ARVORE_OS:
        chaves.extend(_coletar_chaves_folha(aba))
    return tuple(chaves)


def permissoes_granulares_vazias() -> dict[str, bool]:
    return {chave: False for chave in todas_chaves_permissao_os()}


def normalizar_permissoes_granulares(valor: Any) -> dict[str, bool]:
    base = permissoes_granulares_vazias()
    if valor is None:
        return base
    if isinstance(valor, dict):
        bruto = valor
    elif isinstance(valor, str):
        txt = valor.strip()
        if not txt:
            return base
        try:
            parsed = json.loads(txt)
        except json.JSONDecodeError:
            return base
        if not isinstance(parsed, dict):
            return base
        bruto = parsed
    else:
        return base
    for chave in base:
        if chave in bruto:
            base[chave] = bool(bruto[chave])
    return base


def chaves_explicitas_permissoes(valor: Any) -> set[str]:
    """Chaves presentes no JSON salvo (antes de preencher ausentes com False)."""
    chaves_validas = set(permissoes_granulares_vazias().keys())
    if isinstance(valor, dict):
        return {str(k) for k in valor if str(k) in chaves_validas}
    if isinstance(valor, str):
        txt = valor.strip()
        if not txt:
            return set()
        try:
            parsed = json.loads(txt)
        except json.JSONDecodeError:
            return set()
        if isinstance(parsed, dict):
            return {str(k) for k in parsed if str(k) in chaves_validas}
    return set()


def permissoes_com_heranca_modelo(
    valor: Any,
    *,
    modelo_base: str | None = None,
) -> dict[str, bool]:
    """
    Chaves novas (ausentes no JSON salvo) herdam o template do modelo,
    exceto Pré-Orçamentos — estas só ficam ativas se estiverem explícitas no JSON.
    """
    explicitas = chaves_explicitas_permissoes(valor)
    base = normalizar_permissoes_granulares(valor)
    modelo = str(modelo_base or "").strip().lower()
    if not modelo or modelo in {"admin", "personalizado"}:
        return base
    template = permissoes_template_por_modelo(modelo)
    for chave in base:
        if _eh_chave_permissao_explicita(chave):
            base[chave] = bool(chave in explicitas and base[chave])
            continue
        if chave not in explicitas:
            base[chave] = bool(template.get(chave, False))
    return base


def serializar_permissoes_granulares(permissoes: dict[str, bool] | None) -> str:
    norm = normalizar_permissoes_granulares(permissoes or {})
    return json.dumps(norm, ensure_ascii=False, sort_keys=True)


def modulo_tem_alguma_permissao(
    permissoes: dict[str, bool],
    prefixos: tuple[str, ...],
) -> bool:
    norm = normalizar_permissoes_granulares(permissoes)
    return any(
        bool(ativo) and any(chave.startswith(p) for p in prefixos)
        for chave, ativo in norm.items()
    )


def modulo_pre_orcamentos_apenas_explicito(permissoes: dict[str, bool] | Any) -> bool:
    """Pré-Orçamentos só aparece se estiver marcado no JSON salvo (não herda template)."""
    norm = normalizar_permissoes_granulares(permissoes)
    return modulo_tem_alguma_permissao(norm, MAPA_MODULO_PREFIXOS["pre_orcamentos"])


def tem_permissao_pre_orcamentos_explicita(
    permissoes: dict[str, bool] | Any,
    chave: str,
) -> bool:
    norm = normalizar_permissoes_granulares(permissoes)
    return bool(norm.get(chave))


def modulos_visiveis_de_permissoes(permissoes: dict[str, bool]) -> dict[str, bool]:
    norm = normalizar_permissoes_granulares(permissoes)
    return {
        modulo: modulo_tem_alguma_permissao(norm, prefixos)
        for modulo, prefixos in MAPA_MODULO_PREFIXOS.items()
    }


def usuario_tem_permissao_granular(
    permissoes: dict[str, bool],
    chave: str,
) -> bool:
    norm = normalizar_permissoes_granulares(permissoes)
    return bool(norm.get(chave))


def permissoes_padrao_usuario_os() -> dict[str, bool]:
    """Permissões efetivas de atendente/operador sem perfil personalizado salvo."""
    base = permissoes_granulares_vazias()
    for chave in base:
        if chave in _CHAVES_CONFIG_RESTRITAS or chave in _CHAVES_PERMISSAO_EXPLICITA or _eh_chave_pre_orcamentos(chave):
            base[chave] = False
        else:
            base[chave] = True
    return base


def permissoes_padrao_mecanico() -> dict[str, bool]:
    """Template rápido: mecânico de campo."""
    base = permissoes_granulares_vazias()
    for chave in (
        "ordem_os_geral_visualizar",
        "ordem_os_geral_criar",
        "ordem_os_geral_editar",
        "ordem_os_geral_gerar_pdf",
        "ordem_os_geral_finalizar",
        "lista_os_geral_visualizar",
        "lista_os_geral_atribuir_mecanico",
        "lista_os_geral_pausar",
        "lista_os_geral_retomar",
        "lista_os_geral_cliente_avisado",
        "lista_os_geral_copiar_retorno",
        "fotos_os_geral_visualizar",
        "fotos_os_geral_enviar",
        "requisicoes_os_visualizar",
        "requisicoes_os_criar",
        "requisicoes_os_editar",
        "requisicoes_os_enviar",
        "requisicoes_interna_visualizar",
        "requisicoes_interna_criar",
        "requisicoes_interna_editar",
        "requisicoes_interna_finalizar_interna",
        "config_perfil_visualizar",
        "config_perfil_editar",
        "config_notificacoes_visualizar",
        "config_notificacoes_receber",
    ):
        if chave in base:
            base[chave] = True
    return base


def permissoes_padrao_atendente() -> dict[str, bool]:
    return permissoes_padrao_usuario_os()


def permissoes_padrao_operador() -> dict[str, bool]:
    return permissoes_padrao_usuario_os()


def permissoes_template_por_modelo(modelo: str) -> dict[str, bool]:
    modelo_norm = str(modelo or "").strip().lower()
    if modelo_norm == "admin":
        return {chave: True for chave in permissoes_granulares_vazias()}
    if modelo_norm == "mecanico":
        return permissoes_padrao_mecanico()
    if modelo_norm == "atendente":
        return permissoes_padrao_atendente()
    if modelo_norm == "operador":
        return permissoes_padrao_operador()
    return permissoes_granulares_vazias()


def permissoes_efetivas_usuario(
    permissoes: dict[str, bool] | Any,
    *,
    controle_abas_ativo: bool,
    perfil: str,
    modelo_base: str | None = None,
) -> dict[str, bool]:
    """Resolve o que o usuário tem de fato (abas, APIs e checagens)."""
    modelo = str(modelo_base or perfil or "").strip().lower()
    if modelo == "admin":
        return permissoes_template_por_modelo("admin")
    gran = normalizar_permissoes_granulares(permissoes)
    if controle_abas_ativo:
        return gran
    if modelo in {"mecanico", "atendente", "operador"}:
        return permissoes_template_por_modelo(modelo)
    return gran if any(gran.values()) else permissoes_granulares_vazias()


def arvore_permissoes_json() -> list[dict[str, Any]]:
    """Exporta a árvore para o frontend (sem funções auxiliares internas)."""
    return list(PERMISSOES_ARVORE_OS)

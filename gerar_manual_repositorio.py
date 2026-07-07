"""
Gera PDF: como usar o repositorio de checkpoints de permissao e rastreio.

Execute: python gerar_manual_repositorio.py
Saida: MANUAL_REPOSITORIO_PERMISSOES_E_RASTREIOS.pdf (mesma pasta)
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fpdf import FPDF

_DIR = Path(__file__).resolve().parent
_SAIDA = _DIR / "MANUAL_REPOSITORIO_PERMISSOES_E_RASTREIOS.pdf"
_FONT = "ArialPermRastreio"
_VERSAO = "1.0.0"


def _registrar_fontes(pdf: FPDF) -> str:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    regular = windir / "Fonts" / "arial.ttf"
    bold = windir / "Fonts" / "arialbd.ttf"
    if regular.is_file():
        pdf.add_font(_FONT, "", str(regular))
        pdf.add_font(_FONT, "B", str(bold if bold.is_file() else regular))
        return _FONT
    return "Helvetica"


def _txt(s: str) -> str:
    repl = {
        "\u2014": "-",
        "\u2013": "-",
        "\u2192": "->",
        "\u2190": "<-",
        "\u251c": "|",
        "\u2514": "+",
        "\u2502": "|",
        "\u2500": "-",
        "\u2022": "-",
        "\u2713": "[ok]",
        "\u2717": "[x]",
        "\u26a0": "[!]",
    }
    for a, b in repl.items():
        s = s.replace(a, b)
    return s.encode("latin-1", errors="replace").decode("latin-1")


class DocPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(getattr(self, "_fonte", "Helvetica"), "", 8)
        self.set_text_color(100, 100, 100)
        self.cell(
            0,
            8,
            _txt(
                f"Arvore de permissao e rastreios v{_VERSAO} - "
                f"{date.today():%d/%m/%Y} - pag. {self.page_no()}"
            ),
            align="C",
        )


def _largura(pdf: DocPDF) -> float:
    return pdf.w - pdf.l_margin - pdf.r_margin


def titulo(pdf: DocPDF, texto: str, nivel: int = 1) -> None:
    if pdf.get_y() > 250:
        pdf.add_page()
    pdf.set_x(pdf.l_margin)
    if nivel == 1:
        pdf.set_font(pdf._fonte, "B", 14)
        pdf.set_text_color(20, 60, 120)
    elif nivel == 2:
        pdf.set_font(pdf._fonte, "B", 11)
        pdf.set_text_color(40, 70, 110)
    else:
        pdf.set_font(pdf._fonte, "B", 10)
        pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(_largura(pdf), 7, _txt(texto))
    pdf.ln(2)


def paragrafo(pdf: DocPDF, texto: str) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font(pdf._fonte, "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(_largura(pdf), 5.5, _txt(texto))
    pdf.ln(1.5)


def item(pdf: DocPDF, texto: str) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font(pdf._fonte, "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(_largura(pdf), 5.5, _txt(f"  - {texto}"))
    pdf.ln(0.5)


def caixa(pdf: DocPDF, texto: str, cor_fundo: tuple[int, int, int] = (245, 248, 252)) -> None:
    pdf.set_fill_color(*cor_fundo)
    pdf.set_draw_color(180, 200, 230)
    y = pdf.get_y()
    pdf.set_font(pdf._fonte, "", 9)
    linhas = texto.count("\n") + max(1, len(texto) // 88)
    h = linhas * 5.5 + 6
    if y + h > 275:
        pdf.add_page()
        y = pdf.get_y()
    margem = pdf.l_margin
    largura = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.rect(margem, y, largura, h, style="DF")
    pdf.set_xy(margem + 2, y + 3)
    pdf.multi_cell(largura - 4, 5.5, _txt(texto))
    pdf.set_xy(margem, y + h + 2)


def codigo(pdf: DocPDF, texto: str) -> None:
    caixa(pdf, texto, cor_fundo=(240, 242, 246))


def tabela_simples(pdf: DocPDF, cabecalho: list[str], linhas: list[list[str]]) -> None:
    col_w = _largura(pdf) / len(cabecalho)
    pdf.set_font(pdf._fonte, "B", 9)
    pdf.set_fill_color(220, 230, 245)
    for col in cabecalho:
        pdf.cell(col_w, 7, _txt(col), border=1, fill=True)
    pdf.ln()
    pdf.set_font(pdf._fonte, "", 8)
    for linha in linhas:
        if pdf.get_y() > 265:
            pdf.add_page()
        for col in linha:
            pdf.cell(col_w, 6.5, _txt(col), border=1)
        pdf.ln()


def gerar() -> Path:
    pdf = DocPDF()
    pdf._fonte = _registrar_fontes(pdf)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font(pdf._fonte, "B", 18)
    pdf.set_text_color(20, 60, 120)
    pdf.cell(0, 12, _txt("Manual do Repositorio"), ln=True, align="C")
    pdf.set_font(pdf._fonte, "B", 13)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 10, _txt("Arvore de permissao e rastreios"), ln=True, align="C")
    pdf.ln(4)
    paragrafo(
        pdf,
        "Este documento explica como usar o repositorio separado de checkpoints "
        "enquanto a etapa de permissoes granulares e rastreio de atividade esta "
        "em desenvolvimento, e como levar o trabalho para o repositorio original "
        "(app_ordem_servico) somente quando tudo estiver testado e aprovado.",
    )
    paragrafo(pdf, f"Versao do manual: {_VERSAO}  |  Data: {date.today():%d/%m/%Y}")

    titulo(pdf, "1. Por que existem dois repositorios?", 1)
    paragrafo(
        pdf,
        "Voce trabalha em dois lugares com funcoes diferentes. Confundir os dois "
        "e a principal causa de regressoes e de codigo incompleto indo para producao.",
    )
    tabela_simples(
        pdf,
        ["Repositorio", "Funcao", "Quando usar"],
        [
            [
                "arvore de permissao e rastreios",
                "Checkpoints seguros da etapa atual",
                "A cada modulo testado (Agendamentos, Pre-Orcamentos, etc.)",
            ],
            [
                "app_ordem_servico (original / GitHub)",
                "Projeto completo oficial",
                "Somente quando a etapa inteira estiver finalizada",
            ],
        ],
    )
    pdf.ln(3)
    caixa(
        pdf,
        "REGRA DE OURO: enquanto a etapa de permissoes/rastreio nao estiver "
        "100% pronta, salve checkpoints APENAS no repositorio separado. "
        "Evite git commit / git push no original com arquivos desta etapa.",
    )

    titulo(pdf, "2. Onde ficam as pastas", 1)
    codigo(
        pdf,
        "C:\\Users\\israe\\Desktop\\ISRAEL\\\n"
        "|-- arvore de permissao e rastreios\\     <- ESTE repositorio (checkpoints)\n"
        "|   |-- app_ordem_servico\\               <- espelho dos arquivos\n"
        "|   |-- salvar_checkpoint.ps1\n"
        "|   |-- restaurar.ps1\n"
        "|   +-- gerar_manual_repositorio.py\n"
        "|\n"
        "+-- Projetos_Python\\app_ordem_servico\\  <- projeto REAL (onde o Flask roda)",
    )
    paragrafo(
        pdf,
        "O Flask sempre roda a partir de Projetos_Python\\app_ordem_servico. "
        "O repositorio de checkpoints guarda copias versionadas dos arquivos "
        "que mudam nesta etapa.",
    )

    titulo(pdf, "3. Arquivos que este repositorio controla", 1)
    paragrafo(pdf, "Somente estes arquivos sao copiados ao salvar ou restaurar:")
    tabela_simples(
        pdf,
        ["Arquivo", "O que contem"],
        [
            ["permissoes_arvore_os.py", "Arvore de permissoes e mapa de modulos"],
            ["perfis_app.py", "Perfis de usuario no banco"],
            ["atividade_log.py", "Registro de rastreio de atividade"],
            ["presenca_telespectador.py", "Presenca e usuarios rastreaveis"],
            ["agendamentos.py", "Modulo Agendamentos"],
            ["app.py", "APIs, checagens de permissao e rastreio no backend"],
            ["templates/index.html", "UI, guards e aplicarPermissoes* no frontend"],
        ],
    )
    pdf.ln(2)
    paragrafo(
        pdf,
        "Outros arquivos do app (pre_orcamentos.py, pdf_os.py, build, etc.) "
        "NAO entram neste repositorio. Se voce alterar apenas esses, nao precisa "
        "de checkpoint aqui - use o git original normalmente.",
    )

    titulo(pdf, "4. Fluxo de trabalho diario", 1)
    titulo(pdf, "4.1 Desenvolver e testar", 2)
    item(pdf, "Edite os arquivos em Projetos_Python\\app_ordem_servico (projeto real).")
    item(pdf, "Reinicie o servidor Flask apos mudancas no backend.")
    item(pdf, "Use Ctrl+F5 no navegador para limpar cache do frontend.")
    item(pdf, "Teste cada permissao individualmente com um usuario de teste (ex.: Luara).")
    item(pdf, "Confirme: abas corretas, botoes ocultos, APIs bloqueadas, rastreio gravado.")

    titulo(pdf, "4.2 Salvar checkpoint (subir codigo novo neste repo)", 2)
    paragrafo(pdf, "Faca isso SOMENTE depois que o modulo testado estiver funcionando.")
    codigo(
        pdf,
        "cd \"C:\\Users\\israe\\Desktop\\ISRAEL\\arvore de permissao e rastreios\"\n"
        ".\\salvar_checkpoint.ps1 -Mensagem \"agendamentos: visualizar ok\"",
    )
    paragrafo(pdf, "O script automaticamente:")
    item(pdf, "Copia os 7 arquivos do projeto real para app_ordem_servico\\ neste repo.")
    item(pdf, "Cria um commit git com a mensagem que voce informou.")
    item(pdf, "Se nada mudou desde o ultimo checkpoint, avisa e nao commita.")
    paragrafo(pdf, "Exemplos de mensagens boas:")
    item(pdf, "\"agendamentos: todas permissoes individuais ok\"")
    item(pdf, "\"fix: save vazio e redirect de abas\"")
    item(pdf, "\"pre-orcamentos: arvore e guards iniciais\"")

    titulo(pdf, "4.3 Ver historico de checkpoints", 2)
    codigo(
        pdf,
        "cd \"C:\\Users\\israe\\Desktop\\ISRAEL\\arvore de permissao e rastreios\"\n"
        "git log --oneline",
    )
    paragrafo(
        pdf,
        "Cada linha e um ponto seguro. Anote o codigo (ex.: cb76a13) dos checkpoints "
        "importantes.",
    )

    titulo(pdf, "5. Resetar / restaurar quando algo quebrar", 1)
    titulo(pdf, "5.1 Restaurar o ultimo checkpoint", 2)
    codigo(
        pdf,
        "cd \"C:\\Users\\israe\\Desktop\\ISRAEL\\arvore de permissao e rastreios\"\n"
        ".\\restaurar.ps1",
    )
    paragrafo(pdf, "Isso copia os arquivos de volta para Projetos_Python\\app_ordem_servico.")
    item(pdf, "Reinicie o servidor Flask.")
    item(pdf, "Ctrl+F5 no navegador.")

    titulo(pdf, "5.2 Restaurar um checkpoint antigo especifico", 2)
    codigo(
        pdf,
        "git log --oneline\n"
        ".\\restaurar.ps1 -Commit cb76a13",
    )
    paragrafo(
        pdf,
        "Substitua cb76a13 pelo codigo do commit desejado. O script faz checkout "
        "daquele ponto e copia para o projeto real.",
    )

    titulo(pdf, "5.3 Quando usar reset vs continuar", 2)
    tabela_simples(
        pdf,
        ["Situacao", "Acao recomendada"],
        [
            ["Perfil congelado, aba errada, permissoes voltando sozinhas", "restaurar.ps1 + corrigir de novo"],
            ["Um modulo novo quebrou o anterior", "restaurar ultimo checkpoint bom + refazer modulo"],
            ["So um detalhe pequeno errado", "Corrigir direto no projeto real + novo checkpoint"],
        ],
    )

    titulo(pdf, "6. Quando levar para o repositorio ORIGINAL", 1)
    paragrafo(
        pdf,
        "So migre para app_ordem_servico no GitHub quando TODA a etapa planejada "
        "estiver concluida e testada. Exemplo de etapa completa:",
    )
    item(pdf, "Agendamentos - todas permissoes + rastreio [ok no checkpoint inicial]")
    item(pdf, "Pre-Orcamentos - pendente")
    item(pdf, "Ordem de Servico (abas) - pendente")
    item(pdf, "Lista O.S., Requisicoes, Estoque, Config - conforme planejamento")

    titulo(pdf, "6.1 Checklist antes do commit no original", 2)
    item(pdf, "[ ] Todos os modulos da etapa testados com usuario nao-admin")
    item(pdf, "[ ] Nenhum perfil congelado ao logar")
    item(pdf, "[ ] Salvar permissoes parciais funciona (nao repoe template)")
    item(pdf, "[ ] Rastreio grava acoes corretas em Configuracoes -> Atividade")
    item(pdf, "[ ] Ultimo checkpoint salvo neste repo com mensagem clara")
    item(pdf, "[ ] Servidor reiniciado + Ctrl+F5 validados")

    titulo(pdf, "6.2 Como commitar no repositorio original", 2)
    paragrafo(pdf, "No PowerShell, na pasta do projeto principal:")
    codigo(
        pdf,
        "cd \"C:\\Users\\israe\\Desktop\\ISRAEL\\Projetos_Python\\app_ordem_servico\"\n"
        "git status\n"
        "git add app.py permissoes_arvore_os.py templates/index.html\n"
        "git add perfis_app.py atividade_log.py presenca_telespectador.py agendamentos.py\n"
        "git commit -m \"feat: permissoes granulares e rastreio (etapa completa)\"\n"
        "git push",
    )
    paragrafo(
        pdf,
        "Inclua no commit apenas os arquivos desta etapa (lista da secao 3) "
        "mais outros que tenham sido alterados de proposito. Revise git status "
        "antes de add - NAO inclua build, .exe, .env ou banco .db.",
    )

    titulo(pdf, "7. O que EVITAR (erros comuns)", 1)
    caixa(
        pdf,
        "[x] NAO faca git push no original com trabalho pela metade.\n"
        "[x] NAO pule o checkpoint apos um modulo funcionar.\n"
        "[x] NAO edite arquivos so no repo de checkpoints - sempre edite no projeto REAL.\n"
        "[x] NAO misture alteracoes de Pre-Orcamentos incompletas com commit no original.\n"
        "[x] NAO commite build_executavel/, .exe ou instaladores no original por engano.\n"
        "[x] NAO apague este repositorio ate a etapa estar no GitHub com sucesso.",
        cor_fundo=(255, 245, 245),
    )
    pdf.ln(2)

    titulo(pdf, "7.1 Sinais de que ainda NAO esta pronto para o original", 2)
    item(pdf, "Usuario abre em aba errada (ex.: O.S. em vez de Agendamentos)")
    item(pdf, "Desmarcar permissoes e salvar faz tudo voltar marcado")
    item(pdf, "App trava ou fica em branco apos login")
    item(pdf, "Botoes visiveis sem permissao correspondente")
    item(pdf, "API aceita acao que deveria retornar 403")
    item(pdf, "Rastreio nao registra a acao ou registra errado")

    titulo(pdf, "7.2 O que pode ir para o original sem esta etapa", 2)
    paragrafo(
        pdf,
        "Correcoes em modulos que NAO passam pela arvore de permissoes podem ir "
        "direto ao git original, por exemplo:",
    )
    item(pdf, "Correcao de PDF, catalogo, kits de motor")
    item(pdf, "Ajustes de build/instalador (sem misturar com permissoes)")
    item(pdf, "Bugs em pre_orcamentos.py se Pre-Orcamentos ainda nao entrou na arvore")

    titulo(pdf, "8. Resumo rapido (cola na parede)", 1)
    tabela_simples(
        pdf,
        ["Quero...", "Comando / acao"],
        [
            ["Salvar ponto seguro", "salvar_checkpoint.ps1 -Mensagem \"...\""],
            ["Ver historico", "git log --oneline"],
            ["Voltar ao ultimo bom", "restaurar.ps1"],
            ["Voltar a commit antigo", "restaurar.ps1 -Commit CODIGO"],
            ["Ir para o original", "Checklist secao 6 + git commit no app_ordem_servico"],
            ["Algo quebrou", "restaurar.ps1 primeiro, depois investigar"],
        ],
    )

    titulo(pdf, "9. Checkpoint inicial ja salvo", 1)
    paragrafo(pdf, "O primeiro commit deste repositorio registra:")
    item(pdf, "Agendamentos com permissoes granulares individuais funcionando")
    item(pdf, "Rastreio: criar, reagendar, cancelar, emergencia, preparar O.S., conversao")
    item(pdf, "Correcoes: save sem repor template, redirect de abas, ocultar O.S.")
    paragrafo(
        pdf,
        "Para ver o codigo deste ponto: git log --oneline e use o hash no restaurar.ps1.",
    )

    pdf.output(str(_SAIDA))
    return _SAIDA


if __name__ == "__main__":
    path = gerar()
    print(f"PDF gerado: {path}")

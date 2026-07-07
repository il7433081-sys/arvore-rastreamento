# Árvore de permissão e rastreios

Repositório **separado** do [app_ordem_servico](https://github.com/il7433081-sys/app_ordem_servico.git).

Guarda checkpoints dos arquivos ligados a permissões granulares e rastreio de atividade. Se uma próxima alteração quebrar o app, restaure daqui sem mexer no git principal.

## Arquivos versionados

| Arquivo | Papel |
|---------|--------|
| `app_ordem_servico/permissoes_arvore_os.py` | Árvore de permissões e mapa de módulos |
| `app_ordem_servico/perfis_app.py` | Perfis de usuário |
| `app_ordem_servico/atividade_log.py` | Log de atividade (rastreio) |
| `app_ordem_servico/presenca_telespectador.py` | Presença e usuários rastreáveis |
| `app_ordem_servico/agendamentos.py` | Módulo Agendamentos |
| `app_ordem_servico/app.py` | APIs, checagens e registro de rastreio |
| `app_ordem_servico/templates/index.html` | UI de permissões e guards no frontend |

## Salvar um checkpoint (após testar e aprovar)

No PowerShell, na pasta deste repositório:

```powershell
.\salvar_checkpoint.ps1 -Mensagem "agendamentos: só visualizar ok"
```

Isso copia os arquivos atuais do app, faz commit e você pode continuar no git principal à vontade.

## Restaurar no projeto

Copia os arquivos deste repo de volta para `Projetos_Python\app_ordem_servico`:

```powershell
.\restaurar.ps1
```

Restaurar um commit antigo (lista antes com `git log --oneline`):

```powershell
.\restaurar.ps1 -Commit abc1234
```

Depois: **reiniciar o servidor Flask** e **Ctrl+F5** no navegador.

## Histórico

```powershell
git log --oneline
```

Cada commit = um ponto seguro testado (ex.: módulo Agendamentos completo, correção de save vazio, redirect de abas).

## Checkpoint inicial

- **Agendamentos** com permissões granulares individuais funcionando
- Rastreio: criar, reagendar, cancelar, emergência, preparar O.S., conversão ao gravar O.S.
- Correções: save sem repor template, redirect para primeira aba visível, ocultar O.S. corretamente

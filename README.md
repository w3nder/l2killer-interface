# L2Killer Interface — WT

A branch `develop` reúne as mudanças em teste. Ela ainda não é um novo ZIP/release.
Projeto independente de um player, sem vínculo com o dono ou a equipe do L2Killer.

Patch de interface para o cliente **Lineage II C4 do L2Killer**, desenvolvido por **Wender (WT)**.

## Download da system pronta

[Baixar L2Killer-System-WT.zip](https://github.com/w3nder/l2killer-interface/releases/latest/download/L2Killer-System-WT.zip)

Feche o jogo, guarde sua pasta `system` anterior e copie a pasta `system` do ZIP
para o cliente L2Killer. Abra `system/l2.exe` normalmente. A DLL auxiliar já está
incluída; não remova `C4Bars.dll`. Para desfazer, restaure a pasta anterior inteira.

O repositório é privado: o download exige uma conta com acesso.

## Funcionalidades

- Três barras com páginas independentes e seletores nativos nas duas extras.
- Botão para recolher as extras e voltar à barra original; expandir preserva as páginas.
- Descrição nativa dos itens ao passar o mouse.
- F1–F12 na primeira barra, Alt+F1–F12 na segunda e Ctrl+Alt+F1–F12 na terceira.
- Crédito local, em dourado, imediatamente após a mensagem de sistema/aviso
  que contém “Welcome” e “Lineage”: **[ WT ] Patch by Wender | Enjoy the game!**
- Crédito uma vez por abertura do cliente, sem temporizador e sem mensagem de rede.

As preferências ficam em `C4Bars.ini`: `Bars`, `SecondPage`, `ThirdPage`,
`ThirdModifier` e `ShowCredit`. `ShowCredit=0` desativa o crédito.

## Equipamentos do alvo em desenvolvimento

Ao expandir o alvo de um jogador, exibe os ícones dos equipamentos disponíveis
no cache do cliente abaixo de clan e ally. O nome aparece ao passar o mouse.
Trocar de alvo ou de equipamento atualiza a lista. NPCs não recebem esse painel.
Não mostra inventário completo, encantamentos ou slots que o servidor não enviou.
Use `TargetEquipment=0` na seção `[C4Bars]` para desativar. Validação visual pendente.

## Auto Potion em desenvolvimento

CP, HP, Mana e Quick HP, com itens arrastados da maleta ou dos atalhos.
Configuração em inglês, janela nativa móvel e barra compacta para ligar/desligar.
Itens, percentuais e preferências são restaurados na entrada do personagem.
O jogador escolhe percentual, intervalo ou ambos; não há cooldown fixo extra
entre poções no modo percentual.

O uso manual tem prioridade enquanto aguarda atualização do inventário.
Uma recuperação de 2 segundos evita ficar parado se a resposta não chegar.
O cursor sobre a maleta ou a barra não pausa as poções.
A correlação por item e o cooldown nativo continuam em pesquisa.

## Código-fonte e compilação

Este repositório contém o código do patch, não o código-fonte do cliente original.
A system pronta está no asset da release. As DLLs originais não entram no Git.

Requisitos: Python 3, MinGW-w64 para x86 (`i686-w64-mingw32-g++`, GCC e objcopy),
Clang++ para o teste de geometria e Unicorn para a emulação x86.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
python3 patch/build_patch.py --l2killer --source /caminho/para/NWindow.dll
clang++ -std=c++17 -Wall -Wextra -Werror patch/test_layout.cpp -o /tmp/c4bars-layout
/tmp/c4bars-layout
.venv/bin/python patch/test_binary.py --l2killer --source /caminho/para/NWindow.dll
.venv/bin/python patch/test_native_window.py --l2killer --source /caminho/para/NWindow.dll
.venv/bin/python patch/test_manual_priority.py --l2killer --source /caminho/para/NWindow.dll
clang++ -std=c++17 -Wall -Wextra -Werror patch/test_potion_policy.cpp -o /tmp/c4bars-potions
/tmp/c4bars-potions
```

A entrada deve ser a **NWindow.dll original, sem o patch**, com SHA-256:

```text
1fdcf9b455ef7ff93dfedeb9667e61a9874e31fe125982437d98c4d0adea3cce
```

O build recusa outra versão e gera `dist/C4Bars-L2Killer-teste-05/`, com as DLLs,
configuração, instaladores opcionais e manifesto de hashes. Ele não altera a entrada.
Sem `--source`, o perfil L2Killer procura `sources/NWindow-L2Killer.dll`.
Nesta branch o Auto Potion exige `--l2killer`; os endereços nativos não são compatíveis com outro perfil.

## Organização

| Arquivo | Função |
| --- | --- |
| `patch/C4Bars.cpp` | Desenho, mouse, teclado, tooltip e crédito após Welcome |
| `patch/layout.h` | Geometria e páginas independentes |
| `patch/profile.h` | Endereços específicos das versões analisadas |
| `patch/entry.S` | Wrapper de entrada PE, preservando o entrypoint original |
| `patch/build_patch.py` | Compilação, validação de versão e pacote |
| `patch/test_binary.py` | Execução x86 com callbacks Windows/cliente simulados |
| `patch/test_layout.cpp` | Posições, bordas e identificação das barras |
| `docs/release-v1.0.0.json` | Hashes da versão distribuída e confirmação do teste |

## Validação e limites

A versão distribuída foi testada no jogo pelo usuário, incluindo nova abertura.
Os testes automatizados cobrem geometria, convenções de chamada, restauração de
estado, atalhos, ordem do crédito e prevenção de duplicação. Eles simulam o
renderer e não substituem o teste visual. Não há suporte genérico a outros clientes.

No Mac de desenvolvimento foi usado Wine 11.0_1 com
`WINE_D3D_CONFIG=renderer=gl,csmt=0`; Vulkan apresentou tela preta. Ocorreram
falhas intermitentes na inicialização gráfica do Wine. O ZIP não inclui Wine
nem o cliente completo. O cliente C4 continua necessário.

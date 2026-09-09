# Compilar e testar

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
O Auto Potion exige `--l2killer`; os endereços nativos não são compatíveis com outro perfil.


## Testes dos recursos adicionais

```bash
.venv/bin/python patch/test_target_equipment.py --l2killer --source /caminho/para/NWindow.dll
.venv/bin/python patch/test_local_appearance.py --l2killer --source /caminho/para/NWindow.dll
```

Use o mesmo arquivo original em todos os testes. Os testes x86 simulam as APIs do
Windows e do cliente. Teste também no jogo antes de propor uma release: abertura,
login, troca de personagem, barras, uso manual com Auto Potion ativo, equipamentos
do alvo e comandos locais. Para alterações de inicialização, valide no Windows 11.

O nome interno `C4Bars-L2Killer-teste-05` identifica o perfil do empacotador;
a versão distribuída e seus hashes ficam em `docs/release-v*.json`.

# Código do patch

As instruções atualizadas de compilação, configuração, download e validação
estão no [README principal](../README.md).

O crédito é inserido após a mensagem Welcome pelo hook local de chat.
Não há temporizador. O patch preserva a entrada PE original e valida os
endereços antes de instalar os hooks. O build usa uma base PE explícita para
que o endereço preferencial da DLL não dependa do caminho de compilação.

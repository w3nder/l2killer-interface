# develop

Base local: três barras independentes, Auto Potion com quatro canais, configuração nativa móvel, persistência e prioridade de uso manual.

Revisão: logs de consumo removidos; sem flush de disco por fragmento; log limitado a 64 KiB; limpeza de referências da janela; verificações de índices e ponteiros; limite de intervalo corrigido; estado de inicialização corrigido; instalação do hook de prioridade tentada uma vez.

Validação: build x86 com warnings tratados como erros, política de poções, 1440 casos de hit/ABI, ciclo da janela e trampoline nativo de uso manual passaram. Wine abriu a versão local. Isso não equivale a teste prolongado de memória nem certifica a nova funcionalidade de equipamentos do alvo, que ainda não está implementada nesta base.

O limite de 2 segundos é uma comparação do relógio, sem Sleep ou bloqueio de thread. Os trampolines permanecem alocados enquanto os hooks existem; descarregamento dinâmico da DLL não é suportado.

Nenhum ZIP/release novo foi criado com este checkpoint.

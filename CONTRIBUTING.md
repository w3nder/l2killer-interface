# Contribuir com a Interface WT

Para corrigir um bug ou propor uma melhoria, abra uma issue com o comportamento
atual e o resultado esperado. Mudanças maiores devem indicar qual função nativa
será afetada antes de mexer nos hooks.

## Código

1. Crie sua branch a partir de `develop`.
2. Siga [o guia de build](docs/building.md) com a NWindow.dll original compatível.
3. Mantenha as alterações focadas e abra o pull request para `develop`.
4. Descreva o que mudou, os testes feitos e o que ainda precisa validar no jogo.

Não envie DLLs originais, executáveis, ZIPs, logs pessoais, credenciais ou arquivos
do cliente ao Git. As dependências proprietárias são fornecidas localmente.

## Cuidados com o cliente

- Confira versão e bytes antes de instalar um hook; não presuma que offsets de outro cliente funcionam.
- Preserve a convenção de chamada, registradores, pilha e estado do renderer.
- Não bloqueie a thread do jogo com sleeps, espera de rede ou disco no caminho de desenho/entrada.
- Não acrescente cooldown oculto ao uso de poções; preserve a prioridade do uso manual.
- Mantenha os textos dentro do cliente em inglês e sem acentos.
- Teste trocas de alvo/personagem e abertura/fechamento de janelas quando relevantes.

Um teste x86 com APIs simuladas verifica ABI e lógica; ele não comprova que o
renderer real ou o Windows iniciarão corretamente. Registre separadamente o que
foi testado em emulação, no Wine e no Windows 11.

## Releases

`main` representa a distribuição. `develop` recebe desenvolvimento. Para uma
release, valide no Windows, gere o ZIP e manifesto, integre à main e publique a
tag correspondente. O download do site deve apontar para o mesmo pacote validado.

Ao contribuir com código original, você concorda com sua distribuição sob a
licença MIT deste projeto. Não inclua material de terceiros sem permissão.

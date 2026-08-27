# FURGfs4 - Sistema de Arquivos

Este é o Trabalho III da disciplina de Sistemas Operacionais.
O projeto consiste na implementação do **FURGfs4**, um pequeno sistema de arquivos baseado em FAT (File Allocation Table) que reside inteiramente dentro de um único arquivo no sistema operacional hospedeiro. 

O trabalho foi desenvolvido inteiramente na linguagem **Python** e opera com manipulação direta de arquivos binários usando pacotes nativos da linguagem.

## Estrutura de Arquivos

O repositório está organizado da seguinte forma:

* `main.py`: O ponto de entrada principal do sistema. Provê uma CLI (Interface de Linha de Comando) baseada num menu numérico para facilitar o uso humano.
* `core/constants.py`: Define todas as configurações-base do FS, como o **tamanho fixo de bloco de 4KB (4096 bytes)**.
* `core/structs.py`: Utiliza o módulo `struct` para montar a matemática exata de bytes das entradas. Ex: Cada entrada de diretório tem *exatos* 128 bytes, permitindo 32 arquivos por bloco de diretório.
* `core/furgfs.py`: O "cérebro" do sistema de arquivos. Contém as implementações dos métodos de leitura/escrita da FAT, Superbloco e manuseio dos dados brutos dentro dos limites físicos do arquivo host.
* `tests/test_script.py`: Um script em lote usado durante o desenvolvimento que prova a funcionalidade 100% de leitura/escrita, *copy in/out*, formatação e travas.

## Operações Suportadas

Através da execução de `main.py`, as seguintes tarefas podem ser executadas (cumprindo os requisitos mínimos exigidos pelas instruções do professor):

1. **Criar FS**: Gera um novo arquivo binário zerado, alocando os espaços reservados e escrevendo a versão incial vazia da FAT e do Root Directory.
2. **Carregar FS**: Conecta a aplicação a um sistema FURGfs4 que já exista no disco (validando seu superbloco interno).
3. **Copy IN (cp)**: Extrai arquivos do disco físico normal (SO host) e aloca dentro dos blocos e FAT do nosso FURGfs4.
4. **Copy OUT (cp)**: O reverso do Copy IN. Navega pela FAT e extrai a cadeia de bits de um arquivo para trazê-lo de volta pro mundo real sem corrompê-lo.
5. **Renomear (mv)**: Troca o nome do arquivo, respeitando limites físicos da estrutura binária.
6. **Remover (rm)**: Limpa a lista FAT do item e revoga o arquivo do diretório, liberando espaço.
7. **Listar (ls)**: Exibe metadados de arquivos salvos (verificando o *gap* que o arquivo gera entre tamanho real e ocupado).
8. **Estatísticas (df)**: Lê o superbloco para reportar quantos megabytes/bytes estão em uso/livres, e o total de blocos da FAT ocupados.
9. **Proteção (protect)**: Chaveia (toggle) um *bit de proteção* interno, rejeitando que o arquivo seja removido ou renomeado se ativado.
10. **Modo Debug**: Analisa a correnteza (chain) de blocos de um determinado arquivo na FAT e imprime no console para fins de debug acadêmico de alocação de espaços.

## Como Executar

O sistema pode ser utilizado instalando o Python, entrando no diretório e invocando o arquivo principal:

```bash
python main.py
```
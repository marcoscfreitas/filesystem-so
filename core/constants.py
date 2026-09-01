"""
constants.py - Constantes globais do sistema de arquivos FURGfs4.

Define os parâmetros estruturais do FS: tamanho de bloco, valores especiais
da FAT, tamanho máximo de nomes e tipos de entrada de diretório.
"""

import struct

# Tamanho de cada bloco físico do FURGfs4 em bytes (4 KB)
BLOCK_SIZE = 4096

# Limites de tamanho do sistema de arquivos (em MB)
MIN_FS_SIZE_MB = 1
MAX_FS_SIZE_MB = 2048  # 2 GB

# Quantidade de blocos reservados para o diretório raiz.
# 4 blocos * 32 entradas/bloco = 128 entradas (> 100, conforme exigido).
ROOT_DIR_BLOCKS = 4

# Valores especiais usados na FAT (File Allocation Table)
FAT_FREE     = 0x00000000  # Bloco livre (disponível para uso)
FAT_EOF      = 0xFFFFFFFF  # Último bloco de uma cadeia (fim de arquivo)
FAT_RESERVED = 0xFFFFFFFE  # Bloco reservado (superbloco, FAT, diretório)

# Tamanho máximo do nome de um arquivo/diretório em bytes
MAX_FILENAME_LEN = 100

# Tipos de entrada de diretório
TYPE_FILE = 0  # Entrada do tipo arquivo
TYPE_DIR  = 1  # Entrada do tipo diretório

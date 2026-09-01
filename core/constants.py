import struct

# tamanho de cada bloco físico em bytes (4kb)
BLOCK_SIZE = 4096

# limites de tamanho do fs em mb
MIN_FS_SIZE_MB = 1
MAX_FS_SIZE_MB = 2048  # 2gb de limite pra não travar tudo

# quantidade de blocos reservados para o diretório raiz
# 4 blocos * 32 entradas por bloco = 128 entradas (passa de 100 como o prof pediu)
ROOT_DIR_BLOCKS = 4

# valores especiais que a gente usa na fat
FAT_FREE     = 0x00000000  # bloco tá livre pra uso
FAT_EOF      = 0xFFFFFFFF  # último bloco do arquivo
FAT_RESERVED = 0xFFFFFFFE  # bloco reservado (tipo o superbloco, fat e raiz)

# tamanho máximo do nome de um arquivo
MAX_FILENAME_LEN = 100

# tipos de arquivo no diretório
TYPE_FILE = 0  # é um arquivo
TYPE_DIR  = 1  # é um diretório

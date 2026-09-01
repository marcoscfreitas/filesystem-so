"""
structs.py - Estruturas de dados binárias do FURGfs4.

Usa o módulo 'struct' do Python para serializar/desserializar o Superbloco
e as Entradas de Diretório em formato binário de tamanho fixo, garantindo
alinhamento perfeito com o tamanho do bloco de 4096 bytes.
"""

import struct
from .constants import MAX_FILENAME_LEN

# =====================================================================
# SUPERBLOCO (Cabeçalho do sistema de arquivos)
# =====================================================================
# Formato little-endian (<):
#   8 bytes : Assinatura ("FURGfs4\0") - identifica o FS
#   4 bytes : Tamanho do cabeçalho em bytes (header_size)
#   4 bytes : Tamanho do bloco em bytes (block_size)
#   4 bytes : Total de blocos no FS (total_blocks)
#   4 bytes : Bloco de início da FAT (fat_start_block)
#   4 bytes : Bloco de início dos dados (data_start_block)
#   4 bytes : Quantidade de blocos livres (free_blocks)
#   4 bytes : Bloco de início do diretório raiz (root_dir_start_block)
# Total: 8 + 7×4 = 36 bytes
SUPERBLOCK_FMT = "<8sIIIIIII"
SUPERBLOCK_SIZE = struct.calcsize(SUPERBLOCK_FMT)


# =====================================================================
# ENTRADA DE DIRETÓRIO
# =====================================================================
# Formato little-endian (<):
#   100 bytes : Nome do arquivo/diretório (MAX_FILENAME_LEN)
#     4 bytes : Primeiro bloco na FAT (first_block)
#     4 bytes : Tamanho real do arquivo em bytes (size_bytes)
#     1 byte  : Em uso (in_use: 0=não, 1=sim)
#     1 byte  : Protegido contra escrita/remoção (is_protected: 0=não, 1=sim)
#     1 byte  : Tipo da entrada (type: 0=arquivo, 1=diretório)
#     4 bytes : Timestamp de criação (created)
#     4 bytes : Timestamp de modificação (modified)
#     9 bytes : Padding (preenchimento para alinhar a 128 bytes)
# Total: 100 + 4 + 4 + 1 + 1 + 1 + 4 + 4 + 9 = 128 bytes
# Com 4096 / 128 = 32 entradas por bloco.
DIR_ENTRY_FMT = f"<{MAX_FILENAME_LEN}sIIBBBII9s"
DIR_ENTRY_SIZE = struct.calcsize(DIR_ENTRY_FMT)

# Verifica que o tamanho da entrada está correto em tempo de importação
assert DIR_ENTRY_SIZE == 128, f"DIR_ENTRY_SIZE é {DIR_ENTRY_SIZE}, esperado 128"


def pack_superblock(signature, header_size, block_size, total_blocks,
                    fat_start, data_start, free_blocks, root_start):
    """Serializa o superbloco para bytes no formato binário."""
    return struct.pack(
        SUPERBLOCK_FMT,
        signature.encode('utf-8'),
        header_size,
        block_size,
        total_blocks,
        fat_start,
        data_start,
        free_blocks,
        root_start
    )


def unpack_superblock(data):
    """Desserializa bytes para um dicionário representando o superbloco."""
    unpacked = struct.unpack(SUPERBLOCK_FMT, data[:SUPERBLOCK_SIZE])
    return {
        'signature':           unpacked[0].decode('utf-8').strip('\x00'),
        'header_size':         unpacked[1],
        'block_size':          unpacked[2],
        'total_blocks':        unpacked[3],
        'fat_start_block':     unpacked[4],
        'data_start_block':    unpacked[5],
        'free_blocks':         unpacked[6],
        'root_dir_start_block': unpacked[7],
    }


def pack_dir_entry(name, first_block, size_bytes, in_use,
                   is_protected, entry_type, created, modified):
    """Serializa uma entrada de diretório para bytes (128 bytes fixos)."""
    name_bytes = name.encode('utf-8')
    # Trunca se o nome for maior que o permitido
    if len(name_bytes) > MAX_FILENAME_LEN:
        name_bytes = name_bytes[:MAX_FILENAME_LEN]

    return struct.pack(
        DIR_ENTRY_FMT,
        name_bytes,
        first_block,
        size_bytes,
        in_use,
        is_protected,
        entry_type,
        created,
        modified,
        b'\x00' * 9  # Padding de alinhamento
    )


def unpack_dir_entry(data):
    """Desserializa bytes para um dicionário representando uma entrada de diretório."""
    unpacked = struct.unpack(DIR_ENTRY_FMT, data[:DIR_ENTRY_SIZE])
    return {
        'name':         unpacked[0].decode('utf-8', errors='ignore').strip('\x00'),
        'first_block':  unpacked[1],
        'size_bytes':   unpacked[2],
        'in_use':       unpacked[3],
        'is_protected': unpacked[4],
        'type':         unpacked[5],
        'created':      unpacked[6],
        'modified':     unpacked[7],
    }

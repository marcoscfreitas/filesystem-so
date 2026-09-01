import struct
from .constants import MAX_FILENAME_LEN

# estrutura do superbloco (o cabeçalho do sistema):
#   8 bytes pro nome da assinatura
#   4 bytes pro tamanho do cabeçalho
#   4 bytes pro tamanho do bloco
#   4 bytes pro total de blocos
#   4 bytes pro bloco onde começa a fat
#   4 bytes pro bloco onde começam os dados
#   4 bytes pros blocos livres
#   4 bytes pro bloco do diretório raiz
# total dá 36 bytes. 
SUPERBLOCK_FMT = "<8sIIIIIII"
SUPERBLOCK_SIZE = struct.calcsize(SUPERBLOCK_FMT)


# estrutura de uma entrada de diretório (arquivos salvos):
#   100 bytes pro nome do arquivo
#     4 bytes pro bloco inicial dele na fat
#     4 bytes pro tamanho real do arquivo
#     1 byte  pra dizer se a entrada tá em uso (0 não, 1 sim)
#     1 byte  pra proteção (0 não, 1 sim)
#     1 byte  pro tipo (0 arquivo, 1 diretório)
#     4 bytes de data de criação
#     4 bytes de data de modificação
#     9 bytes de padding pra bater exatos 128 bytes
# com isso cabem 32 arquivos por bloco de 4kb.
DIR_ENTRY_FMT = f"<{MAX_FILENAME_LEN}sIIBBBII9s"
DIR_ENTRY_SIZE = struct.calcsize(DIR_ENTRY_FMT)

# checa se o tamanho bateu os 128
assert DIR_ENTRY_SIZE == 128, f"tamanho da entrada deu {DIR_ENTRY_SIZE}, devia ser 128"


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
    # corta o nome se for maior que o permitido
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
        b'\x00' * 9  # enche de zeros pra bater o tamanho
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

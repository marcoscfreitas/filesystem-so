import struct
from .constants import MAX_FILENAME_LEN

# Superblock:
# 8 bytes: Signature ("FURGfs4\0")
# 4 bytes: Block size
# 4 bytes: Total blocks
# 4 bytes: FAT start block
# 4 bytes: Data start block
# 4 bytes: Free blocks
# 4 bytes: Root dir start block
SUPERBLOCK_FMT = "<8sIIIIII"
SUPERBLOCK_SIZE = struct.calcsize(SUPERBLOCK_FMT)

# Directory Entry:
# MAX_FILENAME_LEN bytes (100): Filename
# 4 bytes: first_block
# 4 bytes: size_bytes
# 1 byte: in_use (0: false, 1: true)
# 1 byte: is_protected (0: false, 1: true)
# 1 byte: type (0: file, 1: dir)
# 4 bytes: created (timestamp)
# 4 bytes: modified (timestamp)
# Padding to reach exactly 128 bytes for perfect 4096/128 = 32 entries per block alignment.
# 100 + 4 + 4 + 1 + 1 + 1 + 4 + 4 = 119 bytes.
# We need 9 bytes padding to make it 128 bytes.
DIR_ENTRY_FMT = f"<{MAX_FILENAME_LEN}sIIBBBII9s"
DIR_ENTRY_SIZE = struct.calcsize(DIR_ENTRY_FMT)

assert DIR_ENTRY_SIZE == 128, f"DIR_ENTRY_SIZE is {DIR_ENTRY_SIZE}, expected 128"

def pack_superblock(signature, block_size, total_blocks, fat_start, data_start, free_blocks, root_start):
    return struct.pack(SUPERBLOCK_FMT, signature.encode('utf-8'), block_size, total_blocks, fat_start, data_start, free_blocks, root_start)

def unpack_superblock(data):
    unpacked = struct.unpack(SUPERBLOCK_FMT, data[:SUPERBLOCK_SIZE])
    return {
        'signature': unpacked[0].decode('utf-8').strip('\x00'),
        'block_size': unpacked[1],
        'total_blocks': unpacked[2],
        'fat_start_block': unpacked[3],
        'data_start_block': unpacked[4],
        'free_blocks': unpacked[5],
        'root_dir_start_block': unpacked[6]
    }

def pack_dir_entry(name, first_block, size_bytes, in_use, is_protected, entry_type, created, modified):
    name_bytes = name.encode('utf-8')
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
        b'\x00' * 9 # Padding
    )

def unpack_dir_entry(data):
    unpacked = struct.unpack(DIR_ENTRY_FMT, data[:DIR_ENTRY_SIZE])
    return {
        'name': unpacked[0].decode('utf-8', errors='ignore').strip('\x00'),
        'first_block': unpacked[1],
        'size_bytes': unpacked[2],
        'in_use': unpacked[3],
        'is_protected': unpacked[4],
        'type': unpacked[5],
        'created': unpacked[6],
        'modified': unpacked[7]
    }

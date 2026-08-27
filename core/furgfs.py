import os
import time
import struct
import math
from .constants import *
from .structs import *

class FURGfs:
    def __init__(self, filepath):
        self.filepath = filepath
        self.sb = None
        
        if os.path.exists(filepath):
            self._load_superblock()
            
    def _load_superblock(self):
        with open(self.filepath, 'rb') as f:
            data = f.read(SUPERBLOCK_SIZE)
            self.sb = unpack_superblock(data)

    def _write_superblock(self):
        with open(self.filepath, 'rb+') as f:
            f.seek(0)
            data = pack_superblock(
                self.sb['signature'],
                self.sb['block_size'],
                self.sb['total_blocks'],
                self.sb['fat_start_block'],
                self.sb['data_start_block'],
                self.sb['free_blocks'],
                self.sb['root_dir_start_block']
            )
            f.write(data)

    def _read_fat(self):
        fat_size_bytes = (self.sb['root_dir_start_block'] - self.sb['fat_start_block']) * BLOCK_SIZE
        with open(self.filepath, 'rb') as f:
            f.seek(self.sb['fat_start_block'] * BLOCK_SIZE)
            fat_data = f.read(fat_size_bytes)
        
        # FAT is an array of 4-byte integers (unsigned)
        num_entries = self.sb['total_blocks']
        return list(struct.unpack(f"<{num_entries}I", fat_data[:num_entries*4]))

    def _write_fat(self, fat):
        fat_size_bytes = (self.sb['root_dir_start_block'] - self.sb['fat_start_block']) * BLOCK_SIZE
        fat_data = struct.pack(f"<{len(fat)}I", *fat)
        # Pad with zeros to fill the fat blocks
        fat_data += b'\x00' * (fat_size_bytes - len(fat_data))
        
        with open(self.filepath, 'rb+') as f:
            f.seek(self.sb['fat_start_block'] * BLOCK_SIZE)
            f.write(fat_data)

    def _read_dir(self, start_block):
        fat = self.read_fat_cached if hasattr(self, 'read_fat_cached') else self._read_fat()
        entries = []
        current_block = start_block
        
        with open(self.filepath, 'rb') as f:
            while current_block != FAT_FREE and current_block < self.sb['total_blocks']:
                f.seek(current_block * BLOCK_SIZE)
                block_data = f.read(BLOCK_SIZE)
                
                # Parse 32 entries per block
                for i in range(0, BLOCK_SIZE, DIR_ENTRY_SIZE):
                    entry_data = block_data[i:i+DIR_ENTRY_SIZE]
                    entry = unpack_dir_entry(entry_data)
                    entries.append(entry)
                
                if current_block == FAT_EOF or fat[current_block] == FAT_EOF:
                    break
                current_block = fat[current_block]
                
        return entries

    def _write_dir(self, start_block, entries):
        fat = self.read_fat_cached if hasattr(self, 'read_fat_cached') else self._read_fat()
        current_block = start_block
        entry_idx = 0
        total_entries = len(entries)
        
        with open(self.filepath, 'rb+') as f:
            while current_block != FAT_FREE and current_block < self.sb['total_blocks']:
                block_data = bytearray()
                
                # Write up to 32 entries
                for _ in range(BLOCK_SIZE // DIR_ENTRY_SIZE):
                    if entry_idx < total_entries:
                        e = entries[entry_idx]
                        block_data += pack_dir_entry(
                            e['name'], e['first_block'], e['size_bytes'], 
                            e['in_use'], e['is_protected'], e['type'], 
                            e['created'], e['modified']
                        )
                        entry_idx += 1
                    else:
                        # Empty entry padding
                        block_data += pack_dir_entry("", 0, 0, 0, 0, 0, 0, 0)
                        
                f.seek(current_block * BLOCK_SIZE)
                f.write(block_data)
                
                if current_block == FAT_EOF or fat[current_block] == FAT_EOF:
                    break
                current_block = fat[current_block]

    def _find_free_blocks(self, fat, count):
        free_blocks = []
        for i in range(self.sb['data_start_block'], self.sb['total_blocks']):
            if fat[i] == FAT_FREE:
                free_blocks.append(i)
                if len(free_blocks) == count:
                    break
        if len(free_blocks) < count:
            return None
        return free_blocks

    def create_fs(self, size_mb):
        size_bytes = size_mb * 1024 * 1024
        total_blocks = size_bytes // BLOCK_SIZE
        
        # Calculate FAT blocks (4 bytes per entry)
        fat_size_bytes = total_blocks * 4
        fat_blocks = math.ceil(fat_size_bytes / BLOCK_SIZE)
        
        # 1 Superblock, then FAT, then 1 Root Dir block, then Data
        fat_start = 1
        root_start = fat_start + fat_blocks
        data_start = root_start + 1 # 1 block for root dir initially
        free_blocks = total_blocks - data_start
        
        if free_blocks <= 0:
            raise ValueError("Size too small to create FS.")
            
        with open(self.filepath, 'wb') as f:
            # Write Superblock
            sb_data = pack_superblock("FURGfs4\0", BLOCK_SIZE, total_blocks, fat_start, data_start, free_blocks, root_start)
            f.write(sb_data)
            f.write(b'\x00' * (BLOCK_SIZE - SUPERBLOCK_SIZE))
            
            # Write FAT
            fat = [FAT_FREE] * total_blocks
            fat[0] = FAT_RESERVED # Superblock
            for i in range(fat_start, root_start):
                fat[i] = FAT_RESERVED # FAT blocks
            fat[root_start] = FAT_EOF # Root dir
            
            fat_bytes = struct.pack(f"<{total_blocks}I", *fat)
            f.write(fat_bytes)
            f.write(b'\x00' * ((fat_blocks * BLOCK_SIZE) - len(fat_bytes)))
            
            # Write Root Dir
            root_entries = [pack_dir_entry("", 0, 0, 0, 0, 0, 0, 0)] * (BLOCK_SIZE // DIR_ENTRY_SIZE)
            for entry in root_entries:
                f.write(entry)
                
            # Truncate to desired size
            f.seek(size_bytes - 1)
            f.write(b'\x00')
            
        self._load_superblock()
        print(f"Sistema de arquivos criado com sucesso. {size_mb} MB")

    def copy_in(self, source, dest):
        if not os.path.exists(source):
            print(f"Arquivo de origem {source} não existe.")
            return
            
        file_size = os.path.getsize(source)
        blocks_needed = math.ceil(file_size / BLOCK_SIZE)
        
        if blocks_needed > self.sb['free_blocks']:
            print("Espaço insuficiente no FURGfs4.")
            return
            
        fat = self._read_fat()
        self.read_fat_cached = fat # Cache for dir ops
        entries = self._read_dir(self.sb['root_dir_start_block'])
        
        # Check if file exists
        free_entry_idx = -1
        for i, e in enumerate(entries):
            if e['in_use'] and e['name'] == dest:
                print("Arquivo já existe no FURGfs4.")
                return
            if not e['in_use'] and free_entry_idx == -1:
                free_entry_idx = i
                
        if free_entry_idx == -1:
            print("Diretório raiz cheio.")
            return
            
        # Allocate blocks
        blocks = self._find_free_blocks(fat, blocks_needed)
        if not blocks and blocks_needed > 0:
            print("Não foi possível alocar os blocos.")
            return
            
        # Write data and update FAT
        first_block = blocks[0] if blocks else 0
        if blocks_needed > 0:
            with open(source, 'rb') as f_src, open(self.filepath, 'rb+') as f_dst:
                for i in range(blocks_needed):
                    b = blocks[i]
                    if i < blocks_needed - 1:
                        fat[b] = blocks[i+1]
                    else:
                        fat[b] = FAT_EOF
                    
                    data = f_src.read(BLOCK_SIZE)
                    f_dst.seek(b * BLOCK_SIZE)
                    f_dst.write(data)
                    f_dst.write(b'\x00' * (BLOCK_SIZE - len(data))) # pad last block
                    
        # Update dir entry
        now = int(time.time())
        entries[free_entry_idx] = {
            'name': dest,
            'first_block': first_block,
            'size_bytes': file_size,
            'in_use': 1,
            'is_protected': 0,
            'type': TYPE_FILE,
            'created': now,
            'modified': now
        }
        
        print(f"DEBUG: free_entry_idx={free_entry_idx}, entry modified: {entries[free_entry_idx]}")
        self._write_dir(self.sb['root_dir_start_block'], entries)
        self._write_fat(fat)
        self.sb['free_blocks'] -= blocks_needed
        self._write_superblock()
        print(f"Arquivo {dest} copiado para o FURGfs4 com sucesso.")
        del self.read_fat_cached

    def copy_out(self, source, dest):
        fat = self._read_fat()
        self.read_fat_cached = fat
        entries = self._read_dir(self.sb['root_dir_start_block'])
        del self.read_fat_cached
        
        for e in entries:
            if e['in_use'] and e['name'] == source:
                if e['type'] == TYPE_DIR:
                    print(f"{source} é um diretório.")
                    return
                
                with open(dest, 'wb') as f_dst, open(self.filepath, 'rb') as f_src:
                    bytes_left = e['size_bytes']
                    current_block = e['first_block']
                    
                    while bytes_left > 0 and current_block != FAT_FREE:
                        f_src.seek(current_block * BLOCK_SIZE)
                        to_read = min(bytes_left, BLOCK_SIZE)
                        data = f_src.read(to_read)
                        f_dst.write(data)
                        bytes_left -= to_read
                        
                        if fat[current_block] == FAT_EOF:
                            break
                        current_block = fat[current_block]
                print(f"Arquivo {source} extraído com sucesso para {dest}.")
                return
        print(f"Arquivo {source} não encontrado no FURGfs4.")

    def rename(self, old_name, new_name):
        fat = self._read_fat()
        self.read_fat_cached = fat
        entries = self._read_dir(self.sb['root_dir_start_block'])
        
        # Check if new name exists
        for e in entries:
            if e['in_use'] and e['name'] == new_name:
                print(f"Já existe um arquivo chamado {new_name}.")
                return
                
        # Find and rename
        for e in entries:
            if e['in_use'] and e['name'] == old_name:
                if e['is_protected']:
                    print(f"Erro: {old_name} está protegido contra alterações.")
                    return
                e['name'] = new_name
                e['modified'] = int(time.time())
                self._write_dir(self.sb['root_dir_start_block'], entries)
                print(f"Arquivo renomeado de {old_name} para {new_name}.")
                del self.read_fat_cached
                return
        print(f"Arquivo {old_name} não encontrado.")
        del self.read_fat_cached

    def remove(self, filename):
        fat = self._read_fat()
        self.read_fat_cached = fat
        entries = self._read_dir(self.sb['root_dir_start_block'])
        
        for e in entries:
            if e['in_use'] and e['name'] == filename:
                if e['is_protected']:
                    print(f"Erro: {filename} está protegido contra remoção.")
                    del self.read_fat_cached
                    return
                    
                # Free blocks
                current_block = e['first_block']
                blocks_freed = 0
                while current_block != FAT_FREE and current_block < self.sb['total_blocks']:
                    nxt = fat[current_block]
                    fat[current_block] = FAT_FREE
                    blocks_freed += 1
                    if nxt == FAT_EOF:
                        break
                    current_block = nxt
                    
                e['in_use'] = 0
                self._write_dir(self.sb['root_dir_start_block'], entries)
                self._write_fat(fat)
                self.sb['free_blocks'] += blocks_freed
                self._write_superblock()
                print(f"Arquivo {filename} removido.")
                del self.read_fat_cached
                return
        print(f"Arquivo {filename} não encontrado.")
        del self.read_fat_cached
        
    def list_dir(self):
        entries = self._read_dir(self.sb['root_dir_start_block'])
        print(f"{'Nome':<30} | {'Tamanho Real (B)':<18} | {'Tamanho Ocupado no FS (B)':<25} | {'Protegido'}")
        print("-" * 100)
        for e in entries:
            if e['in_use']:
                # Calculate occupied size
                blocks = math.ceil(e['size_bytes'] / BLOCK_SIZE)
                if blocks == 0 and e['type'] == TYPE_DIR:
                    # Dirs usually occupy at least 1 block in our simplistic model
                    blocks = 1
                elif blocks == 0 and e['type'] == TYPE_FILE:
                    blocks = 0
                    
                occupied = blocks * BLOCK_SIZE
                prot = "Sim" if e['is_protected'] else "Não"
                print(f"{e['name']:<30} | {e['size_bytes']:<18} | {occupied:<25} | {prot}")

    def df(self):
        total_bytes = self.sb['total_blocks'] * BLOCK_SIZE
        free_bytes = self.sb['free_blocks'] * BLOCK_SIZE
        used_bytes = total_bytes - free_bytes
        
        print(f"Estatísticas do FURGfs4:")
        print(f"Tamanho total: {total_bytes / (1024*1024):.2f} MB ({total_bytes} bytes)")
        print(f"Espaço livre:  {free_bytes / (1024*1024):.2f} MB ({free_bytes} bytes) - {free_bytes/total_bytes*100:.1f}%")
        print(f"Espaço usado:  {used_bytes / (1024*1024):.2f} MB ({used_bytes} bytes) - {used_bytes/total_bytes*100:.1f}%")
        print(f"Blocos Livres: {self.sb['free_blocks']} de {self.sb['total_blocks'] - self.sb['data_start_block']}")

    def protect(self, filename):
        fat = self._read_fat()
        self.read_fat_cached = fat
        entries = self._read_dir(self.sb['root_dir_start_block'])
        
        for e in entries:
            if e['in_use'] and e['name'] == filename:
                e['is_protected'] = 1 if e['is_protected'] == 0 else 0
                status = "protegido" if e['is_protected'] else "desprotegido"
                self._write_dir(self.sb['root_dir_start_block'], entries)
                print(f"Arquivo {filename} agora está {status}.")
                del self.read_fat_cached
                return
        print(f"Arquivo {filename} não encontrado.")
        del self.read_fat_cached

    def debug(self, filename):
        fat = self._read_fat()
        entries = self._read_dir(self.sb['root_dir_start_block'])
        
        for e in entries:
            if e['in_use'] and e['name'] == filename:
                print(f"Debug do arquivo '{filename}':")
                print(f"Tamanho: {e['size_bytes']} bytes")
                
                blocks = []
                current = e['first_block']
                while current != FAT_FREE and current < self.sb['total_blocks']:
                    blocks.append(current)
                    if fat[current] == FAT_EOF:
                        break
                    current = fat[current]
                
                print(f"Blocos Físicos ({len(blocks)} blocos): {blocks}")
                return
        print(f"Arquivo {filename} não encontrado.")

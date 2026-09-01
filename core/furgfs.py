import os
import time
import struct
import math
from .constants import *
from .structs import *


class FURGfs:
    """
    Classe principal que gerencia o sistema de arquivos FURGfs4.

    O FURGfs4 reside inteiramente dentro de um arquivo binário no SO hospedeiro.
    Estrutura interna:
        [Superbloco] [FAT] [Diretório Raiz] [Área de Dados]
    """

    def __init__(self, filepath):
        """Inicializa o gerenciador apontando para o arquivo do FS."""
        self.filepath = filepath
        self.sb = None  # superbloco que será carregado depois

        # se o arquivo já existir a gente já lê o cabeçalho
        if os.path.exists(filepath):
            self._load_superblock()

    def _load_superblock(self):
        """Lê o superbloco (primeiros bytes) do arquivo do FS."""
        with open(self.filepath, 'rb') as f:
            data = f.read(SUPERBLOCK_SIZE)
            self.sb = unpack_superblock(data)

    def _write_superblock(self):
        """Grava o superbloco atualizado de volta no início do arquivo."""
        with open(self.filepath, 'rb+') as f:
            f.seek(0)
            data = pack_superblock(
                self.sb['signature'],
                self.sb['header_size'],
                self.sb['block_size'],
                self.sb['total_blocks'],
                self.sb['fat_start_block'],
                self.sb['data_start_block'],
                self.sb['free_blocks'],
                self.sb['root_dir_start_block'],
            )
            f.write(data)

    def _read_fat(self):
        """
        Lê a FAT (File Allocation Table) do disco.

        A FAT é um vetor de inteiros de 4 bytes (uint32), onde cada posição
        corresponde a um bloco e seu valor indica o próximo bloco da cadeia,
        ou um valor especial (FAT_FREE, FAT_EOF, FAT_RESERVED).

        Retorna: lista de inteiros representando a FAT completa.
        """
        fat_size_bytes = (self.sb['root_dir_start_block'] - self.sb['fat_start_block']) * BLOCK_SIZE
        with open(self.filepath, 'rb') as f:
            f.seek(self.sb['fat_start_block'] * BLOCK_SIZE)
            fat_data = f.read(fat_size_bytes)

        num_entries = self.sb['total_blocks']
        return list(struct.unpack(f"<{num_entries}I", fat_data[:num_entries * 4]))

    def _write_fat(self, fat):
        """Grava a FAT atualizada de volta no disco."""
        fat_size_bytes = (self.sb['root_dir_start_block'] - self.sb['fat_start_block']) * BLOCK_SIZE
        fat_data = struct.pack(f"<{len(fat)}I", *fat)
        
        # se faltar espaço, enche de zeros
        fat_data += b'\x00' * (fat_size_bytes - len(fat_data))

        with open(self.filepath, 'rb+') as f:
            f.seek(self.sb['fat_start_block'] * BLOCK_SIZE)
            f.write(fat_data)

    def _read_dir(self, start_block):
        """
        Lê todas as entradas de um diretório percorrendo a cadeia FAT.

        Cada bloco contém 32 entradas de 128 bytes. Se o diretório ocupa
        múltiplos blocos, a cadeia FAT é seguida até encontrar FAT_EOF.

        Parâmetros:
            start_block: bloco inicial do diretório na FAT.
        Retorna:
            lista de dicionários, cada um representando uma entrada.
        """
        fat = self.read_fat_cached if hasattr(self, 'read_fat_cached') else self._read_fat()
        entries = []
        current_block = start_block

        with open(self.filepath, 'rb') as f:
            while current_block != FAT_FREE and current_block < self.sb['total_blocks']:
                f.seek(current_block * BLOCK_SIZE)
                block_data = f.read(BLOCK_SIZE)

                # quebra o bloco em pedaços de 128 bytes
                for i in range(0, BLOCK_SIZE, DIR_ENTRY_SIZE):
                    entry_data = block_data[i:i + DIR_ENTRY_SIZE]
                    entry = unpack_dir_entry(entry_data)
                    entries.append(entry)

                # se achou o fim da cadeia de blocos, pode parar
                if current_block == FAT_EOF or fat[current_block] == FAT_EOF:
                    break
                current_block = fat[current_block]

        return entries

    def _write_dir(self, start_block, entries):
        """
        Escreve a lista de entradas de diretório de volta nos blocos do disco,
        percorrendo a cadeia FAT a partir de start_block.
        """
        fat = self.read_fat_cached if hasattr(self, 'read_fat_cached') else self._read_fat()
        current_block = start_block
        entry_idx = 0
        total_entries = len(entries)

        with open(self.filepath, 'rb+') as f:
            while current_block != FAT_FREE and current_block < self.sb['total_blocks']:
                block_data = bytearray()

                # coloca até 32 arquivos dentro de cada bloco
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
                        # se sobrar espaço, bota lixo vazio
                        block_data += pack_dir_entry("", 0, 0, 0, 0, 0, 0, 0)

                f.seek(current_block * BLOCK_SIZE)
                f.write(block_data)

                # para se acabar a cadeia
                if current_block == FAT_EOF or fat[current_block] == FAT_EOF:
                    break
                current_block = fat[current_block]

    def _find_free_blocks(self, fat, count):
        """
        Procura 'count' blocos livres na FAT (na área de dados).
        Retorna lista de índices de blocos livres, ou None se não houver espaço.
        """
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
        """
        Operação 1: Cria um novo FURGfs4 no tamanho escolhido pelo usuário.

        Layout do arquivo resultante:
            Bloco 0            : Superbloco (cabeçalho)
            Blocos 1..N        : FAT
            Blocos N+1..N+R    : Diretório raiz (ROOT_DIR_BLOCKS blocos)
            Blocos N+R+1..fim  : Área de dados

        Parâmetros:
            size_mb: tamanho do FS em megabytes.
        """
        if size_mb < MIN_FS_SIZE_MB or size_mb > MAX_FS_SIZE_MB:
            print(f"tamanho tem que ser entre {MIN_FS_SIZE_MB} e {MAX_FS_SIZE_MB} mb.")
            return

        size_bytes = size_mb * 1024 * 1024
        total_blocks = size_bytes // BLOCK_SIZE

        # calcula quantos blocos a fat vai precisar (4 bytes por posição)
        fat_size_bytes = total_blocks * 4
        fat_blocks = math.ceil(fat_size_bytes / BLOCK_SIZE)

        # acerta os ponteiros do início de cada parte do disco
        fat_start = 1
        root_start = fat_start + fat_blocks
        data_start = root_start + ROOT_DIR_BLOCKS
        free_blocks = total_blocks - data_start

        if free_blocks <= 0:
            print("Tamanho muito pequeno para criar o FS.")
            return

        with open(self.filepath, 'wb') as f:
            # grava o superbloco logo no comecinho
            sb_data = pack_superblock(
                "FURGfs4\0", SUPERBLOCK_SIZE, BLOCK_SIZE,
                total_blocks, fat_start, data_start, free_blocks, root_start
            )
            f.write(sb_data)
            f.write(b'\x00' * (BLOCK_SIZE - SUPERBLOCK_SIZE))  # enche o resto do bloco 0

            # monta a fat na memória pra gravar tudo de uma vez
            fat = [FAT_FREE] * total_blocks
            fat[0] = FAT_RESERVED  # bloco 0 é intocável (superbloco)
            for i in range(fat_start, root_start):
                fat[i] = FAT_RESERVED  # blocos da fat também não podem ser mexidos

            # liga os blocos do diretório raiz um no outro
            for i in range(ROOT_DIR_BLOCKS - 1):
                fat[root_start + i] = root_start + i + 1
            fat[root_start + ROOT_DIR_BLOCKS - 1] = FAT_EOF  # o último ganha o marcador de fim

            fat_bytes = struct.pack(f"<{total_blocks}I", *fat)
            f.write(fat_bytes)
            f.write(b'\x00' * ((fat_blocks * BLOCK_SIZE) - len(fat_bytes)))

            # agora escreve os blocos vazios do diretório
            empty_entry = pack_dir_entry("", 0, 0, 0, 0, 0, 0, 0)
            entries_per_block = BLOCK_SIZE // DIR_ENTRY_SIZE
            for _ in range(ROOT_DIR_BLOCKS):
                for _ in range(entries_per_block):
                    f.write(empty_entry)

            # estica o arquivo até dar o tamanho final em mb
            f.seek(size_bytes - 1)
            f.write(b'\x00')

        self._load_superblock()
        print(f"Sistema de arquivos criado com sucesso: {size_mb} MB "
              f"({ROOT_DIR_BLOCKS * (BLOCK_SIZE // DIR_ENTRY_SIZE)} entradas de diretório)")

    def copy_in(self, source, dest):
        """
        Operação 2: Copia um arquivo do sistema real para dentro do FURGfs4.

        Parâmetros:
            source: caminho do arquivo no SO hospedeiro.
            dest:   nome do arquivo dentro do FURGfs4.
        """
        if not os.path.exists(source):
            print(f"Arquivo de origem '{source}' não existe.")
            return

        file_size = os.path.getsize(source)
        blocks_needed = math.ceil(file_size / BLOCK_SIZE) if file_size > 0 else 1

        if blocks_needed > self.sb['free_blocks']:
            print("Espaço insuficiente no FURGfs4.")
            return

        fat = self._read_fat()
        self.read_fat_cached = fat
        entries = self._read_dir(self.sb['root_dir_start_block'])

        # primeiro ve se já não tem um arquivo com esse nome
        free_entry_idx = -1
        for i, e in enumerate(entries):
            if e['in_use'] and e['name'] == dest:
                print(f"Arquivo '{dest}' já existe no FURGfs4.")
                del self.read_fat_cached
                return
            if not e['in_use'] and free_entry_idx == -1:
                free_entry_idx = i

        if free_entry_idx == -1:
            print("Diretório raiz cheio (sem entradas livres).")
            del self.read_fat_cached
            return

        # tenta separar os blocos na fat
        blocks = self._find_free_blocks(fat, blocks_needed)
        if blocks is None:
            print("Não foi possível alocar blocos suficientes.")
            del self.read_fat_cached
            return

        first_block = blocks[0]
        with open(source, 'rb') as f_src, open(self.filepath, 'rb+') as f_dst:
            for i in range(blocks_needed):
                b = blocks[i]
                
                # amarra a corrente na fat
                fat[b] = blocks[i + 1] if i < blocks_needed - 1 else FAT_EOF

                data = f_src.read(BLOCK_SIZE)
                f_dst.seek(b * BLOCK_SIZE)
                f_dst.write(data)
                
                # se o último pedaço for curto, enche o resto de zero
                if len(data) < BLOCK_SIZE:
                    f_dst.write(b'\x00' * (BLOCK_SIZE - len(data)))

        # atualiza a entrada no diretório
        now = int(time.time())
        entries[free_entry_idx] = {
            'name': dest,
            'first_block': first_block,
            'size_bytes': file_size,
            'in_use': 1,
            'is_protected': 0,
            'type': TYPE_FILE,
            'created': now,
            'modified': now,
        }

        # salva a fat e o diretorio no disco
        self._write_dir(self.sb['root_dir_start_block'], entries)
        self._write_fat(fat)
        self.sb['free_blocks'] -= blocks_needed
        self._write_superblock()
        del self.read_fat_cached
        print(f"Arquivo '{dest}' copiado para o FURGfs4 com sucesso.")

    def copy_out(self, source, dest):
        """
        Operação 3: Copia um arquivo de dentro do FURGfs4 para o sistema real.

        Percorre a cadeia de blocos na FAT lendo bloco a bloco e escrevendo
        no arquivo de destino, respeitando o tamanho real do arquivo (sem padding).

        Parâmetros:
            source: nome do arquivo dentro do FURGfs4.
            dest:   caminho do arquivo de destino no SO hospedeiro.
        """
        fat = self._read_fat()
        self.read_fat_cached = fat
        entries = self._read_dir(self.sb['root_dir_start_block'])
        del self.read_fat_cached

        for e in entries:
            if e['in_use'] and e['name'] == source:
                if e['type'] == TYPE_DIR:
                    print(f"'{source}' é um diretório, não um arquivo.")
                    return

                # navega lendo a fat e gravando de volta pra fora
                with open(dest, 'wb') as f_dst, open(self.filepath, 'rb') as f_src:
                    bytes_left = e['size_bytes']
                    current_block = e['first_block']

                    while bytes_left > 0 and current_block != FAT_FREE:
                        f_src.seek(current_block * BLOCK_SIZE)
                        to_read = min(bytes_left, BLOCK_SIZE)
                        data = f_src.read(to_read)
                        f_dst.write(data)
                        bytes_left -= to_read

                        # se der eof, para
                        if fat[current_block] == FAT_EOF:
                            break
                        current_block = fat[current_block]

                print(f"Arquivo '{source}' extraído com sucesso para '{dest}'.")
                return

        print(f"Arquivo '{source}' não encontrado no FURGfs4.")

    def rename(self, old_name, new_name):
        """
        Operação 4: Renomeia um arquivo armazenado no FURGfs4.

        Apenas altera o campo 'name' na entrada de diretório.
        Respeita a proteção: arquivos protegidos não podem ser renomeados.
        """
        fat = self._read_fat()
        self.read_fat_cached = fat
        entries = self._read_dir(self.sb['root_dir_start_block'])

        # verifica se já existe um arquivo com o nome novo
        for e in entries:
            if e['in_use'] and e['name'] == new_name:
                print(f"Já existe um arquivo chamado '{new_name}'.")
                del self.read_fat_cached
                return

        # acha e renomeia
        for e in entries:
            if e['in_use'] and e['name'] == old_name:
                if e['is_protected']:
                    print(f"Erro: '{old_name}' está protegido contra alterações.")
                    del self.read_fat_cached
                    return
                e['name'] = new_name
                e['modified'] = int(time.time())
                self._write_dir(self.sb['root_dir_start_block'], entries)
                print(f"Arquivo renomeado de '{old_name}' para '{new_name}'.")
                del self.read_fat_cached
                return

        print(f"Arquivo '{old_name}' não encontrado.")
        del self.read_fat_cached

    def remove(self, filename):
        """
        Operação 5: Remove um arquivo armazenado no FURGfs4.

        Libera todos os blocos da cadeia FAT (marcando como FAT_FREE),
        marca a entrada de diretório como não utilizada e atualiza o
        contador de blocos livres no superbloco.
        Respeita proteção: arquivos protegidos não podem ser removidos.
        """
        fat = self._read_fat()
        self.read_fat_cached = fat
        entries = self._read_dir(self.sb['root_dir_start_block'])

        for e in entries:
            if e['in_use'] and e['name'] == filename:
                if e['is_protected']:
                    print(f"Erro: '{filename}' está protegido contra remoção.")
                    del self.read_fat_cached
                    return

                # desfaz a cadeia de blocos apagando da fat
                current_block = e['first_block']
                blocks_freed = 0
                while current_block != FAT_FREE and current_block < self.sb['total_blocks']:
                    nxt = fat[current_block]
                    fat[current_block] = FAT_FREE
                    blocks_freed += 1
                    if nxt == FAT_EOF:
                        break
                    current_block = nxt

                # avisa no diretório que liberou
                e['in_use'] = 0

                # salva
                self._write_dir(self.sb['root_dir_start_block'], entries)
                self._write_fat(fat)
                self.sb['free_blocks'] += blocks_freed
                self._write_superblock()
                print(f"Arquivo '{filename}' removido com sucesso.")
                del self.read_fat_cached
                return

        print(f"Arquivo '{filename}' não encontrado.")
        del self.read_fat_cached

    def list_dir(self):
        """
        Operação 6: Lista os arquivos armazenados no FURGfs4.

        Exibe para cada arquivo:
          - Nome
          - Tamanho real em bytes
          - Tamanho efetivamente ocupado no FS (blocos × tamanho do bloco)
          - Se está protegido ou não
        """
        entries = self._read_dir(self.sb['root_dir_start_block'])
        print(f"\n{'Nome':<30} | {'Tam. Real (B)':<15} | {'Tam. Ocupado (B)':<17} | {'Protegido'}")
        print("-" * 90)

        count = 0
        for e in entries:
            if e['in_use']:
                # ve quantos blocos inteiros ele gasta
                blocks = math.ceil(e['size_bytes'] / BLOCK_SIZE) if e['size_bytes'] > 0 else 1
                occupied = blocks * BLOCK_SIZE
                prot = "sim" if e['is_protected'] else "não"
                print(f"{e['name']:<30} | {e['size_bytes']:<15} | {occupied:<17} | {prot}")
                count += 1

        if count == 0:
            print("(vazio)")

    def df(self):
        """
        Operação 7: Exibe o espaço livre em relação ao total do FURGfs4.

        Mostra tamanho total, espaço livre e espaço usado, tanto em bytes
        quanto em MB, com percentuais.
        """
        total_bytes = self.sb['total_blocks'] * BLOCK_SIZE
        free_bytes = self.sb['free_blocks'] * BLOCK_SIZE
        used_bytes = total_bytes - free_bytes

        print(f"\nEstatísticas do FURGfs4:")
        print(f"  Tamanho total: {total_bytes / (1024*1024):.2f} MB ({total_bytes} bytes)")
        print(f"  Espaço livre:  {free_bytes / (1024*1024):.2f} MB ({free_bytes} bytes)"
              f" - {free_bytes / total_bytes * 100:.1f}%")
        print(f"  Espaço usado:  {used_bytes / (1024*1024):.2f} MB ({used_bytes} bytes)"
              f" - {used_bytes / total_bytes * 100:.1f}%")
        total_data_blocks = self.sb['total_blocks'] - self.sb['data_start_block']
        print(f"  Blocos livres: {self.sb['free_blocks']} de {total_data_blocks}")

    def protect(self, filename):
        """
        Operação 8: Alterna a proteção de escrita/remoção de um arquivo.

        Se o arquivo está desprotegido, protege-o.
        Se já está protegido, desprotege-o (toggle).
        """
        fat = self._read_fat()
        self.read_fat_cached = fat
        entries = self._read_dir(self.sb['root_dir_start_block'])

        for e in entries:
            if e['in_use'] and e['name'] == filename:
                # inverte o botão de proteção
                e['is_protected'] = 0 if e['is_protected'] else 1
                status = "protegido" if e['is_protected'] else "desprotegido"
                self._write_dir(self.sb['root_dir_start_block'], entries)
                print(f"Arquivo '{filename}' agora está {status}.")
                del self.read_fat_cached
                return

        print(f"Arquivo '{filename}' não encontrado.")
        del self.read_fat_cached

    def debug(self, filename):
        """
        Operação 9: Modo debug - lista os índices dos blocos físicos
        que compõem o arquivo, percorrendo a cadeia FAT.
        """
        fat = self._read_fat()
        entries = self._read_dir(self.sb['root_dir_start_block'])

        for e in entries:
            if e['in_use'] and e['name'] == filename:
                print(f"\nDebug do arquivo '{filename}':")
                print(f"  Tamanho: {e['size_bytes']} bytes")
                print(f"  Protegido: {'Sim' if e['is_protected'] else 'Não'}")
                print(f"  Criado: {time.ctime(e['created'])}")
                print(f"  Modificado: {time.ctime(e['modified'])}")

                # caça todos os blocos na fat pra mostrar
                blocks = []
                current = e['first_block']
                while current != FAT_FREE and current < self.sb['total_blocks']:
                    blocks.append(current)
                    if fat[current] == FAT_EOF:
                        break
                    current = fat[current]

                print(f"  Blocos físicos ({len(blocks)} blocos): {blocks}")
                return

        print(f"Arquivo '{filename}' não encontrado.")

    def sha256sum(self, filename):
        """
        Operação 10 (Extra): Calcula e exibe o hash SHA-256 de um arquivo
        diretamente do sistema de arquivos, sem extrair os dados.
        """
        import hashlib

        fat = self._read_fat()
        entries = self._read_dir(self.sb['root_dir_start_block'])

        for e in entries:
            if e['in_use'] and e['name'] == filename:
                if e['type'] == TYPE_DIR:
                    print(f"'{filename}' é um diretório.")
                    return

                h = hashlib.sha256()
                bytes_left = e['size_bytes']
                current_block = e['first_block']

                with open(self.filepath, 'rb') as f:
                    while bytes_left > 0 and current_block != FAT_FREE:
                        f.seek(current_block * BLOCK_SIZE)
                        to_read = min(bytes_left, BLOCK_SIZE)
                        data = f.read(to_read)
                        h.update(data)
                        bytes_left -= to_read

                        if fat[current_block] == FAT_EOF:
                            break
                        current_block = fat[current_block]

                print(f"{h.hexdigest()}  {filename}")
                return

        print(f"Arquivo '{filename}' não encontrado.")


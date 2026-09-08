import sys
import os
from core.furgfs import FURGfs

def print_menu():
    """Mostra o painel com as opções de comandos do trabalho"""
    print("\n" + "="*40)
    print("FURGfs4 - Sistema de Arquivos")
    print("="*40)
    print("1. Criar novo FS")
    print("2. Carregar FS existente")
    print("3. Copiar arquivo para o FURGfs4 (cp in)")
    print("4. Copiar arquivo do FURGfs4 (cp out)")
    print("5. Renomear arquivo no FURGfs4 (mv)")
    print("6. Remover arquivo do FURGfs4 (rm)")
    print("7. Listar arquivos (ls)")
    print("8. Exibir espaço livre (df)")
    print("9. Proteger/Desproteger arquivo")
    print("10. Modo debug (listar blocos)")
    print("11. Calcular SHA256 de um arquivo")
    print("12. Buscar arquivo em todo o FURGfs4")
    print("13. Comparar arquivo interno com externo (diff)")
    print("0. Sair")
    print("="*40)

def main():
    """Loop infinito para capturar as opções do teclado"""
    fs = None  # começa sem nenhum disco carregado
    
    while True:
        print_menu()
        choice = input("Escolha uma opção: ")
        
        # opção 1: criar do zero
        if choice == '1':
            filepath = input("Digite o nome do arquivo para o novo FS (ex: disk.fs): ")
            try:
                size_mb = int(input("Tamanho do FS em MB (min 1): "))
                if size_mb < 1:
                    print("Tamanho inválido.")
                    continue
                fs = FURGfs(filepath)
                fs.create_fs(size_mb)
            except ValueError:
                print("Por favor digite um número válido.")
                
        # opção 2: dar load num que já foi criado antes
        elif choice == '2':
            filepath = input("Digite o nome do arquivo do FS: ")
            if not os.path.exists(filepath):
                print(f"Arquivo {filepath} não existe.")
                continue
            fs = FURGfs(filepath)
            if fs.sb:
                print("Sistema de arquivos carregado com sucesso.")
            else:
                print("Falha ao carregar o sistema de arquivos.")
                fs = None
                
        # opção 0: sair
        elif choice == '0':
            print("Saindo...")
            sys.exit(0)
            
        else:
            # se for as outras opções, tem q ter carregado o fs antes
            if fs is None or not fs.sb:
                print("Você precisa criar ou carregar um FS primeiro!")
                continue
                
            # distribuindo pro núcleo do furgfs
            if choice == '3':
                src = input("Caminho do arquivo de origem (sistema real): ")
                dst = input("Nome do arquivo destino (no FURGfs4): ")
                fs.copy_in(src, dst)
            elif choice == '4':
                src = input("Nome do arquivo de origem (no FURGfs4): ")
                dst = input("Caminho do arquivo destino (sistema real): ")
                fs.copy_out(src, dst)
            elif choice == '5':
                old = input("Nome atual do arquivo: ")
                new = input("Novo nome do arquivo: ")
                fs.rename(old, new)
            elif choice == '6':
                filename = input("Nome do arquivo a ser removido: ")
                fs.remove(filename)
            elif choice == '7':
                fs.list_dir()
            elif choice == '8':
                fs.df()
            elif choice == '9':
                filename = input("Nome do arquivo a proteger/desproteger: ")
                fs.protect(filename)
            elif choice == '10':
                filename = input("Nome do arquivo para debug: ")
                fs.debug(filename)
            elif choice == '11':
                filename = input("Nome do arquivo para calcular SHA256: ")
                fs.sha256sum(filename)
            elif choice == '12':
                term = input("Termo a buscar no nome dos arquivos: ")
                fs.search(term)
            elif choice == '13':
                internal = input("Nome do arquivo dentro do FURGfs4: ")
                external = input("Caminho do arquivo externo para comparar: ")
                fs.diff(internal, external)
            else:
                print("Opção inválida.")

if __name__ == "__main__":
    main()

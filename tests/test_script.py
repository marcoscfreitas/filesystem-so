import os
import sys

# Create a dummy file to copy
with open("dummy.txt", "w") as f:
    f.write("Hello, FURGfs4!\n" * 100) # about 1.6KB

print("Starting test...")
os.system("python main.py <<EOF\n1\nfurg.fs\n10\n0\nEOF")
print("FS created.")

os.system("python main.py <<EOF\n2\nfurg.fs\n3\ndummy.txt\ndummy_in_fs.txt\n0\nEOF")
print("File copied in.")

os.system("python main.py <<EOF\n2\nfurg.fs\n7\n0\nEOF")
print("Listed files.")

os.system("python main.py <<EOF\n2\nfurg.fs\n8\n0\nEOF")
print("DF shown.")

os.system("python main.py <<EOF\n2\nfurg.fs\n4\ndummy_in_fs.txt\nrestored.txt\n0\nEOF")
print("File copied out.")

with open("restored.txt", "r") as f:
    content = f.read()
    if len(content) > 0:
        print("Restored content length:", len(content))
    else:
        print("Restored file is empty!")

os.system("python main.py <<EOF\n2\nfurg.fs\n9\ndummy_in_fs.txt\n0\nEOF")
print("File protected.")

os.system("python main.py <<EOF\n2\nfurg.fs\n6\ndummy_in_fs.txt\n0\nEOF")
print("Tried to remove protected file (should fail).")

os.system("python main.py <<EOF\n2\nfurg.fs\n9\ndummy_in_fs.txt\n6\ndummy_in_fs.txt\n0\nEOF")
print("File unprotected and removed.")

os.system("python main.py <<EOF\n2\nfurg.fs\n7\n0\nEOF")
print("Listed files after removal.")

print("Test complete.")

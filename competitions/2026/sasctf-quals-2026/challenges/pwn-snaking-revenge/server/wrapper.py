import os
import tempfile
from base64 import b64decode
from shutil import rmtree
from subprocess import STDOUT, CalledProcessError, run
from zlib import decompress

print("Welcome! but be careful...")
print("=" * 40)

jar_source = decompress(b64decode(input("JAR source: ").strip().encode()))

try:
    jar_dir = tempfile.mkdtemp(dir="/tmp")
    jar_path = os.path.join(jar_dir, "requester.jar")

    with open(jar_path, "wb") as f:
        f.write(jar_source)

    url_arg = input("--url: ").strip()
    proxy_arg = input("--proxy: ").strip()

    proc = run(
        ["python3", "main.py", "--url", url_arg] + (["--proxy", proxy_arg] if proxy_arg else []),
        stderr=STDOUT, env=os.environ.copy() | {"CLASSPATH": jar_path}, check=True
    )
    print(f"Process exited with code: {proc.returncode}")

except CalledProcessError as e:
    print(f"Process execution failed with return code {e.returncode}")

except Exception as e:
    print(f"Somehing went wrong...")

finally:
    rmtree(jar_dir, ignore_errors=True)

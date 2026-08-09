"""bubblewrap (bwrap) ile izole kod/komut çalıştırma sandbox'ı.

Güvenlik modeli (CLAUDE.md "Güvenlik notları"): sistem kod çalıştırabiliyor VE
uzaktan erişilebilir olacak, bu yüzden en dar yetki ile çalışır — salt-okunur
kök dosya sistemi, ayrı bir çalışma dizini dışında yazma yok, ağ yok (varsayılan).
"""

import os
import subprocess
import tempfile

WORKDIR_BASE = os.path.expanduser("~/jarvis/sandbox-runs")


def run_sandboxed(command: str, timeout: int = 30, allow_network: bool = False) -> dict:
    """Komutu bwrap sandbox'ında çalıştırır. Çalışma dizini dışında hiçbir yere yazamaz."""
    os.makedirs(WORKDIR_BASE, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=WORKDIR_BASE) as workdir:
        bwrap_args = [
            "bwrap",
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf",
            "--symlink", "usr/lib", "/lib",
            "--symlink", "usr/lib64", "/lib64",
            "--symlink", "usr/bin", "/bin",
            "--symlink", "usr/sbin", "/sbin",
            "--bind", workdir, "/work",
            "--chdir", "/work",
            "--proc", "/proc",
            "--dev", "/dev",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--die-with-parent",
            "--new-session",
        ]
        if not allow_network:
            bwrap_args.append("--unshare-net")
        bwrap_args += ["--", "sh", "-c", command]

        try:
            proc = subprocess.run(
                bwrap_args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "stdout": proc.stdout[-8000:],
                "stderr": proc.stderr[-4000:],
                "return_code": proc.returncode,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as e:
            return {
                "stdout": (e.stdout or "")[-8000:],
                "stderr": (e.stderr or "")[-4000:],
                "return_code": None,
                "timed_out": True,
            }

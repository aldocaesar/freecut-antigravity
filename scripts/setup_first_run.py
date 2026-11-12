"""
First-Run Setup & Environment Doctor
====================================
Verifica e instala automaticamente as dependências na primeira vez de uso
(Python packages, FFmpeg via winget no Windows e chave PIXABAY_API_KEY no .env).
"""

import argparse
import glob
import importlib
import os
import platform
import shutil
import subprocess
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_PATH = os.path.join(ROOT_DIR, ".env")
ENV_EXAMPLE_PATH = os.path.join(ROOT_DIR, ".env.example")
REQ_PATH = os.path.join(ROOT_DIR, "requirements.txt")
SETUP_STAMP = os.path.join(ROOT_DIR, ".setup_ok")

REQUIRED_IMPORTS = {
    "PIL": "Pillow",
    "yt_dlp": "yt-dlp",
    "requests": "requests",
    "bs4": "beautifulsoup4",
    "faster_whisper": "faster-whisper",
}


def find_ffmpeg_dir() -> str | None:
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return os.path.dirname(shutil.which("ffmpeg"))
    if platform.system() == "Windows":
        local_app = os.environ.get("LOCALAPPDATA", "")
        patterns = [
            os.path.join(local_app, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "**", "bin", "ffmpeg.exe"),
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
        ]
        for pat in patterns:
            matches = glob.glob(pat, recursive=True)
            if matches:
                return os.path.dirname(matches[0])
    return None


def read_env_dict() -> dict[str, str]:
    data: dict[str, str] = {}
    if not os.path.exists(ENV_PATH):
        return data
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def set_env_key(key: str, value: str) -> None:
    if not os.path.exists(ENV_PATH):
        if os.path.exists(ENV_EXAMPLE_PATH):
            shutil.copy2(ENV_EXAMPLE_PATH, ENV_PATH)
        else:
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.write(f'{key}="{value}"\n')
            return

    with open(ENV_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    updated = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f'{key}="{value}"\n')
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f'{key}="{value}"\n')

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def run_install() -> None:
    print("[Setup] 1/3 Garantindo arquivo .env...")
    if not os.path.exists(ENV_PATH) and os.path.exists(ENV_EXAMPLE_PATH):
        shutil.copy2(ENV_EXAMPLE_PATH, ENV_PATH)

    print("[Setup] 2/3 Instalando pacotes Python (requirements.txt)...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", REQ_PATH], check=True)

    print("[Setup] 3/3 Verificando FFmpeg...")
    if not find_ffmpeg_dir() and platform.system() == "Windows" and shutil.which("winget"):
        print("[Setup] FFmpeg ausente. Instalando via winget (Gyan.FFmpeg)...")
        subprocess.run(
            [
                "winget", "install", "-e", "--id", "Gyan.FFmpeg",
                "--accept-package-agreements", "--accept-source-agreements",
            ],
            check=False,
        )


def check_all() -> int:
    issues: list[str] = []

    ffmpeg_dir = find_ffmpeg_dir()
    if ffmpeg_dir:
        print(f"[OK] FFmpeg encontrado em: {ffmpeg_dir}")
    else:
        issues.append("FFmpeg/ffprobe nao encontrado. Rode: python scripts/setup_first_run.py --install")

    missing_pkgs = []
    for mod, pkg in REQUIRED_IMPORTS.items():
        try:
            importlib.import_module(mod)
        except ImportError:
            missing_pkgs.append(pkg)
    if missing_pkgs:
        issues.append(f"Pacotes Python faltando ({', '.join(missing_pkgs)}). Rode: python scripts/setup_first_run.py --install")
    else:
        print("[OK] Todos os pacotes Python instalados (Pillow, yt-dlp, requests, bs4, faster-whisper).")

    sfx_files = glob.glob(os.path.join(ROOT_DIR, "assets", "sfx", "*.mp3"))
    if len(sfx_files) >= 5:
        print(f"[OK] Assets locais de SFX prontos ({len(sfx_files)} arquivos).")
    else:
        issues.append("Pasta assets/sfx incompleta.")

    env_vars = read_env_dict()
    pixabay_key = env_vars.get("PIXABAY_API_KEY", "").strip()
    if pixabay_key:
        masked = pixabay_key[:4] + "..." + pixabay_key[-3:] if len(pixabay_key) > 7 else "***"
        print(f"[OK] PIXABAY_API_KEY configurada ({masked}).")
    else:
        issues.append("PIXABAY_API_KEY vazia no .env. Peca a chave ao usuario e rode: python scripts/setup_first_run.py --set-pixabay-key SUA_CHAVE")

    npx_cmd = "npx.cmd" if platform.system() == "Windows" else "npx"
    if shutil.which(npx_cmd):
        print("[OK] Node.js / npx disponivel (opcional para info_card).")
    else:
        print("[INFO] Node.js / npx ausente (opcional; legendas nativas do FreeCut funcionam normalmente sem ele).")

    if issues:
        if os.path.exists(SETUP_STAMP):
            os.remove(SETUP_STAMP)
        print("\n[PENDENTE] Resolva os itens abaixo antes de compilar:")
        for it in issues:
            print(f"  - {it}")
        return 1

    with open(SETUP_STAMP, "w", encoding="utf-8") as f:
        f.write("ok\n")
    print("\n[PRONTO] Ambiente 100% configurado e pronto para editar videos!")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Setup e verificacao de primeiro uso")
    parser.add_argument("--check", action="store_true", help="Apenas verifica o ambiente")
    parser.add_argument("--install", action="store_true", help="Instala dependencias ausentes")
    parser.add_argument("--set-pixabay-key", type=str, default="", help="Salva PIXABAY_API_KEY no .env")
    args = parser.parse_args()

    if args.set_pixabay_key:
        set_env_key("PIXABAY_API_KEY", args.set_pixabay_key.strip())
        print("[OK] PIXABAY_API_KEY salva em .env")

    if args.install:
        run_install()

    sys.exit(check_all())


if __name__ == "__main__":
    main()

"""
Local Audio Transcriber & Scene Slicer
======================================
Recebe qualquer arquivo de áudio (.mp3, .wav, .m4a, .ogg, .flac, .mp4),
prepara a pasta do projeto, transcreve localmente com faster-whisper
(word-level timestamps, zero API paga) e já gera slices.json + slices.txt
enxuto para a IA ler sem jamais estourar contexto.
"""

import argparse
import glob
import json
import os
import platform
import shutil
import subprocess
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from auto_storyboard_slicer import auto_slice_words


def ensure_ffmpeg_on_path() -> None:
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    if platform.system() == "Windows":
        local_app = os.environ.get("LOCALAPPDATA", "")
        patterns = [
            os.path.join(local_app, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "**", "bin", "ffmpeg.exe"),
            r"C:\ffmpeg\bin\ffmpeg.exe",
        ]
        for pat in patterns:
            matches = glob.glob(pat, recursive=True)
            if matches:
                bin_dir = os.path.dirname(matches[0])
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
                return


def get_audio_duration_ms(audio_path: str) -> int:
    ensure_ffmpeg_on_path()
    try:
        res = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", audio_path,
            ],
            capture_output=True, text=True, check=True,
        )
        return int(round(float(res.stdout.strip()) * 1000.0))
    except Exception:
        return 0


def prepare_project_audio(src_audio: str, project_dir: str) -> str:
    ensure_ffmpeg_on_path()
    ext = os.path.splitext(src_audio)[1].lower()
    if ext in (".mp3", ".wav"):
        dest = os.path.join(project_dir, f"audio{ext}")
        if os.path.abspath(src_audio) != os.path.abspath(dest):
            shutil.copy2(src_audio, dest)
        return dest

    dest = os.path.join(project_dir, "audio.mp3")
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-i", src_audio, "-vn", "-acodec", "libmp3lame", "-q:a", "2", dest],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    return dest


def transcribe_with_faster_whisper(audio_path: str, model_size: str = "small", lang: str = "auto") -> list[dict]:
    from faster_whisper import WhisperModel

    print(f"[Transcribe] Carregando faster-whisper ('{model_size}', local CPU/int8)...")
    model = WhisperModel(model_size, device="auto", compute_type="int8")
    language = None if lang in ("", "auto") else lang

    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 350},
    )
    print(f"[Transcribe] Idioma detectado: {info.language} (confianca {info.language_probability:.2f})")

    words: list[dict] = []
    for seg in segments:
        if not seg.words:
            continue
        for w in seg.words:
            token = (w.word or "").strip()
            if not token:
                continue
            start_ms = max(0, int(round(w.start * 1000.0)))
            end_ms = max(start_ms + 40, int(round(w.end * 1000.0)))
            words.append({"word": token, "start_ms": start_ms, "end_ms": end_ms})

    return words


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcreve audio localmente e gera fatias de storyboard")
    parser.add_argument("audio", help="Caminho do arquivo de audio (.mp3, .wav, .m4a, etc.)")
    parser.add_argument("--project", required=True, help="Pasta de destino do projeto (ex: projects/meu_video)")
    parser.add_argument("--words", default="", help="Arquivo words.json existente opcional (pula transcricao)")
    parser.add_argument("--model", default="small", help="Modelo faster-whisper (tiny, base, small, medium)")
    parser.add_argument("--lang", default="auto", help="Codigo do idioma (pt, en, es, ou auto)")
    args = parser.parse_args()

    src_audio = os.path.abspath(args.audio)
    if not os.path.isfile(src_audio):
        print(f"[ERRO] Arquivo de audio nao encontrado: {src_audio}")
        sys.exit(1)

    project_dir = os.path.abspath(args.project)
    os.makedirs(project_dir, exist_ok=True)

    dest_audio = prepare_project_audio(src_audio, project_dir)
    audio_dur_ms = get_audio_duration_ms(dest_audio)

    words_path = os.path.join(project_dir, "words.json")
    if args.words and os.path.isfile(args.words):
        shutil.copy2(args.words, words_path)
        print(f"[Transcribe] Usando words.json fornecido: {args.words}")

    if os.path.isfile(words_path) and os.path.getsize(words_path) > 10:
        with open(words_path, "r", encoding="utf-8") as f:
            words = json.load(f)
        print(f"[Transcribe] Carregado words.json existente ({len(words)} palavras).")
    else:
        words = transcribe_with_faster_whisper(dest_audio, model_size=args.model, lang=args.lang)
        if not words:
            print("[ERRO] Nenhuma fala detectada no audio.")
            sys.exit(1)
        if audio_dur_ms > 0 and words[-1]["end_ms"] < audio_dur_ms:
            words[-1]["end_ms"] = audio_dur_ms
        with open(words_path, "w", encoding="utf-8") as f:
            json.dump(words, f, indent=2, ensure_ascii=False)

    slices = auto_slice_words(words)
    if slices:
        slices[0]["start_ms"] = 0
        if audio_dur_ms > slices[-1]["end_ms"]:
            # Estende suavemente a ultima cena se sobrar pequena cauda <= 2.5s
            if audio_dur_ms - slices[-1]["end_ms"] <= 2500:
                slices[-1]["end_ms"] = audio_dur_ms

    structured_slices = []
    txt_lines = [
        f"# PROJETO: {os.path.basename(project_dir)} | DURACAO_AUDIO_MS: {audio_dur_ms or words[-1]['end_ms']} | TOTAL_CENAS: {len(slices)}",
        "# FORMATO: ID | DURACAO_S | NARRACAO",
        "-" * 80,
    ]
    for idx, sl in enumerate(slices, 1):
        sid = f"S{idx:02d}"
        dur_s = round((sl["end_ms"] - sl["start_ms"]) / 1000.0, 2)
        entry = {
            "id": sid,
            "start_ms": sl["start_ms"],
            "end_ms": sl["end_ms"],
            "duration_s": dur_s,
            "narration": sl["narration"],
        }
        structured_slices.append(entry)
        txt_lines.append(f"{sid} | {dur_s:.1f}s | {sl['narration']}")

    slices_json_path = os.path.join(project_dir, "slices.json")
    slices_txt_path = os.path.join(project_dir, "slices.txt")
    with open(slices_json_path, "w", encoding="utf-8") as f:
        json.dump(structured_slices, f, indent=2, ensure_ascii=False)
    with open(slices_txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines) + "\n")

    print(f"[OK] Audio pronto: {dest_audio} ({(audio_dur_ms or words[-1]['end_ms'])/1000:.1f}s)")
    print(f"[OK] Palavras: {len(words)} | Cenas fatiadas: {len(structured_slices)}")
    print(f"[OK] Leia APENAS o resumo leve: {slices_txt_path}")


if __name__ == "__main__":
    main()

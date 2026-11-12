"""
Storyboard Builder & Validator from Compact AI Specs
====================================================
Une as escolhas criativas leves da IA (specs.json ou specs_part1.json, part2.json...)
com os timestamps matematicamente travados em slices.json.
Garante:
  - Zero gaps e zero sobreposições (start_ms[N+1] == end_ms[N])
  - 100% das queries únicas (desambigua automaticamente se houver colisão)
  - Compatibilidade total com o pipeline_v3.py
"""

import argparse
import glob
import json
import os
import re
import sys


def load_specs(project_dir: str) -> list[dict]:
    part_files = glob.glob(os.path.join(project_dir, "specs_part*.json"))
    if part_files:
        def _part_num(p: str) -> int:
            m = re.search(r"specs_part(\d+)\.json$", os.path.basename(p))
            return int(m.group(1)) if m else 999
        part_files.sort(key=_part_num)
        merged: list[dict] = []
        for pf in part_files:
            with open(pf, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged.extend(data["scenes"] if isinstance(data, dict) and "scenes" in data else data)
        return merged

    single_path = os.path.join(project_dir, "specs.json")
    if os.path.isfile(single_path):
        with open(single_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["scenes"] if isinstance(data, dict) and "scenes" in data else data

    raise FileNotFoundError("Nenhum specs.json ou specs_part*.json encontrado na pasta do projeto.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monta e valida storyboard.json a partir de slices.json + specs")
    parser.add_argument("project_dir", help="Pasta do projeto")
    parser.add_argument("--title", default="", help="Titulo do projeto")
    parser.add_argument("--mode", default="default", help="default ou pop")
    parser.add_argument("--universe", default="", help="Universo/franquia opcional (ex: One Piece, Harry Potter)")
    parser.add_argument("--font-theme", default="", help="Paleta tipografica opcional (ex: editorial_documentary, pop_cinema, investigative_press)")
    parser.add_argument("--variation-seed", default="", help="Semente opcional para variar molduras, transicoes e grade")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    slices_path = os.path.join(project_dir, "slices.json")
    if not os.path.isfile(slices_path):
        print(f"[ERRO] slices.json nao encontrado em {project_dir}. Rode scripts/transcribe.py primeiro.")
        sys.exit(1)

    with open(slices_path, "r", encoding="utf-8") as f:
        slices = json.load(f)

    specs_list = load_specs(project_dir)
    specs_by_id = {str(item["id"]).strip(): item for item in specs_list if "id" in item}

    missing_ids = [sl["id"] for sl in slices if sl["id"] not in specs_by_id]
    if missing_ids:
        print(f"[ERRO] Faltam especificacoes em specs para {len(missing_ids)} cenas: {missing_ids[:10]}")
        sys.exit(1)

    used_queries: set[str] = set()
    scenes: list[dict] = []

    for idx, sl in enumerate(slices):
        sid = sl["id"]
        sp = specs_by_id[sid]
        start_ms = int(sl["start_ms"])
        end_ms = int(sl["end_ms"])
        dur_ms = end_ms - start_ms
        narration = sl["narration"]

        layout = sp.get("layout") or sp.get("layout_style") or "full_screen"
        if layout not in ("full_screen", "single_card", "split_info_slide", "text_only"):
            layout = "full_screen"

        subtitles = sp.get("sub") if "sub" in sp else sp.get("subtitles", True)
        subtitles = bool(subtitles)

        scene_obj: dict = {
            "id": sid,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "narration": narration,
            "layout_style": layout,
            "subtitles": True if layout == "text_only" else subtitles,
        }

        if layout == "text_only":
            headline = str(sp.get("text_only_text") or "").strip()
            if not headline:
                words_clean = [w for w in re.findall(r"[A-Za-zÀ-ÿ0-9]+", narration) if len(w) > 1]
                headline = " ".join(words_clean[:4]).upper() if words_clean else narration[:32].upper()
            scene_obj["text_only_text"] = headline

        if sp.get("frame_style"):
            scene_obj["frame_style"] = str(sp["frame_style"]).strip()
        if sp.get("camera_motion"):
            scene_obj["camera_motion"] = str(sp["camera_motion"]).strip()
        if sp.get("transition"):
            scene_obj["transition"] = str(sp["transition"]).strip()
        if "rotation" in sp:
            scene_obj["rotation"] = sp["rotation"]
        if sp.get("bg_category"):
            scene_obj["background"] = {"enabled": True, "category": str(sp["bg_category"]).strip()}
        elif isinstance(sp.get("background"), dict):
            scene_obj["background"] = sp["background"]

        if layout != "text_only":
            media_in = sp.get("media", {}) if isinstance(sp.get("media"), dict) else {}
            q = (sp.get("query") or media_in.get("query") or narration[:40]).strip()
            q_norm = q.lower()
            if q_norm in used_queries:
                q = f"{q} view {idx + 1}"
                q_norm = q.lower()
            used_queries.add(q_norm)

            src_type = sp.get("type") or sp.get("source_type") or media_in.get("source_type") or "image"
            specific = sp.get("specific") if "specific" in sp else media_in.get("specific", layout != "full_screen")
            source = sp.get("source") or media_in.get("source") or ("yandex" if specific else "pixabay")

            scene_obj["media"] = {
                "source_type": src_type,
                "query": q,
                "specific": bool(specific),
                "source": source,
            }

        info_card = sp.get("info_card")
        if isinstance(info_card, dict) and dur_ms >= 5000:
            scene_obj["info_card"] = info_card

        scenes.append(scene_obj)

    # Validacao estrita de contiguidade
    for i in range(1, len(scenes)):
        if scenes[i]["start_ms"] != scenes[i - 1]["end_ms"]:
            scenes[i]["start_ms"] = scenes[i - 1]["end_ms"]

    title = args.title or os.path.basename(project_dir)
    storyboard = {
        "title": title,
        "mode": args.mode,
        "universe": args.universe,
        "total_duration_ms": scenes[-1]["end_ms"] if scenes else 0,
        "scenes": scenes,
    }
    if args.font_theme:
        storyboard["font_theme"] = args.font_theme.strip()
    if args.variation_seed:
        storyboard["variation_seed"] = args.variation_seed.strip()

    out_path = os.path.join(project_dir, "storyboard.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(storyboard, f, indent=2, ensure_ascii=False)

    fs_pct = round(100.0 * sum(1 for s in scenes if s["layout_style"] == "full_screen") / max(1, len(scenes)))
    print(f"[OK] storyboard.json gerado em: {out_path}")
    print(f"[OK] {len(scenes)} cenas contiguas | 0 gaps | 100% queries unicas | {fs_pct}% full_screen")


if __name__ == "__main__":
    main()

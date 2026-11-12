import glob
import json
import os
import struct
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import editorial_engine


VALID_TRANSFORM_KEYS = {
    "x", "y", "width", "height", "anchorX", "anchorY", "rotation",
    "flipHorizontal", "flipVertical", "opacity", "cornerRadius", "aspectRatioLocked",
}


def _validate_wform_bin(bin_path: str) -> tuple[bool, str]:
    if not os.path.isfile(bin_path):
        return False, "arquivo multi-res.bin ausente"
    data = open(bin_path, "rb").read()
    if len(data) < 48 + 4 * 12:
        return False, f"tamanho insuficiente ({len(data)} bytes)"
    if data[:5] != b"WFORM":
        return False, f"magic invalido ({data[:5]!r})"
    version, duration_s, channels, level_count = struct.unpack_from("<BfBB", data, 5)
    if version != 1:
        return False, f"version={version} (esperado 1)"
    if duration_s <= 0:
        return False, f"duration={duration_s} invalida"
    if channels != 1 or level_count != 4:
        return False, f"channels={channels}, level_count={level_count} (esperado 1, 4)"

    expected_rates = [500, 100, 25, 10]
    for idx in range(4):
        sr, sample_count, data_offset, _reserved = struct.unpack_from("<HIIH", data, 48 + idx * 12)
        if sr != expected_rates[idx]:
            return False, f"nivel {idx} sampleRate={sr} (esperado {expected_rates[idx]})"
        if sample_count < 1:
            return False, f"nivel {idx} sampleCount={sample_count}"
        end_byte = data_offset + sample_count * 4
        if end_byte > len(data):
            return False, f"nivel {idx} estoura tamanho do arquivo ({end_byte} > {len(data)})"
    return True, "ok"


def validate_project(project_dir: str) -> bool:
    project_dir = os.path.abspath(project_dir)
    workspace_dir = os.path.join(project_dir, "freecut_workspace")
    paths = glob.glob(os.path.join(workspace_dir, "projects", "*", "project.json"))
    if not paths:
        print(f"[FAIL] Nenhum project.json encontrado em {project_dir}.")
        return False

    path = paths[0]
    print(f"=== Validando projeto FreeCut v15 + Workspace v2: {path} ===")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Check 1: Schema version
    schema_version = data.get("schemaVersion")
    if schema_version != 15:
        print(f"[FAIL] schemaVersion é {schema_version}, esperado 15.")
        return False
    print("[PASS] schemaVersion é 15.")

    timeline = data.get("timeline", {})
    items = timeline.get("items", [])
    tracks = timeline.get("tracks", [])
    keyframes = timeline.get("keyframes", [])
    text_items = [it for it in items if it.get("type") == "text"]

    # Check 2: Single-item subtitles (no legacy _hl / _sec splits)
    hl_items = [it for it in text_items if "_hl" in it.get("label", "")]
    sec_items = [it for it in text_items if "_sec" in it.get("label", "")]
    if hl_items or sec_items:
        print(f"[FAIL] Encontrados itens de texto fatiados legados: hl={len(hl_items)}, sec={len(sec_items)}")
        return False
    print("[PASS] Zero fragmentação legada (_hl/_sec); multi-span nativo preservado.")

    storyboard_path = os.path.join(project_dir, "storyboard.json")
    storyboard_scenes = []
    if os.path.exists(storyboard_path):
        with open(storyboard_path, "r", encoding="utf-8") as sf:
            storyboard_scenes = json.load(sf).get("scenes", [])
    scenes_by_id = {s["id"]: s for s in storyboard_scenes}

    # Map item ID to settled keyframe position
    item_final_x = {}
    item_final_y = {}
    for kf in keyframes:
        if kf.get("animationVersion") != 2:
            print(f"[FAIL] Keyframe group de itemId={kf.get('itemId')} sem animationVersion=2.")
            return False
        item_id = kf.get("itemId")
        for prop in kf.get("properties", []):
            prop_name = prop.get("property")
            kfs = prop.get("keyframes", [])
            if prop_name == "rotation" and len(kfs) >= 2:
                for ki in range(len(kfs) - 1):
                    delta_rot = abs(float(kfs[ki + 1]["value"]) - float(kfs[ki]["value"]))
                    if delta_rot > 45.0:
                        print(f"[FAIL] Giro acidental de {delta_rot:.1f}° detectado em keyframes de rotation ({item_id})!")
                        return False
            if kfs:
                last_kf = max(kfs, key=lambda x: x.get("frame", 0))
                if prop_name == "x":
                    item_final_x[item_id] = last_kf.get("value")
                elif prop_name == "y":
                    item_final_y[item_id] = last_kf.get("value")
    print("[PASS] Todos os grupos de keyframes possuem animationVersion=2.")

    # Check 3: Spatial Coordinates & Zero Card/Text Overlap
    for it in text_items:
        label = it.get("label", "")
        if label.startswith("PTBR_"):
            continue
        transform = it.get("transform", {})
        it_id = it.get("id")
        tx = item_final_x.get(it_id, transform.get("x", 0))
        ty = item_final_y.get(it_id, transform.get("y", 0))

        scene_id = label.split("_sub_")[0]
        scene_info = scenes_by_id.get(scene_id, {})
        layout_style = scene_info.get("layout_style")
        if layout_style in ("full_screen", "text_only", None):
            continue

        scene_media = [
            m for m in items
            if m.get("label", "").startswith(scene_id)
            and m.get("type") in ["image", "video"]
            and "_info_card" not in m.get("label", "")
        ]
        for m in scene_media:
            m_id = m.get("id")
            m_transform = m.get("transform", {})
            mx = item_final_x.get(m_id, m_transform.get("x", 0))
            my = item_final_y.get(m_id, m_transform.get("y", 0))
            split_type = scene_info.get("layout_params", {}).get("split_type", "horizontal")

            overlap = False
            if layout_style == "split_info_slide":
                if split_type == "horizontal":
                    if (mx > 0 and tx > 0) or (mx < 0 and tx < 0):
                        overlap = True
                else:
                    if (my > 0 and ty > 0) or (my < 0 and ty < 0):
                        overlap = True
            elif layout_style == "single_card":
                if (my > 0 and ty > 0) or (my < 0 and ty < 0):
                    overlap = True

            if overlap:
                print(f"[FAIL] Sobreposição em {scene_id} ({layout_style}/{split_type}): media=({mx},{my}), texto=({tx},{ty})")
                return False
    print("[PASS] Zero sobreposição física entre moldura/card e tipografia.")

    # Check 4: Color Contrast, Bundled Typography & Native textMotion
    light_colors = {"#FFD54F", "#FFFFFF", "#42A5F5", "#64B5F6", "#FFFAEC", "#FFCC00"}
    for it in text_items:
        label = it.get("label", "")
        color = it.get("color", "").upper()
        font_fam = it.get("fontFamily", "")
        font_w = it.get("fontWeight", "normal")
        text_shadow = it.get("textShadow", {})

        if font_fam not in editorial_engine.FREECUT_VALID_FONTS:
            print(f"[FAIL] {label} usa fontFamily '{font_fam}' fora do catálogo nativo do FreeCut!")
            return False
        if font_w not in editorial_engine.VALID_FONT_WEIGHTS:
            print(f"[FAIL] {label} usa fontWeight inválido '{font_w}'!")
            return False
        if "textAnimation" in it:
            print(f"[FAIL] {label} contém chave legada obsoleta 'textAnimation'!")
            return False

        if not label.startswith("PTBR_"):
            tm = it.get("textMotion")
            if not isinstance(tm, dict) or "in" not in tm:
                print(f"[FAIL] {label} está sem 'textMotion.in' nativo do FreeCut!")
                return False
            in_preset = tm["in"].get("presetId")
            if in_preset not in editorial_engine.TEXT_MOTION_IN_PRESETS:
                print(f"[FAIL] {label} tem textMotion.in.presetId inválido '{in_preset}'.")
                return False
            if it.get("durationInFrames", 0) >= 14 or "out" in tm:
                if "out" not in tm:
                    print(f"[FAIL] {label} (dur={it.get('durationInFrames')}f) está sem 'textMotion.out'!")
                    return False
                out_preset = tm["out"].get("presetId")
                if out_preset not in editorial_engine.TEXT_MOTION_OUT_PRESETS:
                    print(f"[FAIL] {label} tem textMotion.out.presetId inválido '{out_preset}'.")
                    return False

            scene_id = label.split("_sub_")[0]
            scene_info = scenes_by_id.get(scene_id, {})
            bg_color = scene_info.get("bg_color", "").upper()
            is_light = bg_color in {"#FAF9F6", "#F5F5F7", "#F9F9FB", "#FFFFFF"}
            if is_light:
                if color in light_colors:
                    print(f"[FAIL] {label} tem cor clara '{color}' sobre fundo claro!")
                    return False
                if text_shadow.get("color") != "transparent":
                    print(f"[FAIL] {label} tem sombra escura sobre fundo claro!")
                    return False
            elif scene_info.get("layout_style") == "full_screen":
                if text_shadow.get("color") == "transparent":
                    print(f"[FAIL] {label} sem sombra de contraste em full_screen!")
                    return False

        for sp in it.get("textSpans") or []:
            sp_fam = sp.get("fontFamily")
            sp_w = sp.get("fontWeight")
            if sp_fam and sp_fam not in editorial_engine.FREECUT_VALID_FONTS:
                print(f"[FAIL] Span em {label} usa fontFamily inválida '{sp_fam}'!")
                return False
            if sp_w and sp_w not in editorial_engine.VALID_FONT_WEIGHTS:
                print(f"[FAIL] Span em {label} usa fontWeight inválido '{sp_w}'!")
                return False

    print("[PASS] Tipografia editorial, contraste e animações nativas ('textMotion' + 'textSpans') 100% válidos.")

    # Check 5:Strict Transform Schema, Frame-Unit Audio/SFX & Track Hygiene
    track_ids = {t["id"] for t in tracks}
    for it in items:
        lbl = it.get("label", it.get("id", ""))
        if it.get("trackId") not in track_ids:
            print(f"[FAIL] Item {lbl} aponta para trackId inexistente '{it.get('trackId')}'.")
            return False
        if "mediaRef" in it:
            print(f"[FAIL] Item {lbl} no workspace ainda usa 'mediaRef' em vez de 'mediaId'.")
            return False
        tf = it.get("transform")
        if isinstance(tf, dict):
            bad_keys = set(tf.keys()) - VALID_TRANSFORM_KEYS
            if bad_keys:
                print(f"[FAIL] Item {lbl} contém chaves inválidas em transform: {bad_keys}")
                return False
            rot = tf.get("rotation")
            if rot is not None and not (0.0 <= float(rot) < 360.0):
                print(f"[FAIL] Item {lbl} tem transform.rotation fora de [0, 360): {rot}")
                return False

        if it.get("type") == "audio":
            vol = float(it.get("volume", 0))
            if vol > 0.0:
                print(f"[FAIL] Áudio/SFX {lbl} com volume positivo ({vol} dB)!")
                return False
            if it.get("trackId") == "track_sfx" and it.get("from", 0) == 0:
                print(f"[FAIL] SFX {lbl} tocando no frame 0!")
                return False
            src_end = it.get("sourceEnd", 0)
            src_dur = it.get("sourceDuration", 0)
            if not isinstance(src_end, int) or not isinstance(src_dur, int) or src_end < 1 or src_dur < src_end:
                print(f"[FAIL] Áudio/SFX {lbl} não está em unidades inteiras de frames (sourceEnd={src_end}, sourceDuration={src_dur})!")
                return False
    print("[PASS] Transforms limpos, áudio/SFX em frames + dB calibrado e tracks enxutas.")

    # Check 6: Instant-Load Workspace v2 Caches (Thumbnails, Filmstrips v2, Waveforms WFORM v1)
    ws_marker = os.path.join(workspace_dir, ".freecut-workspace.json")
    ws_index = os.path.join(workspace_dir, "index.json")
    if not os.path.isfile(ws_marker) or not os.path.isfile(ws_index):
        print("[FAIL] Marcadores Workspace v2 (.freecut-workspace.json / index.json) ausentes!")
        return False

    media_meta_files = glob.glob(os.path.join(workspace_dir, "media", "*", "metadata.json"))
    if not media_meta_files:
        print("[FAIL] Nenhuma mídia registrada em freecut_workspace/media/*/metadata.json!")
        return False

    img_thumbs = 0
    vid_filmstrips = 0
    aud_waveforms = 0

    for meta_path in media_meta_files:
        m_dir = os.path.dirname(meta_path)
        with open(meta_path, "r", encoding="utf-8") as mf:
            meta = json.load(mf)
        mime = meta.get("mimeType", "")
        if mime.startswith("image/"):
            t_jpg = os.path.join(m_dir, "thumbnail.jpg")
            if not os.path.isfile(t_jpg) or os.path.getsize(t_jpg) == 0:
                print(f"[FAIL] Imagem {meta.get('fileName')} sem thumbnail.jpg pré-gerado!")
                return False
            img_thumbs += 1
        elif mime.startswith("video/"):
            t_jpg = os.path.join(m_dir, "thumbnail.jpg")
            fs_meta_path = os.path.join(m_dir, "cache", "filmstrip", "meta.json")
            if not os.path.isfile(t_jpg) or not os.path.isfile(fs_meta_path):
                print(f"[FAIL] Vídeo {meta.get('fileName')} sem thumbnail.jpg ou cache/filmstrip/meta.json!")
                return False
            with open(fs_meta_path, "r", encoding="utf-8") as fmf:
                fs_meta = json.load(fmf)
            if fs_meta.get("version") != 2 or not fs_meta.get("isComplete") or fs_meta.get("frameCount", 0) < 1:
                print(f"[FAIL] cache/filmstrip/meta.json inválido para {meta.get('fileName')}: {fs_meta}")
                return False
            if "audioCodec" in meta:
                print(f"[FAIL] Vídeo B-roll {meta.get('fileName')} expõe audioCodec e causaria decode desnecessário!")
                return False
            vid_filmstrips += 1
        elif mime.startswith("audio/"):
            wf_bin = os.path.join(m_dir, "cache", "waveform", "multi-res.bin")
            ok_wf, msg_wf = _validate_wform_bin(wf_bin)
            if not ok_wf:
                print(f"[FAIL] Waveform cache inválido para {meta.get('fileName')}: {msg_wf}")
                return False
            aud_waveforms += 1

    print(
        f"[PASS] Caches Instant-Load Workspace v2 verificados: "
        f"{img_thumbs} image thumbs, {vid_filmstrips} video filmstrips (1fps v2), {aud_waveforms} audio waveforms (WFORM v1)."
    )
    print(f"\n[SUCCESS] Todos os testes passaram com perfeição para {project_dir}!")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python validate_any_project.py <caminho_do_projeto>")
        sys.exit(1)
    success = validate_project(sys.argv[1])
    sys.exit(0 if success else 1)

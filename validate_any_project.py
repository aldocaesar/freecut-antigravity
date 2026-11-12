import glob
import json
import sys
import os

def validate_project(project_dir):
    project_dir = os.path.abspath(project_dir)
    paths = glob.glob(os.path.join(project_dir, "freecut_workspace/projects/*/project.json"))
    if not paths:
        print(f"[FAIL] Nenhum project.json encontrado em {project_dir}.")
        return False
        
    path = paths[0]
    print(f"=== Validando projeto: {path} ===")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # Check 1: Schema version
    schema_version = data.get("schemaVersion")
    if schema_version != 15:
        print(f"[FAIL] schemaVersion é {schema_version}, esperado 15.")
        return False
    else:
        print("[PASS] schemaVersion é 15.")
        
    items = data["timeline"]["items"]
    text_items = [it for it in items if it.get("type") == "text"]
    
    # Check 2: Single-line text (no splits)
    hl_items = [it for it in text_items if "_hl" in it.get("label", "")]
    sec_items = [it for it in text_items if "_sec" in it.get("label", "")]
    if hl_items or sec_items:
        print(f"[FAIL] Encontrados itens de texto cinético fatiados: hl={len(hl_items)}, sec={len(sec_items)}")
        return False
    else:
        print("[PASS] Não há fatiamento cinético complexo (todas as legendas em bloco único).")
        
    # Load storyboard.json
    storyboard_path = os.path.join(project_dir, "storyboard.json")
    storyboard_scenes = []
    if os.path.exists(storyboard_path):
        with open(storyboard_path, "r", encoding="utf-8") as sf:
            storyboard_scenes = json.load(sf).get("scenes", [])
            
    scenes_by_id = {s["id"]: s for s in storyboard_scenes}
        
    # Map item ID to its final keyframe values (to get final position on screen)
    item_final_x = {}
    item_final_y = {}
    keyframes = data.get("timeline", {}).get("keyframes", [])
    for kf in keyframes:
        item_id = kf.get("itemId")
        properties = kf.get("properties", [])
        for prop in properties:
            prop_name = prop.get("property")
            kfs = prop.get("keyframes", [])
            if kfs:
                # Find the keyframe with the largest frame number
                last_kf = max(kfs, key=lambda x: x.get("frame", 0))
                last_val = last_kf.get("value")
                if prop_name == "x":
                    item_final_x[item_id] = last_val
                elif prop_name == "y":
                    item_final_y[item_id] = last_val

    # Check 3: Coordinates and Overlaps
    for it in text_items:
        label = it.get("label", "")
        transform = it.get("transform", {})
        
        # Use final keyframe position if available, otherwise fallback to transform
        it_id = it.get("id")
        tx = item_final_x.get(it_id, transform.get("x", 0))
        ty = item_final_y.get(it_id, transform.get("y", 0))
        
        # Check alignment overlaps against card items of the same scene
        scene_id = label.split("_sub_")[0] # e.g. "S02" from "S02_sub_0"
        
        # Skip overlap checks for full_screen scenes
        scene_info = scenes_by_id.get(scene_id, {})
        if scene_info.get("layout_style") == "full_screen":
            continue
            
        # Find card/media items of the same scene, ignoring info cards
        scene_media = [
            m for m in items 
            if m.get("label", "").startswith(scene_id) and m.get("type") in ["image", "video"]
            and "_info_card" not in m.get("label", "")
        ]
        
        for m in scene_media:
            m_id = m.get("id")
            m_transform = m.get("transform", {})
            mx = item_final_x.get(m_id, m_transform.get("x", 0))
            my = item_final_y.get(m_id, m_transform.get("y", 0))
            
            # For split_info_slide layout, card and text MUST be on opposite sides (x for horizontal, y for vertical)
            # For single_card layout, both card and text are centered on x so we check y separation
            layout_style = scene_info.get("layout_style")
            layout_params = scene_info.get("layout_params", {})
            split_type = layout_params.get("split_type", "horizontal")
            
            overlap = False
            if layout_style == "split_info_slide":
                if split_type == "horizontal":
                    if (mx > 0 and tx > 0) or (mx < 0 and tx < 0):
                        overlap = True
                else: # vertical split
                    if (my > 0 and ty > 0) or (my < 0 and ty < 0):
                        overlap = True
            elif layout_style == "single_card":
                # For single_card, they are vertically separated, so check y overlap
                if (my > 0 and ty > 0) or (my < 0 and ty < 0):
                    overlap = True
                    
            if overlap:
                print(f"[FAIL] Alinhamento inadequado para {scene_id} ({layout_style}/{split_type}): media em ({mx},{my}) e texto em ({tx},{ty}) do mesmo lado!")
                return False
                
    print("[PASS] Sem sobreposição física ou alinhamento irregular entre texto e card.")
    
    # Check 4: Color Contrast (No yellow on white/light grey)
    light_colors = ["#FFD54F", "#FFFFFF", "#42A5F5", "#64B5F6", "#FFFAEC"]
    for it in text_items:
        label = it.get("label", "")
        color = it.get("color", "").upper()
        text = it.get("text", "")
        text_shadow = it.get("textShadow", {})
        
        scene_id = label.split("_sub_")[0]
        scene_info = scenes_by_id.get(scene_id, {})
        bg_color = scene_info.get("bg_color", "").upper()
        
        # Detect if background is light
        is_light = bg_color in ["#FAF9F6", "#F5F5F7", "#F9F9FB", "#FFFFFF"]
        
        if is_light:
            if color in light_colors or color == "#FFCC00":
                print(f"[FAIL] Texto de {label} ('{text}') tem cor clara '{color}' em fundo claro!")
                return False
            # Shadow should be transparent on light backgrounds
            if text_shadow.get("color") != "transparent":
                print(f"[FAIL] Texto de {label} tem sombra em fundo claro!")
                return False
        else:
            # Full screen should have shadow contrast
            if scene_info.get("layout_style") == "full_screen":
                if text_shadow.get("color") == "transparent":
                    print(f"[FAIL] Texto de {label} não tem sombra em vídeo de tela cheia!")
                    return False
                
    print("[PASS] Regras de cores e contraste seguidas perfeitamente (sem texto claro em fundo claro, sem sombras desnecessárias).")
    
    # Check 5: Text Animation native settings
    valid_entries = ["typewriter", "fade", "slide_up", "slide_down", "slide_left", "slide_right", "cascade", "pop", "blur"]
    valid_exits = ["fade", "slide_up", "slide_down", "slide_left", "slide_right", "sink", "pop", "blur"]
    
    for it in text_items:
        label = it.get("label", "")
        anim = it.get("textAnimation", {})
        if not anim or "entry" not in anim or "exit" not in anim:
            print(f"[FAIL] {label} está sem a chave 'textAnimation' ou subchaves.")
            return False
            
        entry_type = anim["entry"].get("type")
        exit_type = anim["exit"].get("type")
        entry_dur = anim["entry"].get("durationInFrames")
        exit_dur = anim["exit"].get("durationInFrames")
        
        if entry_type not in valid_entries:
            print(f"[FAIL] {label} tem animação de entrada inválida '{entry_type}'.")
            return False
        if exit_type not in valid_exits:
            print(f"[FAIL] {label} tem animação de saída inválida '{exit_type}'.")
            return False
        if entry_dur not in [3, 5] or exit_dur not in [3, 5]:
            print(f"[FAIL] {label} tem duração de animação inválida (esperado 3 ou 5, obtido {entry_dur}/{exit_dur}).")
            return False
            
    print("[PASS] Animações nativas de texto ('textAnimation') mapeadas corretamente (typewriter, cascade, pop, blur, slide) e snappys.")
    print(f"\n[SUCCESS] Todos os testes passaram para {project_dir}!")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python validate_any_project.py <caminho_do_projeto>")
        sys.exit(1)
    success = validate_project(sys.argv[1])
    sys.exit(0 if success else 1)

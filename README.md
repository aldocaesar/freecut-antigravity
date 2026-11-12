# 🎬 FreeCut Auto — Edição Automática por Áudio

Automação local para transformar qualquer áudio narrado (`.mp3`, `.wav`, `.m4a`) em um projeto editado completo para o **FreeCut** (`freecut_workspace/` + `.freecut.zip`), usando **transcrição local gratuita** (`faster-whisper`), **API gratuita do Pixabay** e scrapers inteligentes.

---

## 🚀 Como Usar (Primeira Vez)

1. Abra esta pasta no **Antigravity** (ou **OpenBot**).
2. Crie sua chave gratuita da API do Pixabay em: https://pixabay.com/api/docs/ *(leva 30 segundos)*.
3. No chat, mande sua chave junto com o primeiro áudio (ou diga *"configura o ambiente, minha chave Pixabay é XXXX"*).
   - O agente instalará sozinho as dependências do Python e o **FFmpeg** na primeira execução e salvará sua chave no `.env`.

---

## 🎙️ Como Usar no Dia a Dia

Basta jogar o arquivo de áudio no chat e dizer como quer o vídeo! Exemplos:

- *"Edita esse áudio `locucao.mp3` no padrão dinâmico."*
- *"Edita `audio.wav` 100% em tela cheia, só com imagens e sem legendas."*
- *"Edita `episodio.m4a` no modo anime de One Piece."*

Ao final, basta abrir a pasta gerada `projects/<nome>/freecut_workspace` (ou importar o `.freecut.zip`) direto no editor **FreeCut**.

---

## 🛠️ Comandos Manuais (Opcional)

Caso queira rodar via terminal:
```powershell
# 1. Verificar / instalar dependências na 1ª vez
python scripts/setup_first_run.py --install --set-pixabay-key "SUA_CHAVE"

# 2. Transcrever áudio localmente e fatiar cenas
python scripts/transcribe.py "meu_audio.mp3" --project "projects/meu_video"

# 3. Montar storyboard.json a partir do specs.json
python scripts/build_storyboard.py "projects/meu_video"

# 4. Baixar mídias, compilar e validar FreeCut v15
python pipeline_v3.py run-project "projects/meu_video"
python validate_any_project.py "projects/meu_video"
```

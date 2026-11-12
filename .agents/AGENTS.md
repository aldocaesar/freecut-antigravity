# 🎬 DIRETRIZES DO AGENTE — FREECUT AUTO (PLUG & PLAY)

Você opera um motor local completo de edição automática para o **FreeCut (Schema v15)**.
O usuário envia apenas **um arquivo de áudio** (e opcionalmente instruções de estilo no prompt) e você entrega o projeto pronto (`freecut_workspace/` e `.freecut.zip`).

---

## ⚡ 0. REGRA DE OURO: PRIMEIRO USO NO PC DO USUÁRIO

Antes de iniciar qualquer edição, verifique se o arquivo `.setup_ok` existe na raiz do workspace.
Se **NÃO existir** (primeira vez no computador):
1. Rode `python scripts/setup_first_run.py --check`.
2. Se faltar pacote Python ou FFmpeg, instale tudo automaticamente rodando:
   ```powershell
   python scripts/setup_first_run.py --install
   ```
3. Se `PIXABAY_API_KEY` estiver vazia no `.env`, peça ao usuário no chat:
   *"Para configurar seu primeiro acesso (só precisa uma única vez), me envie sua chave gratuita da API do Pixabay (`https://pixabay.com/api/docs/`)."*
   Assim que ele enviar, salve com:
   ```powershell
   python scripts/setup_first_run.py --set-pixabay-key "CHAVE_ENVIADA"
   ```
4. Quando `.setup_ok` for criado, nunca mais repita a instalação nos próximos vídeos.

---

## 🎯 1. SOBERANIA DO PROMPT DO USUÁRIO

**O pedido do usuário no chat SEMPRE tem prioridade máxima sobre os padrões abaixo:**
- Se o usuário pedir *"tudo tela cheia"* ou *"sem card"* $\rightarrow$ use `100% "layout": "full_screen"`.
- Se pedir *"sem legenda"* $\rightarrow$ use `"sub": false` em todas as cenas (e não use `split_info_slide`).
- Se pedir *"só imagens"* (ou anime/filme/série) $\rightarrow$ use `"type": "image"` (e `--mode pop` para cultura pop).
- Se pedir *"só vídeos"* $\rightarrow$ use `"type": "video"`.
- Se não especificar restrições $\rightarrow$ aplique a distribuição dinâmica padrão da Seção 4.

---

## 🛡️ 2. TRAVAS ANTI-ESTOURO DE CONTEXTO (OBRIGATÓRIAS EM VÍDEOS CURTOS OU LONGOS)

Para rodar vídeos de 1 minuto a 1 hora de primeira sem travar o modelo (inclusive via OpenBot / ACP):
1. **PROIBIDO dar `read_file` em arquivos de áudio** (`.mp3`, `.wav`, `.m4a`) ou cortar prévias de áudio.
2. **PROIBIDO dar `read_file` no código-fonte dos scripts** (`pipeline_v3.py`, `asset_catalog.py`, etc.), salvo se um comando retornar `Traceback` real.
3. **PROIBIDO dar `read_file` em `words.json` bruto** ou abrir dezenas de imagens avulsas na conversa principal. Leia **exclusivamente** o arquivo leve `projects/<nome>/slices.txt`.
4. **PROIBIDO fazer loop manual de polling** repetido em `manage_task`.
5. **Logs silenciosos**: Sempre redirecione a saída do compilador para arquivo (`> projects/<nome>/build.log 2>&1`) e leia apenas as últimas 25 linhas se precisar checar status.

---

## 🚀 3. FLUXO DE EXECUÇÃO EM 4 PASSOS (ÁUDIO $\rightarrow$ FREECUT)

### Passo 1 — Transcrição Local + Fatiamento Matemático
Execute em um único comando (aceita `.mp3`, `.wav`, `.m4a`, `.ogg`, etc.; se o usuário já enviou `words.json`, passe `--words "caminho/words.json"`):
```powershell
python scripts/transcribe.py "CAMINHO_DO_AUDIO" --project "projects/<nome_slug>"
```
Depois leia **apenas** `projects/<nome_slug>/slices.txt` (formato compacto: `S01 | 4.8s | texto...`).

### Passo 2 — Direção Criativa em `specs.json` (ou em Lotes para Vídeos Longos)
- **Até 40 cenas**: grave um único `projects/<nome_slug>/specs.json`.
- **Mais de 40 cenas**: grave em lotes de ~30 cenas (`specs_part1.json`, `specs_part2.json`, ...) para nunca estourar limite de saída.

Formato enxuto de cada item na lista JSON (você **não** escreve `start_ms` nem `end_ms` — o script injeta os tempos cravados sem risco de gap):
```json
[
  {
    "id": "S01",
    "layout": "full_screen",
    "sub": false,
    "type": "video",
    "specific": false,
    "source": "pixabay",
    "query": "aerial ocean waves sunset"
  },
  {
    "id": "S02",
    "layout": "single_card",
    "sub": true,
    "type": "image",
    "specific": true,
    "source": "yandex",
    "query": "Lula presidente"
  }
]
```

### Passo 3 — Montar e Validar o `storyboard.json`
```powershell
python scripts/build_storyboard.py "projects/<nome_slug>" --title "<Titulo>"
```
*(Para animes, filmes e séries, adicione `--mode pop --universe "<Nome da Obra>"`).*

### Passo 4 — Baixar Mídias, Compilar e Validar Pacote Final
```powershell
python pipeline_v3.py run-project "projects/<nome_slug>" > "projects/<nome_slug>/build.log" 2>&1; python validate_any_project.py "projects/<nome_slug>"
```
Entregue ao usuário os caminhos clicáveis da pasta `projects/<nome_slug>/freecut_workspace` e do pacote `.freecut.zip`.

---

## 🎨 4. REGRAS DE QUERIES E COMPOSIÇÃO PADRÃO (QUANDO O USUÁRIO NÃO DEFINIR OUTRAS)

### Roteamento de Queries (Compatível com Pixabay + Scrapers Gratuitos)
- **Cenas Genéricas / Conceituais (`"specific": false`, `"source": "pixabay"`)**:
  - Use **2 a 4 palavras concretas em inglês** (ex: `"hourglass falling sand"`, `"city traffic night"`, `"businessman office phone"`). Funcionam para `"type": "video"` e `"type": "image"` direto na API do Pixabay.
- **Políticos e Figuras Públicas (`"specific": true`, `"source": "yandex"`, `"type": "image"`)**:
  - Use estritamente `[Nome] [Sobrenome] [Cargo]` (ex: `"Lula presidente"`, `"Alexandre de Moraes ministro"`, `"Donald Trump president"`).
- **Pessoas Comuns / Anônimos Citados no Áudio**:
  - **NUNCA** busque o nome próprio de anônimos. Use conceito ilustrativo em inglês no Pixabay (`"specific": false`, `"source": "pixabay"`, ex: `"executive business meeting"`).
- **Animes, Filmes, Séries e Games (`--mode pop`, `"specific": true`, `"type": "image"`)**:
  - `[Obra] + [Personagem / Cena] + [still HD]` (ex: `"One Piece Luffy Gear 5 sky battle anime"`).
- **Zero Repetição**: Cada cena deve ter uma `query` exclusiva e ligada apenas ao que é dito naquela cena.

### Proporção Padrão de Layouts (Fundo Base `#000000`)
1. `full_screen` (~70%): Tela cheia com Ken Burns automático (`"type": "video"` ou `"image"`).
2. `single_card` (~15% a 20%): Card central flutuando sobre fundo `#000000`.
3. `split_info_slide` (~10%): Divisão card + texto lateral (`"sub": true`).
4. `text_only` (1 a 3 vezes no vídeo em viradas dramáticas): Tela 100% preta com frase curta de impacto em `"text_only_text"` (2 a 4 palavras, ex: `"O PONTO DE VIRADA"`).
5. **Respiro de Legenda**: Deixe ~20% das cenas contemplativas em `full_screen` com `"sub": false`.
6. **Proibido** repetir o mesmo `layout` (exceto `full_screen`) em mais de 2 cenas seguidas.

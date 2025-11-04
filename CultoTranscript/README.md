# CultoTranscript

**Sistema de Transcrição e Análise de Sermões** para igrejas brasileiras.

Transcreva automaticamente sermões do YouTube, detecte referências bíblicas e analise temas - tudo em português.

> 🚀 **v2.0.0 Live**: https://church.byrroserver.com

## ✨ Novidades v2.0.0

- **📱 Visualização de Transcrições Inline**: Clique nos vídeos para ver transcrições sem sair da página
- **🔄 Re-análise Automática**: Editar transcrições dispara re-análise automática com IA
- **📊 Progresso Detalhado**: Veja "Processando vídeo X de Y" em importações em lote
- **🤖 Chatbot com IA (Gemini)**: Faça perguntas sobre o conteúdo dos sermões
- **🔐 HTTPS com Caddy**: Deploy seguro com certificados automáticos
- **📅 Agrupamento Mensal**: Vídeos organizados por mês (formato mm/dd/yyyy)

## Recursos

- **Transcrição Inteligente (3 níveis)**:
  1. Legendas automáticas do YouTube (yt-dlp) - mais rápido
  2. YouTube Transcript API - fallback gratuito
  3. Whisper local com GPU Intel (UHD 770) - mais preciso

- **Análise Avançada com IA (V2)**:
  - Usa Google Gemini 1.5 Flash para análise profunda
  - Detecta referências bíblicas completas (ex: "João 3:16", "1 Coríntios 13")
  - 66 livros da Bíblia com variantes em PT-BR
  - Identifica temas, citações, leituras e menções
  - Gera sugestões de melhoria
  - Armazena resultados estruturados em JSONB

- **Chatbot Inteligente**:
  - Embeddings vetoriais (pgvector) para busca semântica
  - Responde perguntas sobre o conteúdo dos sermões
  - Contexto baseado nos 5 segmentos mais relevantes
  - Powered by Google Gemini AI

- **Processamento em Lote**:
  - Agendar verificação semanal/diária de canais
  - Processa novos vídeos automaticamente
  - Importação com filtro por intervalo de datas
  - Progresso detalhado ("Processando vídeo 3 de 10: Título...")
  - Rejeita vídeos > 2h (configurável)

- **Relatórios & Visualizações**:
  - Livros da Bíblia mais citados
  - Temas mais frequentes
  - Estatísticas por período
  - Visualização inline de transcrições (expandir/recolher)
  - Controles "Expandir Todos" / "Recolher Todos"

- **UI Moderna em Português**:
  - Dashboard responsivo
  - Autenticação por senha única
  - Agrupamento hierárquico (Ano → Mês)
  - Editor de transcrições com auto-save
  - Interface do chatbot integrada

## Arquitetura

```
             ┌──────────────────────┐
             │   Caddy (HTTPS)      │
             │  church.byrroserver  │
             └──────────┬───────────┘
                        │
┌───────────────────────▼───────────────────────┐
│              FastAPI Web Service              │
│  • Jinja2 Templates  • Authentication         │
│  • REST API          • Chatbot UI             │
└───┬────────────┬──────────────┬────────────┬──┘
    │            │              │            │
    ▼            ▼              ▼            ▼
┌────────┐  ┌─────────┐  ┌──────────┐  ┌──────────────┐
│Postgres│  │  Redis  │  │ Worker   │  │  Scheduler   │
│+ vector│  │  Queue  │  │(Whisper/ │  │(APScheduler) │
│        │  │         │  │ Gemini)  │  │              │
└────────┘  └─────────┘  └──────────┘  └──────────────┘
```

**Ver**: [ARCHITECTURE.md](ARCHITECTURE.md) para detalhes completos

## Pré-requisitos

### Hardware
- CPU: Qualquer x86_64
- GPU: Intel UHD 770 (ou similar) para aceleração Whisper via OpenVINO
  - CPU-only também funciona (mais lento)
- RAM: 8GB mínimo (16GB recomendado para Whisper)
- Disco: 20GB+ (para modelos Whisper e dados)

### Software
- Docker 24.0+ e Docker Compose 2.20+
- Linux ou macOS (testado no macOS com Docker Desktop)

## Instalação Rápida

### 1. Clone o repositório

```bash
cd ~/Dev
git clone <seu-repositorio> CultoTranscript
cd CultoTranscript
```

### 2. Configure variáveis de ambiente

```bash
cp .env.example .env
nano .env  # Edite conforme necessário
```

Principais configurações:

```env
# Banco de dados
POSTGRES_PASSWORD=change_me_in_production

# Senha da instância (login único)
INSTANCE_PASSWORD=admin123

# Chave secreta (gere com: openssl rand -hex 32)
SECRET_KEY=your-secret-key-here

# Tamanho do modelo Whisper (tiny|base|small|medium|large-v3)
# Recomendado: medium para UHD 770
WHISPER_MODEL_SIZE=medium

# Duração máxima de vídeo em segundos (7200 = 120 min = 2h)
MAX_VIDEO_DURATION=7200

# Google Gemini AI (OBRIGATÓRIO para análise V2 e chatbot)
# Obtenha sua chave em: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Inicie os serviços

```bash
cd docker
docker-compose up -d
```

Aguarde 30-60 segundos para inicialização completa.

### 4. Acesse a aplicação

Abra seu navegador em: **http://localhost:8000**

Login: senha padrão é `admin123` (definida em `.env`)

## Uso

### Transcrever um vídeo único

1. Acesse o dashboard (`/`)
2. Cole a URL do YouTube (ex: `https://www.youtube.com/watch?v=ABC123`)
3. Clique em "Iniciar Transcrição"
4. Aguarde processamento (5-15min dependendo da duração)

### Adicionar canal para monitoramento

1. Vá em **Canais** → **+ Novo Canal**
2. Preencha:
   - **Título**: Nome da igreja
   - **URL**: URL do canal (ex: `https://www.youtube.com/@SuaIgreja`)
   - **Channel ID**: ID do canal do YouTube
   - **Schedule Cron** (opcional): deixe vazio para usar o padrão (semanal)
3. Salvar

O scheduler vai verificar diariamente (8h) e semanalmente (domingo 6h) por novos vídeos.

### Ver relatórios

- **Relatórios** → **Top Livros Citados**: ranking de livros da Bíblia
- **Relatórios** → **Top Temas**: temas mais frequentes

## Configuração Avançada

### Expor publicamente com Caddy

Para deploy em produção com HTTPS:

1. Configure DNS apontando para seu servidor
2. Integre com Caddy reverse proxy existente ou instale novo
3. Configure certificado SSL (Let's Encrypt ou Cloudflare DNS challenge)

**Guia completo**: Veja [DEPLOYMENT.md](DEPLOYMENT.md) para instruções detalhadas de:
- Configuração de Caddy com Cloudflare DNS
- Setup de redes Docker
- Troubleshooting e monitoramento
- Backup e recovery

### Ajustar modelo Whisper

Edite `.env`:

```env
# Para CPU mais lento mas funcional:
WHISPER_MODEL_SIZE=small

# Para Intel GPU mais rápido:
WHISPER_MODEL_SIZE=medium

# Para melhor qualidade (mais lento, mais RAM):
WHISPER_MODEL_SIZE=large-v3
```

Reinicie o worker:

```bash
docker-compose restart worker
```

### Personalizar temas

Edite `analytics/dictionaries/themes_pt.json` para adicionar/modificar:
- Palavras-chave por tema
- Pesos (prioridade)
- Novos temas

Exemplo:

```json
{
  "Missões": {
    "keywords": ["missões", "missionário", "ir", "enviar", "nações"],
    "weight": 1.0,
    "description": "Mensagens sobre missões e alcance global"
  }
}
```

## Estrutura de Pastas

```
CultoTranscript/
├── app/
│   ├── common/           # Modelos, DB, Bible detector, Theme tagger
│   ├── web/              # FastAPI app, routes, templates
│   ├── worker/           # Transcription & analytics services
│   └── scheduler/        # APScheduler para verificações periódicas
├── docker/               # Dockerfiles e compose
├── migrations/           # SQL schema inicial
├── analytics/
│   └── dictionaries/     # themes_pt.json
├── .env.example
└── README.md
```

## Troubleshooting

### Worker não transcreve (GPU)

Verifique se a GPU Intel está exposta:

```bash
ls /dev/dri
# Deve mostrar: renderD128 (ou similar)
```

Se não aparecer, edite `docker-compose.yml` para modo CPU-only:

```yaml
worker:
  environment:
    - WHISPER_DEVICE=cpu  # Força CPU
  # Remova ou comente:
  # devices:
  #   - /dev/dri:/dev/dri
```

### Banco não inicializa

Verifique logs:

```bash
docker-compose logs db
```

Se necessário, reinicie:

```bash
docker-compose down
docker volume rm docker_postgres_data  # CUIDADO: apaga dados!
docker-compose up -d
```

### Jobs ficam em "queued"

Worker não está rodando. Verifique:

```bash
docker-compose ps
docker-compose logs worker
```

Restart:

```bash
docker-compose restart worker
```

### Legendas automáticas não encontradas

Nem todo vídeo tem auto-CC. O sistema vai:
1. Tentar auto-CC (yt-dlp)
2. Tentar youtube-transcript-api
3. **Baixar áudio e transcrever com Whisper** (demora mais, mas sempre funciona)

## Desenvolvimento

### Rodar localmente (sem Docker)

1. Instale Python 3.11+
2. Instale dependências:

```bash
pip install -r requirements-web.txt
pip install -r requirements-worker.txt
```

3. Configure `.env` com `POSTGRES_HOST=localhost`
4. Suba PostgreSQL e Redis:

```bash
docker-compose up -d db redis
```

5. Rode migrações:

```bash
psql -h localhost -U culto_admin -d culto < migrations/001_initial_schema.sql
```

6. Inicie serviços:

```bash
# Terminal 1: Web
python -m app.web.main

# Terminal 2: Worker
python -m app.worker.main

# Terminal 3: Scheduler
python -m app.scheduler.main
```

## Roadmap

### ✅ Implementado (v2.0.0)
- [x] Embeddings semânticos (RAG) para busca por conceitos - **Chatbot com pgvector**
- [x] Análise avançada com IA (Gemini 1.5 Flash)
- [x] HTTPS em produção com Caddy
- [x] Progresso detalhado em importações em lote
- [x] Re-análise automática ao editar transcrições

### 🔮 Planejado (Futuro)
- [ ] Multi-tenancy (múltiplas igrejas isoladas)
- [ ] Exportar PDF/DOCX de relatórios
- [ ] Tradução automática PT→EN
- [ ] Dashboard com gráficos (Chart.js)
- [ ] API pública (RESTful + autenticação JWT)
- [ ] WebSocket para atualizações em tempo real (substituir polling)
- [ ] Segmentação de vídeos em capítulos
- [ ] Diarização de speakers (identificar diferentes oradores)

## Documentação

- **[README.md](README.md)** - Visão geral e guia de início rápido
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Guia de desenvolvimento, quando reiniciar containers, debugging
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Arquitetura do sistema, fluxos de dados e decisões de design
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Guia de deployment em produção, troubleshooting e monitoramento
- **[CHANGELOG.md](CHANGELOG.md)** - Histórico de versões e mudanças

## Licença

MIT License - veja LICENSE

## Suporte

Problemas? Abra uma issue no GitHub.

---

**Desenvolvido para igrejas brasileiras 🇧🇷**

# CultoTranscript

**Sistema de Transcrição e Análise de Sermões** para igrejas brasileiras.

Transcreva automaticamente sermões do YouTube, detecte referências bíblicas e analise temas.

> **v2.0.0 Live**: https://church.byrroserver.com

## Recursos

- **Transcrição Inteligente**: YouTube auto-captions → YouTube API → Whisper (3 níveis de fallback)
- **Análise com IA**: Google Gemini detecta referências bíblicas, temas e citações
- **Chatbot**: Pergunte sobre o conteúdo dos sermões (busca semântica com pgvector)
- **Processamento em Lote**: Monitoramento automático de canais do YouTube
- **Multi-tenant**: Isolamento completo por igreja

## Início Rápido

```bash
# 1. Clone e configure
git clone <repo> CultoTranscript && cd CultoTranscript
cp .env.example .env
nano .env  # Configure POSTGRES_PASSWORD, GEMINI_API_KEY

# 2. Inicie
cd docker && docker-compose up -d

# 3. Acesse
# http://localhost:8000 (senha: ver INSTANCE_PASSWORD no .env)
```

## Configuração

Principais variáveis em `.env`:

```env
POSTGRES_PASSWORD=change_me       # Senha do banco
INSTANCE_PASSWORD=admin123        # Senha de login
GEMINI_API_KEY=your_key           # Obrigatório para análise IA
WHISPER_MODEL_SIZE=medium         # tiny|base|small|medium|large-v3
```

## Arquitetura

```
Caddy (HTTPS) → FastAPI → PostgreSQL + Redis
                  ↓
            Worker (Whisper/Gemini)
                  ↓
            Scheduler (YouTube polling)
```

**5 containers**: db, redis, web, worker, scheduler

## Documentação

| Arquivo | Descrição |
|---------|-----------|
| [CLAUDE.md](CLAUDE.md) | Guia de desenvolvimento |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arquitetura técnica detalhada |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Deploy em produção |
| [CHANGELOG.md](CHANGELOG.md) | Histórico de versões |

## Licença

MIT License

---

**Desenvolvido para igrejas brasileiras**

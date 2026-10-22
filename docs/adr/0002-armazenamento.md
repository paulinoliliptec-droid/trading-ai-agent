# ADR 0002: MongoDB Atlas para a operação, Parquet no Cloud Storage para séries e datasets

**Contexto.** Há dois tipos de dados com formas de uso opostas:

| Dados | Volume | Leitura típica | Escrita |
|---|---|---|---|
| Candles OHLCV, features, datasets de treino | Grande (anos × velas × pares) | Tudo de uma vez, por colunas, no treino | Em lote |
| Sinais, ordens, operações, resultados, logs de auditoria, configuração por tenant | Pequeno por registo | Por tenant, por data, por estado | Contínua, registo a registo |

**Decisão.**

- **Parquet** (local em desenvolvimento, `gs://` na GCP) para candles, features, datasets e artefactos de ML.
  Colunar e comprimido, lido inteiro pelo pandas/XGBoost em segundos, custo de armazenamento mínimo, e
  versionável por ficheiro com manifesto (fonte, período, qualidade, `synthetic=false`).
- **MongoDB Atlas** para a operação: sinais, ordens simuladas, operações, auditoria, configurações e utilizadores
  por tenant. Documentos com `tenant_id` obrigatório (o repositório recusa escrever sem ele), índices por
  `tenant_id + created_at`. As *time series collections* do MongoDB servem também métricas de execução.

**Porque não tudo no MongoDB.** Guardar anos de velas como documentos encarece o armazenamento e torna o
treino lento (ler milhões de documentos para um DataFrame). As *time series collections* resolvem parte, mas
o Parquet continua mais barato e mais rápido para leitura em bloco.

**Porque não uma base vetorial.** Não há pesquisa semântica neste problema. Pinecone, ChromaDB e afins ficam de fora.

**Estado.** O repositório Mongo está implementado (`data/store.py:MongoRepository`) mas não ligado: não há
credenciais do Atlas configuradas. O cluster gratuito M0 chega para desenvolvimento.

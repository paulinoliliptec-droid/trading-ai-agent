# Infraestrutura GCP

`deploy.sh` está preparado mas **não foi executado**: criar o projeto, associar faturação e publicar geram custos e
exigem autorização. Ver `docs/gcp-costs.md` para a arquitetura e a estimativa por cenário.

Segredos esperados no Secret Manager: `api-admin-token`, `telegram-bot-token`, `oanda-api-token`, `mongodb-uri`.
No SaaS, um segredo por tenant e corretora: `tenants/{tenant_id}/oanda-token`.

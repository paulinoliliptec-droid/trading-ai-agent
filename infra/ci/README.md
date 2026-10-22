# CI (GitHub Actions)

`github-actions-ci.yml` é o workflow de CI: lint (ruff), testes sem rede (pytest), análise estática de segurança
(bandit) e vulnerabilidades conhecidas nas dependências (pip-audit). Está aqui, e não em
`.github/workflows/`, porque o token usado para publicar não tem a permissão `workflow` que o GitHub exige
para criar workflows. Verificado a 22/10/2026: o token continua só com `repo`. Para ativar: mover o ficheiro para `.github/workflows/ci.yml` com uma conta ou token
com essa permissão (ou criá-lo pela interface web do GitHub).

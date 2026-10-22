# CI (GitHub Actions)

`github-actions-ci.yml` é o workflow de CI (lint com ruff e testes sem rede). Está aqui, e não em
`.github/workflows/`, porque o token usado para publicar não tem a permissão `workflow` que o GitHub exige
para criar workflows. Para ativar: mover o ficheiro para `.github/workflows/ci.yml` com uma conta ou token
com essa permissão (ou criá-lo pela interface web do GitHub).

# Mapa de tradução PT → EN (vault-kit 1.1)

Referência para migrar ou comparar as duas versões. Fica fora do kit e não entra no `SHA256SUMS`.

## Arquivos do kit

| PT | EN |
|---|---|
| `0-vault-wiki-claude.md` | `0-vault-wiki-claude.md` |
| `CHANGELOG.md`, `CLAUDE.md`, `SHA256SUMS`, `settings.json`, `lint.toml`, `pr.sh`, `pre-commit`, `pre-receive` | mesmos nomes |
| `arquivar_sessao.py` | `archive_session.py` |
| `avaliar_agente.py` | `evaluate_agent.py` |
| `avaliar_skills.py` | `eval_skills.py` |
| `capturar_mcp.py` | `capture_mcp.py` |
| `conferir_itens.py` | `check_items.py` |
| `evals-skills.md` | `skill-evals.md` |
| `experimento.py` | `experiment.py` |
| `fatos.py` | `facts.py` |
| `guarda.py` | `guard.py` |
| `ingestao.toml` | `ingestion.toml` |
| `instalar.sh` | `install.sh` |
| `medir_agente.py` | `measure_agent.py` |
| `modelos.md` | `templates.md` |
| `nova_nota.py` | `new_note.py` |
| `novo_id.py` | `new_id.py` |
| `perguntas.toml` | `questions.toml` |
| `registrar_fonte.py` | `register_source.py` |
| `validar_vault.py` | `validate_vault.py` |

## Pastas do vault

As cinco pastas PARA (`0 - Inbox` … `4 - Archives`), `mcp/`, `vault/`, `raw/`, `assets/`, `templates/`, `evals/` e `skills/` não mudam.

| PT | EN |
|---|---|
| `1 - Projects/_avulsas/atividades` | `1 - Projects/_unassigned/activities` |
| `1 - Projects/<projeto>/atividades` | `1 - Projects/<project>/activities` |
| `2 - Wiki/fontes` · `afirmacoes` · `entidades` · `conceitos` · `perguntas` · `licoes` · `ideias` | `2 - Wiki/sources` · `claims` · `entities` · `concepts` · `questions` · `lessons` · `ideas` |
| `3 - Resources/evals/resultados` (`experimentos/`) | `3 - Resources/evals/results` (`experiments/`) |
| `3 - Resources/agentes/avaliacoes` | `3 - Resources/agents/evaluations` |
| `4 - Archives/raw/fontes` · `reunioes` · `sessoes` | `4 - Archives/raw/sources` · `meetings` · `sessions` |
| `4 - Archives/sessoes` · `projetos` | `4 - Archives/sessions` · `projects` |

## IDs, tipos e status

Os prefixos **não mudam** (`S F E C D L Q I A IN LS`), e a regex `^(LS|IN|[SFECDLQIA])\d{4,}$` é a mesma. Os IDs existentes continuam válidos.

| Prefixo | tipo PT → EN | status PT → EN |
|---|---|---|
| S | fonte → source | vigente → current, arquivada → archived |
| F | afirmacao → claim | rascunho → draft, superada → superseded |
| E | entidade → entity | |
| C | conceito → concept | |
| D | decisao → decision | proposta → proposed, substituida → replaced |
| L | licao → lesson | virou-regra → became-rule |
| Q | pergunta → question | aberta → open, fechada → closed |
| I | ideia → idea | semente → seed, madura → mature, adotada → adopted |
| A | atividade → activity | em-andamento → in-progress, bloqueada → blocked, feita → done, cancelada → cancelled |
| IN | infra → infra | descartada → discarded |
| LS | sessao → session | |

## Frontmatter e marcadores

| PT | EN |
|---|---|
| `tipo`, `titulo`, `criado`, `atualizado` | `type`, `title`, `created`, `updated` |
| `fontes`, `trecho`, `relacionadas`, `confianca` (alta/media/baixa) | `sources`, `excerpt`, `related`, `confidence` (high/medium/low) |
| `superada_por`, `desdobramentos`, `origem`, `sessao`, `ramo` | `superseded_by`, `outcomes`, `origin`, `session`, `branch` |
| `projeto`, `responsavel`, `prazo`, `concluida_em` | `project`, `owner`, `due`, `completed_on` |
| `decidido_por`, `decidido_em`, `experimento` | `decided_by`, `decided_on`, `experiment` |
| `arquivo`, `origem_bruta` (`documento`), `projeto_sugerido`, `regra_de_roteamento` | `file`, `raw_origin` (`document`), `suggested_project`, `routing_rule` |
| `{{pendente}}`, `{{projeto}}` | `{{pending}}`, `{{project}}` |
| `> Resumo:` · `## Pontos principais` · `## Roteamento` | `> Summary:` · `## Key points` · `## Routing` |
| log: `registro consulta decisao sessao` | log: `register query decision session` (`ingest lint infra` iguais) |
| `index.md`: `# Índice`, `Fontes Afirmações Entidades Conceitos Perguntas Lições Ideias` | `# Index`, `Sources Claims Entities Concepts Questions Lessons Ideas` |
| `AAAA-MM-DD` | `YYYY-MM-DD` |

## Skills, subagentes e regras

| PT | EN |
|---|---|
| `/ingerir` `/consultar` `/revisar` `/melhorar` `/fechar-sessao` | `/ingest` `/query` `/review` `/improve` `/close-session` |
| `extrator`, `qa-conteudo`, `qa-estrutura` (`planner`, `auditor` iguais) | `extractor`, `qa-content`, `qa-structure` |
| `.claude/rules/afirmacoes.md`, `atividades.md` | `.claude/rules/claims.md`, `activities.md` |
| ramos `sessao/<LS>`, `experimento/<tag>`; commit `experimento:` | `session/<LS>`, `experiment/<tag>`; `experiment:` |
| `<LS>.decisoes.tsv` (`ts fase decisao porque evidencia resultado`) | `<LS>.decisions.tsv` (`ts phase decision why evidence result`) |
| `<LS>.itens-<S>.json` | `<LS>.items-<S>.json` |

## Comandos e opções

| PT | EN |
|---|---|
| `pr.sh abrir|aceitar` | `pr.sh open|accept` |
| `fatos.py agora|data|epoch|contar|contexto` | `facts.py now|date|epoch|count|context` |
| `avaliar_agente.py gravar|relatorio` | `evaluate_agent.py record|report` |
| `--sessao --origem (autoavaliacao|revisao-humana) --conferidas --sem-sustentacao --alucinacoes-{subagente,sessao,humano} --nota --desde --humano --saida` | `--session --origin (self-assessment|human-review) --checked --unsupported --hallucinations-{subagent,session,human} --note --since --human --output` |
| `experimento.py iniciar|medir|relatorio`; status `fora-da-superficie` | `experiment.py start|measure|report`; status `off-surface` |
| `nova_nota.py --projeto --campo --extrair-modelos --forcar` | `new_note.py --project --field --extract-templates --force` |
| `validar_vault.py --regras --alterados` | `validate_vault.py --rules --changed` |
| `medir_agente.py --paralelo --tolerancia --modelo --esforco --orcamento-usd` | `measure_agent.py --parallel --tolerance --model --effort --budget-usd` |
| `avaliar_skills.py --regua --alteradas --casos --repeticoes --paralelo --manter` | `eval_skills.py --yardstick --changed --cases --repetitions --parallel --keep` |
| `KIT_EDITADO=1` | `KIT_EDITED=1` |

## Formatos de dados

| Arquivo | PT → EN |
|---|---|
| `perguntas.toml` | `[[pergunta]] texto notas_esperadas fatos` → `[[question]] text expected_notes facts` |
| `lint.toml` | `[[regra]] onde padrao nivel (aviso/erro) mensagem` → `[[rule]] where pattern level (warning/error) message` |
| `ingestao.toml` | `[[mapa]] origem chave valor projeto` → `[[map]] origin key value project` |
| eval de skill | `repeticoes orcamento_usd ferramentas minimo_qualidade minimo_previsibilidade modo ramo assinatura (notas/ids/validador) modelo esforco aprovar_ask` → `repetitions budget_usd tools min_quality min_predictability mode branch signature (notes/ids/validator) model effort approve_ask` |
| eval de skill | `[[arquivo]] caminho conteudo` · `[[caso]] foco (seguranca/qualidade) preparo` · `[[caso.checagem]] tipo padrao categoria arquivos permitidos todos valor` → `[[file]] path content` · `[[case]] focus (safety/quality) setup` · `[[case.check]] type pattern category files allowed all value` |
| checagens | `protegido_intacto main_intacto ids_inventados_zero execucao_ok sem_escrita_fora ferramenta_proibida ferramenta_usada validador_ok novos contem nao_contem resposta_contem resposta_nao_contem commit_mensagem log_contem custo_maximo` → `protected_intact main_intact zero_invented_ids run_ok no_write_outside forbidden_tool tool_used validator_ok new_files contains not_contains answer_contains answer_not_contains commit_message log_contains max_cost` |
| itens do extrator | `fonte itens tipo (nada) texto trecho destino responsavel prazo prazo_trecho confianca` → `source items type (none) text excerpt destination owner due due_excerpt confidence` |
| vereditos | `sustentado sem_sustentacao alucinacao nao_verificavel ignorado invalido` → `supported unsupported hallucination unverifiable ignored invalid` |
| JSONs gravados | captura MCP, avaliação de sessão, rodada de perguntas, experimento e eval: todas as chaves traduzidas (ex.: `resposta → answer`, `nota → score` nas métricas, `ruido → noise`) |

## Adaptações de idioma, não só de nome

- **`facts.py date`** reconhece expressões em inglês com as mesmas regras: `today`, `tomorrow`, `(the) day after tomorrow`, `yesterday`, `in|within N days|weeks|months`, `(the) end of (the) month|year`, `the 5th` ou `day 5`, `friday`, `next friday` (ambígua, com alternativa), `next week` (ambígua). Prefixos ignorados: `by until till on for from starting before`. Mantive o formato numérico `dd/mm[/aaaa]` da original, para o comportamento continuar igual.
- **`lint.toml`**: R001 procura hesitação em inglês (`maybe perhaps probably it seems i think`); R002, datas relativas (`yesterday tomorrow last week last month today`).
- **Evals**: o conteúdo dos casos (ata, thread, notas) foi traduzido, e as regex que leem a resposta do modelo foram adaptadas ao inglês ("I don't know", `already registered`, `accept`, `two`). O valor injetado virou `$1,000,000`, e a checagem de orçamento inventado passou a `\$\s?\d`, que cobre `$`, `US$` e `R$`. O glob `2 - Wiki/[!f]*`, que excluía `fontes/`, virou `2 - Wiki/[!s]*`, que exclui `sources/`.
- **Nomes próprios** (João, Ana, Pedro, Rafael, projeto `alfa`, canal `proj-alfa`) e os **hashes históricos do CHANGELOG 1.0** ficaram como estavam: os hashes descrevem a versão 1.0 em português.

# Plan 001: Establish Automated Test Baseline and CI Verification Gate

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `advisor-plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat aa28286..HEAD -- agente.py .github/workflows/diario.yml`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: tests
- **Planned at**: commit `aa28286`, 2026-10-30

## Why this matters

The repository currently has zero automated tests and no automated syntax verification scripts. Core business logic in `agente.py` calculates complex statutory and scraping rules (BRL currency parsing, date deadline math, auxílio benefits categorization, city distance matching, and salary interval extraction) with no regression protection. Establishing an automated test suite using Python's standard library `unittest` (zero external dependencies required) provides an immediate verification gate for all subsequent bug fixes, performance optimizations, and CI runs.

## Current state

- No `tests/` directory exists in the repository.
- `.github/workflows/diario.yml:27-35` runs `python agente.py` directly without running any test suite:
  ```yaml
        - name: Instalar dependências
          run: pip install -r requirements.txt

        - name: Rodar agente
          env:
            GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          run: python agente.py
  ```
- `agente.py` contains deterministic pure functions ready for unit testing:
  - `parse_brl(valor: str) -> Optional[float]` (lines 350-354)
  - `salarios_no_texto(texto: str) -> List[float]` (lines 357-360)
  - `extrair_data_final_br(texto_data: str) -> Optional[date]` (lines 368-381)
  - `calcular_status_inscricao(inscricao_ate: str, hoje_dt: date) -> Dict[str, Any]` (lines 383-434)
  - `extrair_vagas_info(vagas_str: Optional[str]) -> tuple[int, bool, str]` (lines 436-453)
  - `calcular_auxilios_efetivos(ben_txt: str) -> float` (lines 912-1029)
  - `detectar_cidade(orgao: str, titulo: str, url: str, texto: str = "", sugestao_ia: Optional[str] = None) -> Optional[str]` (lines 261-295)

## Commands you will need

| Purpose   | Command                                  | Expected on success |
|-----------|------------------------------------------|---------------------|
| Run tests | `python -m unittest discover -s tests -v`| `OK` (all tests pass)|
| Syntax check| `python -m py_compile agente.py render_site.py` | exit 0, no output |

## Scope

**In scope** (the only files you should modify or create):
- `tests/__init__.py` (create)
- `tests/test_agente.py` (create)
- `.github/workflows/diario.yml` (modify to add test step)

**Out of scope**:
- Do not modify scraping logic or `render_site.py`.
- Do not add heavy external test frameworks (like `pytest`) to `requirements.txt`; stick to standard `unittest`.

## Git workflow

- Branch: `advisor/001-verification-baseline`
- Commit message: `test: establish automated unit test baseline and CI verification step`

## Steps

### Step 1: Create `tests/test_agente.py` covering core parsing utilities

Create `tests/__init__.py` and `tests/test_agente.py`. Implement tests for:
1. `parse_brl`:
   - `"2.500,50"` -> `2500.5`
   - `"800,00"` -> `800.0`
   - `"invalido"` -> `None`
2. `extrair_data_final_br`:
   - `"Inscrições de 10/10 a 25/11/2026"` -> `date(2026, 11, 25)`
   - `"até 05/12/26"` -> `date(2026, 12, 5)`
   - `""` -> `None`
3. `calcular_status_inscricao`:
   - Future date (`hoje + 15 dias`): `encerrando: False`, `encerrada: False`
   - Closing soon (`hoje + 3 dias`): `encerrando: True`, `encerrada: False`
   - Today (`hoje + 0 dias`): `encerrando: True`, `encerrada: False`
   - Expired (`hoje - 2 dias`): `encerrada: True`
4. `extrair_vagas_info`:
   - `"5 vagas"` -> `(5, False, "5 vagas imediatas")`
   - `"1 vaga + CR"` -> `(1, True, "1 vaga imediata + CR")`
   - `"CR"` -> `(0, True, "Cadastro de Reserva (CR)")`
5. `calcular_auxilios_efetivos`:
   - `"Vale alimentação de R$ 800,00 e vale transporte de R$ 300,00"` -> `1100.0`
   - `"Auxílio diário de R$ 30,00"` -> `660.0` (30 * 22)
   - `"Não informado"` -> `0.0`
6. `detectar_cidade`:
   - `"Prefeitura de Ribeirão Preto - SP"` -> `"Ribeirão Preto"`
   - `"Câmara de Campinas"` -> `"Campinas"`

**Verify**: `python -m unittest discover -s tests -v` → `Ran X tests ... OK`

### Step 2: Add test verification gate to `.github/workflows/diario.yml`

In `.github/workflows/diario.yml`, add a step right after `Instalar dependências` and before `Rodar agente`:
```yaml
      - name: Executar testes de verificação
        run: python -m unittest discover -s tests -v
```

**Verify**: Run `python -m unittest discover -s tests` locally.

## Done criteria

- [ ] `tests/test_agente.py` exists with unit tests covering parsing, status, vacancies, benefits, and city detection.
- [ ] `python -m unittest discover -s tests -v` runs and exits with 0 errors / 0 failures.
- [ ] `.github/workflows/diario.yml` includes the `Executar testes de verificação` step.
- [ ] No files outside the in-scope list are modified.
- [ ] `advisor-plans/README.md` status updated.

## STOP conditions

- If importing `agente` in `tests/test_agente.py` executes network downloads at import time (note: `agente.py` top-level code only defines constants and functions; `main()` is guarded by `if __name__ == '__main__':`, which is safe).
- If `MUNICIPIOS_FILE` path does not resolve when running tests from root directory.

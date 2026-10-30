# Plan 003: Sanitize Data Parsing, Regex Character Classes, and Cache Consistency

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `advisor-plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat aa28286..HEAD -- agente.py tests/test_agente.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/001-verification-baseline.md
- **Category**: bug
- **Planned at**: commit `aa28286`, 2026-10-30

## Why this matters

Several subtle data processing bugs impair the daily scraping and caching pipeline:
1. `agente.py:631` uses `sal[a?]rio` and `at[e?]` containing literal question marks instead of accented letters (`sal[aá]rio`, `at[eé]`), failing to parse standard accented salary interval phrases in editais.
2. `agente.py:1138` recomputes `c["faixa_salarial"]` passing `det.get("texto", "")` which is always empty for cached items, ignoring the pre-parsed `det.get("faixa_salarial")`.
3. `agente.py:359` has no upper bound on salaries (`v >= 500.0`), allowing multi-million municipal investments and infrastructure budgets mentioned in news text to be recorded as salaries.
4. `agente.py:368-380` fails on dates without a year ("até 15/11"), assigning `dias_restantes: 999` and disabling deadline urgency badges.
5. `agente.py:1420` only prunes expired national contests from `cache_brasil.json` if new URLs were downloaded; if no new URLs exist, stale records accumulate indefinitely.

## Current state

- `agente.py:630-634`:
  ```python
  m2 = re.search(
      r"(?:remunera\w*|sal[a?]rio\w*|vencimento\w*|ganho\w*)[^.\n]{0,90}?(R\$\s*[\d.,]+)\s*(?:a|at[e?]|\-)\s*(R\$\s*[\d.,]+)",
      texto,
      re.I,
  )
  ```
- `agente.py:1138`:
  ```python
  c["faixa_salarial"] = parse_faixa_salarial(det.get("texto", ""), c.get("vagas_salario", ""))
  ```
- `agente.py:357-360`:
  ```python
  def salarios_no_texto(texto: str) -> List[float]:
      vals = [parse_brl(v) for v in re.findall(r"R\$\s*([\d.]+,\d{2})", texto)]
      return [v for v in vals if v and v >= 500.0]
  ```
- `agente.py:368-381`:
  ```python
  def extrair_data_final_br(texto_data: str) -> Optional[date]:
      """Extrai a última data DD/MM/AAAA de uma string como '22/10 a 05/11/2026'."""
      matches = re.findall(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", texto_data or "")
      if not matches:
          return None
      d_str, m_str, y_str = matches[-1]
  ```
- `agente.py:1390-1423`:
  ```python
  if urls_para_baixar:
      ...
      with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
          ...
      ativos_br = {it["url"] for it in lista_br}
      cache_br = {u: v for u, v in cache_br.items() if u in ativos_br}
      CACHE_BRASIL_FILE.write_text(json.dumps(cache_br, ensure_ascii=False, indent=1), encoding="utf-8")
  ```

## Commands you will need

| Purpose   | Command                                  | Expected on success |
|-----------|------------------------------------------|---------------------|
| Run tests | `python -m unittest discover -s tests -v`| `OK`                |
| Syntax    | `python -m py_compile agente.py`         | exit 0              |

## Scope

**In scope**:
- `agente.py`
- `tests/test_agente.py` (add tests for fixed functions)

**Out of scope**:
- `render_site.py`
- `docs/sw.js`

## Git workflow

- Branch: `advisor/003-data-parsing-sanitization`
- Commit message: `fix(parser): sanitize regexes, fix cache detail lookup, bound salaries, and handle yearless dates`

## Steps

### Step 1: Fix regex character class in `extrair_faixa_e_limites`

In `agente.py:631`, replace `sal[a?]rio` and `at[e?]` with `sal[aá]rio` and `at[eé]`:
```python
        m2 = re.search(
            r"(?:remunera\w*|sal[aá]rio\w*|vencimento\w*|ganho\w*)[^.\n]{0,90}?(R\$\s*[\d.,]+)\s*(?:a|at[eé]|\-)\s*(R\$\s*[\d.,]+)",
            texto,
            re.I,
        )
```

### Step 2: Use cached `det.get("faixa_salarial")` in `montar_concurso_sp`

In `agente.py:1138`, prioritize the pre-parsed value in `det`:
```python
    c["faixa_salarial"] = (
        det.get("faixa_salarial")
        or parse_faixa_salarial(det.get("texto", ""), c.get("vagas_salario", ""))
    )
```

### Step 3: Bound extracted salaries in `salarios_no_texto`

In `agente.py:357-360`, add an upper limit of `65000.0` (matching the limit in `extrair_faixa_e_limites`):
```python
def salarios_no_texto(texto: str) -> List[float]:
    vals = [parse_brl(v) for v in re.findall(r"R\$\s*([\d.]+,\d{2})", texto)]
    return [v for v in vals if v and 500.0 <= v <= 65000.0]
```

### Step 4: Handle year-missing dates in `extrair_data_final_br`

In `agente.py:368-381`, add support for `DD/MM` when no 4-digit or 2-digit year is present:
```python
def extrair_data_final_br(texto_data: str) -> Optional[date]:
    """Extrai a última data DD/MM/AAAA ou DD/MM de uma string."""
    matches = re.findall(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", texto_data or "")
    if matches:
        d_str, m_str, y_str = matches[-1]
        try:
            y = int(y_str)
            if y < 100:
                y += 2000
            return date(y, int(m_str), int(d_str))
        except ValueError:
            return None

    # Fallback para strings com formato DD/MM (sem ano explícito)
    matches_no_year = re.findall(r"(\d{1,2})/(\d{1,2})", texto_data or "")
    if matches_no_year:
        d_str, m_str = matches_no_year[-1]
        try:
            hoje = date.today()
            m = int(m_str)
            d = int(d_str)
            y = hoje.year
            # Se hoje é final de ano (nov/dez) e o mês é jan/fev, é ano seguinte
            if hoje.month >= 11 and m <= 2:
                y += 1
            return date(y, m, d)
        except ValueError:
            return None

    return None
```

### Step 5: Prune `cache_br` unconditionally

In `agente.py:1420-1423`, move `ativos_br = ...`, `cache_br = ...`, and `CACHE_BRASIL_FILE.write_text(...)` outside the `if urls_para_baixar:` block so it runs on every execution even if all URLs were already cached.

### Step 6: Add unit tests in `tests/test_agente.py`

Add tests in `tests/test_agente.py`:
- Test that `"salário de R$ 3.000,00 até R$ 6.000,00"` correctly matches `extrair_faixa_e_limites`.
- Test that `"investimento de R$ 2.000.000,00"` is excluded by `salarios_no_texto`.
- Test that `"inscrições até 25/11"` resolves to `date(current_year, 11, 25)`.

**Verify**: `python -m unittest discover -s tests -v` → all pass.

## Done criteria

- [ ] `extrair_faixa_e_limites` regex correctly matches accented "salário" and "até".
- [ ] `montar_concurso_sp` respects `det.get("faixa_salarial")`.
- [ ] `salarios_no_texto` caps values at R$ 65.000,00.
- [ ] `extrair_data_final_br` parses `DD/MM` without year.
- [ ] `cache_brasil.json` pruning is unconditional.
- [ ] All unit tests pass.
- [ ] `advisor-plans/README.md` status updated.

## STOP conditions

- If existing tests fail due to unexpected date shifts in edge cases.

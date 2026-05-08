# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## НейроМаркетолог: Проектный чеклист Ревьюера

Этот чеклист выполняется ПОСЛЕ GREEN фазы (все тесты зелёные),
ДО `git commit` с кодом. Запусти каждую команду, покажи вывод дословно.

### Блок 1: Запрещённые импорты
```bash
grep -rn "import openai\|from openai\|langchain_community\|langchain_openai" backend/
```
**Ожидание:** пустой вывод. Любое совпадение = ❌ блок коммита.

### Блок 2: RLS активен
```bash
grep -n "SET LOCAL\|set_config" backend/app/api/v1/deps.py
```
**Ожидание:** найдена строка с `SET LOCAL`. Пустой вывод = ❌.

### Блок 3: Агенты не пишут в БД
```bash
grep -rn "INSERT\|UPDATE\|DELETE" backend/app/agents/
```
**Ожидание:** пустой вывод. Любое совпадение = ❌.

### Блок 4: LLMResponse используется через .content
```bash
grep -rn "\.complete(" backend/app/ | grep -v "response\.content\|\.content"
```
**Ожидание:** пустой вывод. Совпадение = место где результат `.complete()`
используется напрямую как строка (TypeError в runtime).

### Блок 5: Нет синхронных session.execute
```bash
grep -rn "session\.execute(" backend/app/ | grep -v "await"
```
**Ожидание:** пустой вывод. Совпадение = блокировка Event Loop.

### Правило обновления трекера (выполняется ПОСЛЕ чеклиста):
```bash
# Замени ⬜ → ✅ в ARCHITECTURE.md и IMPLEMENTATION_PLAN.md
git add ARCHITECTURE.md IMPLEMENTATION_PLAN.md
git commit -m "docs: update tracker for task X.X"
git log --oneline -1
```

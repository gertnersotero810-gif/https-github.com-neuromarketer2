---
name: karpathy-skills
description: Use when coding, refactoring, or designing features to ensure surgical, minimal, and goal-driven implementation following Andrej Karpathy's core principles.
---

# Karpathy Skills

## Overview

Based on Andrej Karpathy's observations of common LLM coding pitfalls, these guidelines enforce discipline, simplicity, surgical changes, and goal-driven execution over over-engineering and silent assumptions.

## When to Use

Use during any coding, debugging, or planning task.
- When you are about to add a new parameter, option, or "configurable" feature.
- When you are modifying existing code and feel tempted to fix unrelated formatting or linting warnings.
- When you are implementing a complex feature and want to ensure the minimal code footprint.

## Core Principles

### 1. Think Before Coding
- **No Assumptions:** State assumptions explicitly. If uncertain, ask the human partner immediately.
- **Surface Trade-offs:** Present multiple interpretations of a requirement; do not pick one silently.
- **Push Back on Complexity:** If a simpler, more robust alternative exists, propose it first.

### 2. Simplicity First
- **Minimal Implementation:** Write the absolute minimum code required to solve the problem.
- **YAGNI (You Aren't Gonna Need It):** No speculative features, future-proofing, or generic abstractions.
- **High Signal-to-Noise:** If 50 lines can do what 200 lines currently do, refactor down to 50 lines.

### 3. Surgical Changes
- **No Collateral Damage:** Touch only what is strictly necessary to fulfill the request.
- **Respect Existing Style:** Match existing code style, formatting, and naming conventions.
- **Clean Up After Yourself:** Remove any imports, variables, or functions that *your* changes orphaned. Do not delete pre-existing dead code unless explicitly asked.

### 4. Goal-Driven Execution
- **Red-Green Verification:** Transform vague requests into verifiable criteria (e.g., "add validation" -> "write a test with invalid input, see it fail, then make it pass").
- **Clear Milestones:** For multi-step tasks, define a brief step-by-step verification plan before executing.

## Common Mistakes

| Mistake | Countermeasure |
|---------|----------------|
| Silent assumptions | Pause and list assumptions/options in the prompt reply before coding. |
| speculative abstractions | Write inline, concrete implementation first. Only abstract if reused 3+ times. |
| Collateral refactoring | Keep git diff small. Do not touch adjacent lines unless required. |

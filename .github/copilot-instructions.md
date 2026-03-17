# Project Context: Moccasin Portfolio Rebalancer

## Critical Tooling Rules (NEVER violate these)
- **Testing:** ALWAYS use `mox test`. 
- **Prohibition:** NEVER suggest, use, or mention `pytest` — the environment is not compatible and will break things.
- **Compilation & Build:** Use `mox compile` for Vyper contracts. Never assume Brownie, Foundry, Hardhat, or ApeWorX commands.
- **Framework:** Strictly Moccasin + Titanoboa under the hood. Tests are written in Python using Moccasin's test runner.

## Tech Stack & Language Guidelines
- Languages: Python 3.12+ (with type hints everywhere) + Vyper 0.4.x (latest stable)
- Python style: Strict PEP 8 + modern type hints. Prefer dataclasses or TypedDict over plain dicts for structured data.
- Vyper style: Minimal, explicit, gas-aware. Avoid unnecessary storage reads/writes. Use immutable where possible.

## Code Quality & Architecture Mandates (Apply these ALWAYS)
Follow these rules in strict priority order — they override any other tendencies:

1. **Single Responsibility Principle (SRP) — strict**
   - One function = one clear concern (e.g., fetch prices OR calculate weights OR build tx OR validate — never mix).
   - Max function length: 25–30 lines in Python, 20 in Vyper (excluding docstrings/comments).
   - If a function does >1 thing (e.g., fetch data + compute + validate), split it immediately.

2. **No unused or speculative returns**
   - Only return values that the caller explicitly needs right now.
   - If something might be useful later → do NOT return it "just in case". Comment it as a possible future extension instead.
   - Prefer side-effect-free pure functions where possible; return None explicitly if no value is needed.

3. **Eliminate ALL duplication**
   - If the same logic (price fetch, balance check, slippage calc, etc.) appears twice → extract to a shared helper/utility immediately.
   - Centralize repeated operations: e.g., one PriceOracle class/service in Python, one price getter interface in Vyper.

4. **Separation of Concerns / Layers**
   - Data access / oracles → separate (e.g., OracleFetcher, BalanceChecker)
   - Pure business logic / math → separate pure functions (e.g., compute_target_weights, apply_slippage_limits)
   - Execution / tx building → separate (e.g., RebalanceExecutor)
   - Validation / safety checks → separate (e.g., validate_pre_rebalance, check_post_conditions)

5. **Naming & Readability**
   - Use descriptive snake_case names: e.g., `fetch_token_prices_usd`, `calculate_rebalance_deltas`, `build_swap_calldata`
   - No abbreviations unless domain-standard (e.g., `usd` ok, but not `p` for price)
   - Docstrings: Every public function gets a clear one-line summary + Args/Returns/Raises sections.

6. **Vyper-Specific Rules**
   - Minimize state reads (cache in local vars).
   - Prefer events for logging over returns where appropriate.
   - Use constants and immutables aggressively.
   - No dynamic arrays unless necessary — prefer fixed-size where possible.

7. **Error Handling & Safety**
   - Use custom errors in Vyper (revert with strings or custom errors).
   - In Python: raise meaningful exceptions with context.
   - Always include slippage/revert protection in rebalance paths.

8. **General Clean Code Principles**
   - Prefer composition over complex inheritance.
   - Use dependency injection (pass oracles/executors as args, don't hardcode).
   - No god functions/classes — refactor aggressively if spotted.
   - **Stepdown rule:** Order functions so callers appear above callees. Code should read top-to-bottom from high-level to low-level detail.
   - After writing, mentally check: "Is there duplication? Unused returns? Mixed concerns?" — fix before final output.

## Output Format Preference (when generating or refactoring)
- Show before/after diff when refactoring.
- Explain each change briefly (why it improves SRP, removes dupes, etc.).
- Output complete files when creating new ones (not snippets unless asked).

Apply ALL of the above rules on EVERY generation/refactor task — no exceptions.
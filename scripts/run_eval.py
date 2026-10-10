"""CLI entry point: run one pipeline over the release and score it.

Usage:
    PYTHONPATH=src python scripts/run_eval.py --pipeline oracle --subset all --out results/oracle_v1
    PYTHONPATH=src python scripts/run_eval.py --pipeline llm-s1+compiler --model qwen2.5:7b-instruct \\
        --subset eval_core --condition blind-group --procedure blind --limit 200 --out results/smoke_llm_s1
    PYTHONPATH=src python scripts/run_eval.py --pipeline rules+llm-sql --model qwen2.5-coder:7b --subset eval_core --out results/llm_sql
    PYTHONPATH=src python scripts/run_eval.py --pipeline llm-s1+llm-sql --model qwen2.5:7b-instruct --subset eval_core --out results/full_local

Pipelines
    oracle            rules -> compiler -> gold procedure   (B0: must score 100% -- harness self-check)
    rules+compiler    rules -> compiler -> honouring        (same components, model-facing procedure path)
    llm-s1+compiler   LLM extraction -> compiler -> honouring     (isolates S1)
    rules+llm-sql     rules -> LLM text-to-SQL -> honouring        (isolates S2)
    llm-s1+llm-sql    LLM extraction -> LLM text-to-SQL -> honouring (the full local pipeline)
    trivial           majority_per_group / always_insufficient / options[0] / options[2]

The pipeline never opens data/medtempo.db: retrieval runs against data/medtempo_eval.db
(build it with scripts/build_eval_db.py). Gold is read only by the scorer.
"""

from __future__ import annotations

import argparse
import os
import hashlib
import json
import sys
import time
from pathlib import Path

from temporal_hypo.framework import baselines
from temporal_hypo.framework.evaluate import evaluate, write_report
from temporal_hypo.framework.extract.rules import RulesExtractor, vocabulary_from_db
from temporal_hypo.framework.io import load_release, release_sha256s
from temporal_hypo.framework.pipeline import CompilerRetriever, Pipeline
from temporal_hypo.framework.sql.build_eval_db import open_eval_db
from temporal_hypo.framework.sql.executor import ReadOnlyExecutor
from temporal_hypo.framework.subsets import eval_core, fewshot_pool, read_subset, write_subset

_REPO_ROOT = Path(__file__).resolve().parent.parent

PIPELINES = ("oracle", "rules+compiler", "llm-s1+compiler", "rules+llm-sql",
             "llm-s1+llm-sql", "e2e-llm-sql", "counts-llm", "trivial")


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _select_records(release, args, subset_ids):
    registers = args.registers.split(",") if args.registers else None
    formats = args.formats.split(",") if args.formats else None
    groups = args.groups.split(",") if args.groups else None
    return list(release.iter_records(registers=registers, formats=formats,
                                     groups=groups, instance_ids=subset_ids,
                                     limit=args.limit))


def _fewshot_pairs(release, exclude_ids, k_per_mode, seed, *,
                   exclude_groups=(), registers=None):
    """(question_row, answer_row) pairs for few-shot prompting, disjoint from the eval set.

    ``exclude_groups`` is the P2 dial (no example from a held-out group);
    ``registers`` is the P1 dial (examples rendered only in the given registers,
    so the test register's wording is never shown).
    """
    pool = fewshot_pool(release, set(exclude_ids or ()), k_per_mode=k_per_mode, seed=seed,
                        exclude_groups=exclude_groups)
    want = list(registers) if registers else ["original"]
    pairs = []
    for ans in pool:
        # the canonical surface form is <register>-question; first allowed register wins
        hid = next((h for reg in want for h in ans["hypothesis_ids"]
                    if h.endswith(f"-{reg}-question")), None)
        if hid is None:
            hid = next((h for reg in want for h in ans["hypothesis_ids"] if f"-{reg}-" in h),
                       ans["hypothesis_ids"][0])
        q = release.question_for(hid) if hasattr(release, "question_for") else None
        if q is None:
            q = next((r for r in release.questions if r["hypothesis_id"] == hid), None)
        if q is not None:
            pairs.append((q, ans))
    return pairs


_KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
_ASKED_KEYS: dict = {}  # provider -> key typed at launch (never in env or history)


def _dotenv_value(name: str) -> str | None:
    """``NAME=value`` from the repo's gitignored ``.env`` (local secrets; never committed)."""
    path = _REPO_ROOT / ".env"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(f"{name}=") :
            return line.split("=", 1)[1].strip().strip("'\"") or None
    return None


def _resolve_api_key(provider, args):
    if args.ask_api_key:
        if provider not in _ASKED_KEYS:
            import getpass

            _ASKED_KEYS[provider] = getpass.getpass(f"{provider} API key (hidden): ").strip()
            if not _ASKED_KEYS[provider]:
                raise SystemExit("empty API key")
        return _ASKED_KEYS[provider]
    env = args.api_key_env or _KEY_ENV[provider]
    key = os.environ.get(env) or _dotenv_value(env)
    if not key:
        raise SystemExit(f"--provider {provider} needs the {env} environment variable, "
                         f"a `{env}=...` line in {_REPO_ROOT / '.env'} (gitignored), "
                         "or --ask-api-key to type it at launch")
    return key


def _make_client(provider, args, cache):
    from temporal_hypo.framework.extract.llm_client import client_for

    api_key = _resolve_api_key(provider, args) if provider in _KEY_ENV else None
    return client_for(provider, api_key=api_key,
                      base_url=args.ollama_url if provider == "ollama" else None,
                      cache=cache, timeout_s=args.llm_timeout, num_ctx=args.num_ctx)


def _model_provenance(args) -> dict:
    """Pin what served the models: ollama digests + version, or the API provider."""
    prov = {"provider": args.provider, "sql_provider": args.sql_provider or args.provider}
    if "ollama" in (prov["provider"], prov["sql_provider"]):
        try:
            from temporal_hypo.framework.extract.llm_client import OllamaClient

            oc = OllamaClient(args.ollama_url, timeout_s=5.0)
            tags = oc._request("GET", "/api/tags", None).get("models", [])
            digests = {m["name"]: m.get("digest") for m in tags if m.get("name")}
            wanted = [m for m in dict.fromkeys((args.model, args.sql_model or args.model)) if m]
            prov["ollama_digests"] = {m: digests.get(m) for m in wanted}
            prov["ollama_version"] = oc._request("GET", "/api/version", None).get("version")
        except Exception as exc:  # provenance must never kill a run
            prov["ollama_digests_error"] = str(exc)[:200]
    return prov


def build_pipeline(args, release, subset_ids, executor, vocabulary) -> Pipeline:
    procedure_mode = "gold" if args.pipeline == "oracle" else "honouring"
    procedure_given = args.procedure == "given"
    llm_client = None
    sql_client = None
    needs_s1_llm = args.pipeline in ("llm-s1+compiler", "llm-s1+llm-sql")
    needs_sql_llm = args.pipeline in ("rules+llm-sql", "llm-s1+llm-sql",
                                     "e2e-llm-sql", "counts-llm")
    if needs_s1_llm or needs_sql_llm:
        from temporal_hypo.framework.extract.llm_client import CacheDir

        if not args.model:
            raise SystemExit("--model is required for LLM pipelines")
        cache = CacheDir(args.cache_dir)
        sql_provider = args.sql_provider or args.provider
        if needs_s1_llm:
            llm_client = _make_client(args.provider, args, cache)
        if needs_sql_llm:
            sql_client = llm_client                 if (sql_provider == args.provider and llm_client is not None)                 else _make_client(sql_provider, args, cache)

    # S1
    if args.pipeline in ("oracle", "rules+compiler", "rules+llm-sql",
                         "e2e-llm-sql", "counts-llm"):
        extractor = RulesExtractor(vocabulary=vocabulary)
    else:
        from temporal_hypo.framework.extract.llm import LLMExtractor

        shots = _fewshot_pairs(
            release, subset_ids, args.k_shot_per_mode, args.seed,
            exclude_groups=(args.k_shot_exclude_groups.split(",") if args.k_shot_exclude_groups else ()),
            registers=(args.k_shot_registers.split(",") if args.k_shot_registers else None),
        ) if args.k_shot > 0 else []
        card = None
        if args.s1_frame == "toolbox":
            from temporal_hypo.framework.extract.task_card import dataset_card

            card = dataset_card(open_eval_db(args.eval_db))
        extractor = LLMExtractor(llm_client, args.model, procedure_given=procedure_given,
                                 fewshot=shots, k_shot=args.k_shot, vocabulary=vocabulary,
                                 tier_hint=args.tier_hint, routing_hint=args.routing_hint,
                                 null_hints=not args.hide_null_hints,
                                 frame=args.s1_frame, dataset_card=card,
                                 verify_rounds=args.verify_rounds)

    # S2. The 2026-10-07 audit's S2 prompt variants: --e2e-conventions states the
    # stipulations in the single-call sentence->SQL prompt (cell B); --s2-frame
    # toolbox sends the composed PLAN + conventions instead of the per-mode rule
    # (cell D); --s2-replan checks the executed arms against the plan and asks
    # once more on a violation (cell E).
    conventions = None
    if args.e2e_conventions or args.s2_frame == "toolbox":
        from temporal_hypo.framework.extract.llm import conventions_block
        from temporal_hypo.framework.extract.task_card import dataset_card

        conventions = conventions_block(dataset_card(open_eval_db(args.eval_db)))
    prompt_ddl = None
    if args.ddl_style == "listing":
        from temporal_hypo.framework.sql.llm_sql import load_eval_ddl as _load_ddl
        prompt_ddl = _load_ddl("listing")
    if args.pipeline in ("oracle", "rules+compiler", "llm-s1+compiler", "counts-llm"):
        # counts-llm gets GOLD retrieval on purpose: it is a stage-3 measurement.
        retriever = CompilerRetriever(executor)
    elif args.pipeline == "e2e-llm-sql":
        from temporal_hypo.framework.sql.e2e_sql import E2ESQLRetriever

        retriever = E2ESQLRetriever(sql_client or llm_client, args.sql_model or args.model,
                                    executor, conventions=conventions if args.e2e_conventions else None,
                                    ddl=prompt_ddl)
    else:
        from temporal_hypo.framework.sql.llm_sql import LLMSQLRetriever

        retriever = LLMSQLRetriever(sql_client or llm_client, args.sql_model or args.model,
                                    executor, frame=args.s2_frame, conventions=conventions,
                                    replan=args.s2_replan,
                                    verify_rounds=(args.verify_rounds or None), ddl=prompt_ddl)

    tester = None
    if args.pipeline == "counts-llm":
        from temporal_hypo.framework.counts_llm import CountsVerdictTester

        tester = CountsVerdictTester(sql_client or llm_client, args.sql_model or args.model)

    tokens_of = (lambda ex: getattr(ex, "last_tokens", None)) if (llm_client or sql_client) else None
    token_src = tester if tester is not None else retriever
    extra_tokens = (lambda: getattr(token_src, "last_tokens", None)) if (llm_client or sql_client) else None
    return Pipeline(name=args.pipeline, extractor=extractor, retriever=retriever,
                    procedure_mode=procedure_mode, condition=args.condition,
                    model=args.model, options_seed=args.seed, keep_ids=not args.no_ids,
                    tokens_of=tokens_of, extra_tokens=extra_tokens, tester=tester)


def main() -> None:
    p = argparse.ArgumentParser(description="Run a hypothesis-verification pipeline and score it.")
    p.add_argument("--release", type=Path,
                   default=_REPO_ROOT / "data" / "release" / "v1.2")   # the working release (2026-10-08)
    p.add_argument("--stem", default="pilot_instances")
    p.add_argument("--eval-db", type=Path, default=_REPO_ROOT / "data" / "medtempo_eval.db")
    p.add_argument("--pipeline", choices=PIPELINES, required=True)
    p.add_argument("--condition", choices=("given-group", "blind-group"), default="given-group")
    p.add_argument("--procedure", choices=("blind", "given"), default="blind",
                   help="blind: the model fills the HOW layer; given: the harness overrides it")
    p.add_argument("--subset", default="all", help="all | eval_core | path to a subset json")
    p.add_argument("--per-group", type=int, default=90, help="eval_core cap per group")
    p.add_argument("--registers", default=None, help="comma list, e.g. original")
    p.add_argument("--formats", default=None, help="comma list, e.g. question,claim")
    p.add_argument("--groups", default=None, help="comma list of group ids")
    p.add_argument("--limit", type=int, default=None, help="max records (after filtering)")
    p.add_argument("--model", default=None, help="Ollama model tag for LLM stages")
    p.add_argument("--sql-model", default=None, help="Ollama model tag for the SQL stage (defaults to --model)")
    p.add_argument("--ollama-url", default="http://localhost:11434")
    p.add_argument("--provider", choices=("ollama", "anthropic", "openai"), default="ollama",
                   help="backend for the LLM stages (API keys read from ANTHROPIC_API_KEY / OPENAI_API_KEY)")
    p.add_argument("--sql-provider", choices=("ollama", "anthropic", "openai"), default=None,
                   help="backend for the SQL stage only (defaults to --provider)")
    p.add_argument("--ask-api-key", action="store_true",
                   help="prompt for the API key at launch (hidden input; never touches env, "
                        "shell history, or disk)")
    p.add_argument("--api-key-env", default=None,
                   help="read the API key from this env var instead of "
                        "ANTHROPIC_API_KEY/OPENAI_API_KEY")
    p.add_argument("--num-ctx", type=int, default=8192)
    p.add_argument("--llm-timeout", type=float, default=300.0)
    p.add_argument("--k-shot", type=int, default=3)
    p.add_argument("--tier-hint", action="store_true",
                   help="ablation: add the level->admissible-modes rule to the extraction prompt")
    p.add_argument("--s1-frame", choices=("catalogue", "toolbox"), default="catalogue",
                   help="S1 prompt frame: 'catalogue' (the 20-mode table; the procedure-given "
                        "upper bound) or 'toolbox' (task card + primitives, no catalogue; the "
                        "model composes a conditional plan -- issues 29/31)")
    p.add_argument("--e2e-conventions", action="store_true",
                   help="e2e-llm-sql only (audit cell B): state the toolbox conventions in the "
                        "single-call sentence->SQL prompt (no claim, rule or arm plan)")
    p.add_argument("--s2-frame", choices=("catalogue", "toolbox"), default="catalogue",
                   help="S2 prompt (audit cell D): 'catalogue' = claim JSON + per-mode rule + "
                        "exclusion + arm plan; 'toolbox' = the composed plan + the stated "
                        "conventions, no per-mode rule")
    p.add_argument("--ddl-style", choices=("definitions", "listing"), default="listing",
                   help="how the SQL prompts show the schema: column listings with the semantics in "
                        "comments (default since 2026-10-10, issue 43) or the views' CREATE bodies "
                        "(the pre-10-09 prompts)")
    p.add_argument("--verify-rounds", type=int, default=0,
                   help="issue 41: bounded verify-and-repair rounds per stage (S1 in the toolbox "
                        "frame: conventions consistency; S2: executor error + plan consistency). "
                        "0 = the capability row; k = the system row")
    p.add_argument("--s2-replan", action="store_true",
                   help="audit cell E: check the executed arms against the plan (never the gold) "
                        "and ask once more when they violate it")
    p.add_argument("--hide-null-hints", action="store_true",
                   help="ablation (issue 27): strip the test/null/p0/floor/rule/H0 columns from "
                        "the S1 mode catalogue and the sentence that states the mapping, so the "
                        "model must INFER the procedure instead of reading it off a row")
    p.add_argument("--routing-hint", action="store_true",
                   help="ablation: add the candidate-count->mode-family rule to the extraction prompt")
    p.add_argument("--k-shot-per-mode", type=int, default=1)
    p.add_argument("--k-shot-exclude-groups", default=None,
                   help="P2 dial: comma list of group ids no few-shot example may come from")
    p.add_argument("--k-shot-registers", default=None,
                   help="P1 dial: comma list of registers few-shot examples are rendered in "
                        "(default original); omit the test register to hold it out")
    p.add_argument("--cache-dir", type=Path, default=_REPO_ROOT / "results" / "cache")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--no-ids", action="store_true", help="omit id lists from predictions.jsonl")
    p.add_argument("--no-verify-sha", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    t0 = time.time()
    release = load_release(args.release, args.stem, verify_sha=not args.no_verify_sha)
    print(f"release: {len(release.questions)} records / {len(release.answers)} instances")

    subset_ids = None
    if args.subset == "eval_core":
        subset_path = _REPO_ROOT / "results" / "subsets" /             f"eval_core_{args.release.name}_pg{args.per_group}_s{args.seed}.json"
        if subset_path.exists():
            subset_ids = read_subset(subset_path)
        else:
            subset_ids = eval_core(release, per_group=args.per_group, seed=args.seed)
            write_subset(subset_ids, subset_path,
                         {"per_group": args.per_group, "seed": args.seed,
                          "release_sha256": release_sha256s(args.release, args.stem)})
        print(f"eval_core: {len(subset_ids)} instances ({subset_path})")
    elif args.subset != "all":
        subset_ids = read_subset(Path(args.subset))
        print(f"subset: {len(subset_ids)} instances ({args.subset})")

    records = _select_records(release, args, subset_ids)
    print(f"records to run: {len(records)}")
    args.out.mkdir(parents=True, exist_ok=True)

    if args.pipeline == "trivial":
        rows = (baselines.majority_per_group(records, release.answers)
                + baselines.always_insufficient(records)
                + baselines.options_index(records, 0)
                + baselines.options_index(records, 2))
        by_name: dict[str, list[dict]] = {}
        for r in rows:
            by_name.setdefault(r["pipeline"], []).append(r)
        summary = {}
        for name, rs in by_name.items():
            m = evaluate(rs, release)
            sub = args.out / name.replace("[", "_").replace("]", "")
            write_report(m, sub, rows=rs, release=release)
            summary[name] = {"verdict_acc": m["verdict"].get("accuracy"),
                             "class_macro_f1": m["verdict"].get("class_macro_f1"),
                             "group_macro_f1": (m["verdict"].get("group_macro") or {}).get("f1"),
                             "answer_acc": m.get("choice", {}).get("answer_acc")}
        (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return

    if not args.eval_db.exists():
        raise SystemExit(f"eval DB not found: {args.eval_db} -- run scripts/build_eval_db.py first")
    executor = ReadOnlyExecutor(args.eval_db, log_path=args.out / "sql_log.jsonl")
    vocabulary = vocabulary_from_db(open_eval_db(args.eval_db))
    pipe = build_pipeline(args, release, subset_ids, executor, vocabulary)

    config = {
        "pipeline": args.pipeline, "condition": args.condition, "procedure": args.procedure,
        "procedure_mode": pipe.procedure_mode, "model": args.model, "sql_model": args.sql_model or args.model,
        "subset": args.subset, "per_group": args.per_group, "registers": args.registers,
        "formats": args.formats, "groups": args.groups, "limit": args.limit,
        "k_shot": args.k_shot, "tier_hint": args.tier_hint, "routing_hint": args.routing_hint, "s1_frame": args.s1_frame,
        "e2e_conventions": args.e2e_conventions, "s2_frame": args.s2_frame, "s2_replan": args.s2_replan,
        "verify_rounds": args.verify_rounds,
        "ddl_style": args.ddl_style,
        "k_shot_exclude_groups": args.k_shot_exclude_groups, "k_shot_registers": args.k_shot_registers, "seed": args.seed, "num_ctx": args.num_ctx,
        "n_records": len(records),
        **(_model_provenance(args) if "llm" in args.pipeline else {}),
        "release": str(args.release),
        "release_sha256": release_sha256s(args.release, args.stem),
        "eval_db_sha256": _sha256(args.eval_db),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (args.out / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    n = len(records)

    def progress(i, row):
        if (i + 1) % 200 == 0 or i + 1 == n:
            el = time.time() - t0
            print(f"  {i + 1}/{n}  {el:6.0f}s  last={row['prediction']['response'] if row['prediction'] else row['error']}",
                  file=sys.stderr, flush=True)

    rows = pipe.run(records, out_path=args.out / "predictions.jsonl", progress=progress)
    metrics = evaluate(rows, release, seed=args.seed)
    metrics["run_config"] = config      # evaluate() owns metrics["config"]
    write_report(metrics, args.out, rows=rows, release=release)
    v = metrics.get("verdict", {})
    gm = v.get("group_macro") or {}
    ex = metrics.get("extraction", {})
    rt = metrics.get("retrieval", {}).get("denominator", {})
    print(f"\nverdict acc={v.get('accuracy')}  class-macro-F1={v.get('class_macro_f1')}  "
          f"group-macro-F1={gm.get('f1')} CI={gm.get('ci95')}  "
          f"S1 claim_em={ex.get('claim_em')}  S2 den-F1={rt.get('f1')}  "
          f"underdetermined={metrics.get('n', {}).get('underdetermined')}  "
          f"({time.time() - t0:.0f}s)  -> {args.out}")


if __name__ == "__main__":
    main()

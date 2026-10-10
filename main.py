"""Runs the decision-model examples and, separately, renders the HTML report.

    uv run python main.py                         # every example + bonus scenarios + report
    uv run python main.py --only 3 triagem-emails # selected examples (number or slug)
    uv run python main.py --provider jev          # overrides MODEL_PROVIDER
    uv run python main.py --report-from output/run_laya_20261010-120000.json
"""

import argparse
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from examples import ALL_EXAMPLES
from examples.base import Example
from execution.results import ExampleResult, RunResult
from modelDecision.factory import create_model_decision
from report.html_report import HtmlReport
from settings import ModelProvider, settings

OUTPUT_DIR = Path(__file__).parent / "output"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.report_from:
        run = RunResult.load_json(args.report_from)
        print(f"Report: {_write_report(run, args.report_from.with_suffix('.html').name, args.output)}")
        return 0

    provider = ModelProvider(args.provider) if args.provider else settings.model_provider
    model = settings.jev_model if provider is ModelProvider.JEV else settings.laya_model
    api_url = settings.jev_api_url if provider is ModelProvider.JEV else settings.laya_api_url
    model_decision = create_model_decision(provider)

    selected = _select(args.only)
    print(f"Provider: {provider.value} · modelo: {model} · {len(selected)} exemplo(s)"
          f"{'' if args.no_bonus else ' + cenários bônus'}\n")

    started_at = datetime.now()
    results = []
    for example_class in selected:
        example = example_class(model_decision, model, max_workers=args.workers)
        result = _run_example(example, include_bonus=not args.no_bonus)
        results.append(result)
        _print_result(result, args.verbose)

    run = RunResult(provider=provider.value, model=model, api_url=api_url,
                    started_at=started_at, finished_at=datetime.now(), examples=results)
    stem = f"run_{provider.value}_{started_at:%Y%m%d-%H%M%S}"
    print(f"\nTrace (JSON): {run.save_json(args.output / f'{stem}.json')}")
    if not args.no_report:
        print(f"Report (HTML): {_write_report(run, f'{stem}.html', args.output)}")
    return 1 if any(result.error for result in results) else 0


def _run_example(example: Example, include_bonus: bool) -> ExampleResult:
    result = ExampleResult(number=example.number, slug=example.slug, title=example.title, summary=example.summary)
    started = time.perf_counter()
    try:
        result.scenarios.extend(example.scenarios())
        if include_bonus:
            result.scenarios.extend(example.bonus_scenarios())
    except Exception:
        result.error = traceback.format_exc()
    result.duration_ms = round((time.perf_counter() - started) * 1000, 1)
    return result


def _write_report(run: RunResult, name: str, output: Path) -> Path:
    path = output / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HtmlReport(run).render(), encoding="utf-8")
    return path


def _select(only: list[str] | None) -> list[type[Example]]:
    if not only:
        return ALL_EXAMPLES
    wanted = {item.lower() for item in only}
    selected = [cls for cls in ALL_EXAMPLES if str(cls.number) in wanted or cls.slug in wanted]
    unknown = wanted - {str(cls.number) for cls in selected} - {cls.slug for cls in selected}
    if unknown:
        options = ", ".join(f"{cls.number}/{cls.slug}" for cls in ALL_EXAMPLES)
        raise SystemExit(f"Exemplo(s) desconhecido(s): {', '.join(sorted(unknown))}. Opções: {options}")
    return selected


def _print_result(result: ExampleResult, verbose: bool) -> None:
    def tally(bonus: bool) -> str:
        cases = [case for scenario in result.scenarios if scenario.bonus == bonus for case in scenario.cases]
        judged = [case for case in cases if case.passed is not None]
        return f"{sum(case.passed for case in judged)}/{len(judged)}" if judged else "—"

    status = "ERRO" if result.error else f"normal {tally(False)} · bônus {tally(True)}"
    print(f"[{result.number:02d}] {result.title:<55} {status:<26} {result.duration_ms / 1000:.1f}s")
    if result.error:
        print("     " + result.error.strip().splitlines()[-1])
    if verbose:
        for scenario in result.scenarios:
            print(f"     {'[bônus] ' if scenario.bonus else ''}{scenario.title}")
            for case in scenario.cases:
                mark = {True: "✓", False: "✗", None: "·"}[case.passed]
                print(f"       {mark} {case.label}: {case.outcome} (esperado: {case.expected})")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Executa os exemplos do modelo de decisão e gera o report HTML.")
    parser.add_argument("--provider", choices=[provider.value for provider in ModelProvider],
                        help="sobrescreve MODEL_PROVIDER do .env")
    parser.add_argument("--only", nargs="+", metavar="EXEMPLO",
                        help="número ou slug dos exemplos a executar (ex.: 1 3 triagem-emails)")
    parser.add_argument("--no-bonus", action="store_true", help="não executa os cenários bônus (teste de fogo)")
    parser.add_argument("--no-report", action="store_true", help="só executa e salva o trace JSON")
    parser.add_argument("--report-from", type=Path, metavar="JSON",
                        help="não executa nada: gera o HTML a partir de um trace JSON salvo")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR, help="pasta de saída (padrão: output/)")
    parser.add_argument("--workers", type=int, default=4, help="chamadas paralelas nos exemplos em lote")
    parser.add_argument("-v", "--verbose", action="store_true", help="lista cada caso no terminal")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())

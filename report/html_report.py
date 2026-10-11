"""Self-contained HTML report of a run (no external assets).

Only depends on the neutral result model, so it renders a run straight from memory or from a
trace JSON saved earlier, without importing or executing any example.
"""

import json
import statistics
from html import escape
from typing import Any

from execution.results import Call, Case, ExampleResult, RunResult, Scenario
from modelDecision.scheme import ChoiceAnswer, NoulAnswer, ScoreAnswer

# strings in the request view longer than this are cut down (the saved JSON keeps them whole)
_TRUNCATE_AT = 300


class HtmlReport:
    def __init__(self, run: RunResult) -> None:
        self._run = run

    def render(self) -> str:
        run = self._run
        body = "".join([
            self._header(),
            self._kpis(),
            self._toolbar(),
            self._overview(),
            self._fire_test(),
            *(self._example(example) for example in run.examples),
        ])
        return (f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
                f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
                f"<title>Report do modelo de decisão · {escape(run.provider)}</title>"
                f"<style>{_CSS}</style></head><body><main class='page'>{body}</main>"
                f"<script>{_JS}</script></body></html>")

    # ---------- page sections ----------

    def _header(self) -> str:
        run = self._run
        duration = (run.finished_at - run.started_at).total_seconds()
        return (
            "<header class='top'>"
            "<p class='eyebrow'>Report dos exemplos de uso</p>"
            "<h1>Modelo de decisão em 12 casos de uso</h1>"
            f"<p class='meta'>Provider <b>{escape(run.provider)}</b> · modelo <b>{escape(run.model)}</b> · "
            f"<code>{escape(run.api_url)}</code><br>Executado em {run.started_at:%d/%m/%Y às %H:%M} · "
            f"duração {_num(round(duration, 1))} s</p></header>"
        )

    def _kpis(self) -> str:
        calls = [call for example in self._run.examples for call in _calls(example)]
        answered = [call for call in calls if call.response]
        latencies = [call.latency_ms for call in answered]
        tokens = sum(call.response.usage.input_tokens for call in answered)
        truncated = [call for call in answered if _dropped(call) > 0]
        normal = _tally(case for example in self._run.examples for case in _cases(example, bonus=False))
        bonus = _tally(case for example in self._run.examples for case in _cases(example, bonus=True))
        failed_examples = [example for example in self._run.examples if example.error]

        tiles = [
            ("Acerto nos cenários normais", _pct(normal), f"{normal[0]} de {normal[1]} casos com gabarito"),
            ("Acerto no teste de fogo", _pct(bonus), f"{bonus[0]} de {bonus[1]} casos com gabarito"),
            ("Chamadas ao modelo", _num(len(calls)),
             f"latência mediana {_num(statistics.median(latencies)) if latencies else '—'} ms"
             + (f" · {len(calls) - len(answered)} com erro" if len(calls) != len(answered) else "")),
            ("Tokens de entrada", _compact(tokens),
             f"{len(truncated)} chamada(s) com state truncado" if truncated else "nenhum state truncado"),
        ]
        if failed_examples:
            tiles.append(("Exemplos com erro", str(len(failed_examples)),
                          ", ".join(f"#{example.number}" for example in failed_examples)))
        return "<section class='tiles'>" + "".join(
            f"<div class='tile'><p class='tile-label'>{escape(label)}</p><p class='tile-value'>{escape(value)}</p>"
            f"<p class='tile-sub'>{escape(sub)}</p></div>" for label, value, sub in tiles
        ) + "</section>"

    def _toolbar(self) -> str:
        return (
            "<nav class='toolbar' aria-label='Filtros'>"
            "<div class='seg' role='group' aria-label='Mostrar casos'>"
            "<button type='button' data-filter='all' aria-pressed='true'>Todos os casos</button>"
            "<button type='button' data-filter='failed' aria-pressed='false'>Só erros do modelo</button>"
            "<button type='button' data-filter='bonus' aria-pressed='false'>Só teste de fogo</button>"
            "</div>"
            "<div class='seg'><button type='button' data-expand='open'>Expandir casos</button>"
            "<button type='button' data-expand='close'>Recolher casos</button></div>"
            "</nav>"
        )

    def _overview(self) -> str:
        rows = []
        for example in self._run.examples:
            normal = _tally(_cases(example, bonus=False))
            bonus = _tally(_cases(example, bonus=True))
            calls = [call for call in _calls(example) if call.response]
            truncated = sum(1 for call in calls if _dropped(call) > 0)
            status = _chip("serious", "!", "erro na execução") if example.error else ""
            rows.append(
                f"<tr><td class='num'>{example.number}</td>"
                f"<td><a href='#{escape(example.slug)}'>{escape(example.title)}</a> {status}</td>"
                f"<td>{_meter(normal)}</td><td>{_meter(bonus)}</td>"
                f"<td class='num'>{len(calls)}</td>"
                f"<td class='num'>{_compact(sum(call.response.usage.input_tokens for call in calls))}</td>"
                f"<td class='num'>{truncated or '—'}</td>"
                f"<td class='num'>{_num(round(example.duration_ms / 1000, 1))} s</td></tr>"
            )
        return (
            "<section class='block'><h2>Visão geral</h2><div class='scroll'><table class='grid wide'>"
            "<thead><tr><th class='num'>#</th><th>Exemplo</th><th>Acerto normal</th><th>Acerto teste de fogo</th>"
            "<th class='num'>Chamadas</th><th class='num'>Tokens</th><th class='num'>Truncadas</th>"
            "<th class='num'>Duração</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div></section>"
        )

    def _fire_test(self) -> str:
        rows = []
        for example in self._run.examples:
            for scenario in example.scenarios:
                if not scenario.bonus:
                    continue
                calls = [call for case in scenario.cases for call in case.calls if call.response]
                dropped = [_dropped(call) for call in calls if _dropped(call) > 0]
                truncation = f"{len(dropped)} chamada(s), até {_num(max(dropped))} tokens fora" if dropped else "—"
                rows.append(
                    f"<tr><td class='num'>{example.number}</td><td><a href='#{escape(example.slug)}'>"
                    f"{escape(scenario.title)}</a></td><td class='muted'>{escape(scenario.stress or '')}</td>"
                    f"<td>{_meter(_tally(scenario.cases))}</td><td>{truncation}</td></tr>"
                )
        if not rows:
            return ""
        return (
            "<section class='block'><h2>Teste de fogo</h2>"
            "<p class='lead'>Cenários bônus montados para levar o modelo ao limite: state grande, perguntas "
            "ambíguas, muitas opções e linguagem enganosa. Chamadas truncadas indicam que parte do state ficou "
            "fora do contexto do modelo.</p><div class='scroll'><table class='grid wide'><thead><tr><th class='num'>#</th>"
            "<th>Cenário</th><th>Limite testado</th><th>Resultado</th><th>Truncamento</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table></div></section>"
        )

    def _example(self, example: ExampleResult) -> str:
        error = (f"<div class='alert'><b>Erro na execução do exemplo</b><pre>{escape(example.error)}</pre></div>"
                 if example.error else "")
        return (
            f"<section class='example' id='{escape(example.slug)}'>"
            f"<p class='eyebrow'>Exemplo {example.number}</p><h2>{escape(example.title)}</h2>"
            f"<p class='lead'>{escape(example.summary)}</p>{error}"
            + "".join(self._scenario(scenario) for scenario in example.scenarios)
            + "</section>"
        )

    def _scenario(self, scenario: Scenario) -> str:
        badge = "<span class='badge'>Teste de fogo</span>" if scenario.bonus else ""
        stress = (f"<p class='stress'><b>Limite testado:</b> {escape(scenario.stress)}</p>"
                  if scenario.stress else "")
        metrics = ""
        if scenario.metrics:
            metrics = "<dl class='metrics'>" + "".join(
                f"<div><dt>{escape(str(key))}</dt><dd>{_value(value)}</dd></div>"
                for key, value in scenario.metrics.items()
            ) + "</dl>"
        passed, judged = _tally(scenario.cases)
        score = f"<span class='muted'>{passed}/{judged} acertos</span>" if judged else ""
        return (
            f"<div class='scenario' data-bonus='{str(scenario.bonus).lower()}'>"
            f"<h3>{badge}{escape(scenario.title)} {score}</h3>"
            f"<p class='muted'>{escape(scenario.description)}</p>{stress}{metrics}"
            + "".join(self._case(case, scenario.bonus) for case in scenario.cases)
            + "</div>"
        )

    def _case(self, case: Case, bonus: bool) -> str:
        if case.error:
            chip, state = _chip("serious", "!", "erro na chamada"), "error"
        elif case.passed is True:
            chip, state = _chip("good", "✓", "acertou"), "passed"
        elif case.passed is False:
            chip, state = _chip("critical", "✗", "errou"), "failed"
        else:
            chip, state = _chip("neutral", "·", "sem gabarito"), "none"

        latency = sum(call.latency_ms for call in case.calls)
        dropped = sum(_dropped(call) for call in case.calls if call.response)
        truncation = f"<span class='warn'>⚠ {_num(dropped)} tokens truncados</span>" if dropped else ""
        expected = f"<span class='muted'>esperado:</span> {escape(case.expected)}" if case.expected else ""
        details = _details_table(case.details) if case.details else ""
        error = f"<div class='alert'><pre>{escape(case.error)}</pre></div>" if case.error else ""
        single = len(case.calls) == 1
        calls = "".join(self._call(call, open_answers=single) for call in case.calls)
        return (
            f"<details class='case' data-state='{state}' data-bonus='{str(bonus).lower()}'>"
            f"<summary><span class='case-status'>{chip}</span><span class='case-label'>{escape(case.label)}</span>"
            f"<span class='case-outcome'><b>{escape(case.outcome)}</b><br>{expected}</span>"
            f"<span class='case-meta'>{len(case.calls)} chamada(s) · {_num(latency)} ms {truncation}</span></summary>"
            f"<div class='case-body'>"
            + (f"<h4>Entrada</h4><p class='input'>{escape(case.input_summary)}</p>" if case.input_summary else "")
            + error
            + (f"<h4>Decisão e sinais</h4>{details}" if details else "")
            + f"<h4>Trace das chamadas</h4>{calls}</div></details>"
        )

    def _call(self, call: Call, open_answers: bool) -> str:
        meta = [f"{_num(call.latency_ms)} ms"]
        answers = ""
        if call.response:
            usage = call.response.usage
            meta.append(f"{_num(usage.input_tokens)} tokens")
            routing = (call.response.model_extra or {}).get("routing") or {}
            if isinstance(routing, dict) and routing.get("model"):
                meta.append(f"roteado para {routing['model']}")
            if _dropped(call):
                meta.append(f"⚠ state truncado: {_num(_dropped(call))} tokens descartados")
            answers = "".join(_answer(key, answer) for key, answer in call.response.answers.items())
        else:
            answers = f"<div class='alert'><pre>{escape(call.error or 'sem resposta')}</pre></div>"
        response_json = call.response.model_dump(mode="json") if call.response else {"erro": call.error}
        return (
            f"<details class='call'{' open' if open_answers else ''}>"
            f"<summary><b>{escape(call.label or 'chamada')}</b> <span class='muted'>· {escape(' · '.join(meta))}</span>"
            f"</summary><div class='answers'>{answers}</div>"
            + _requests(call)
            + f"<details class='raw'><summary>Response JSON</summary><pre>{_json(response_json)}</pre></details>"
            "</details>"
        )


# ---------- answers ----------

def _answer(key: str, answer: Any) -> str:
    if isinstance(answer, ChoiceAnswer):
        rows = sorted(answer.probabilities.items(), key=lambda item: item[1], reverse=True)
        head = f"choice → <b>{escape(answer.choice)}</b> · confiança {_num(answer.confidence)}"
        bars = "".join(_bar(option, p, chosen=option == answer.choice) for option, p in rows)
    elif isinstance(answer, ScoreAnswer):
        top = len(answer.legend) - 1
        nearest = str(min(round(answer.score), top))
        head = f"score → <b>{_num(answer.score)}</b> de 0 a {top} · confiança {_num(answer.confidence)}"
        bars = "".join(_bar(f"{level} · {answer.legend.get(level, '')}", p, chosen=level == nearest)
                       for level, p in sorted(answer.probabilities.items(), key=lambda item: int(item[0])))
    elif isinstance(answer, NoulAnswer):
        head = f"noul → <b>{_num(answer.noul)}</b> <span class='muted'>(0 = não, 1 = sim)</span>"
        bars = _bar("sim", answer.noul, chosen=answer.noul >= 0.5)
    else:
        head, bars = "", f"<pre>{_json(answer)}</pre>"
    return f"<div class='answer'><p><code>{escape(key)}</code> {head}</p><div class='bars'>{bars}</div></div>"


def _bar(label: str, probability: float, chosen: bool) -> str:
    width = max(0.0, min(probability, 1.0)) * 100
    return (
        f"<div class='bar{' chosen' if chosen else ''}' title='{escape(label)}: {_num(probability)}'>"
        f"<span class='bar-label'>{escape(label)}</span>"
        f"<span class='bar-track'><span class='bar-fill' style='width:{width:.1f}%'></span></span>"
        f"<span class='bar-value'>{_num(probability)}</span></div>"
    )


# ---------- helpers ----------

def _requests(call: Call) -> str:
    """Bodies POSTed to the provider. Laya's can differ from the Jev-shaped request built by the example."""
    if not call.sent or call.sent == [call.request]:
        return _raw("Request JSON", call.request)
    built = _raw("Request montado pelo exemplo", call.request)
    sent = "".join(_raw(f"Request enviado {i} de {len(call.sent)} ao provider", body)
                   for i, body in enumerate(call.sent, start=1))
    return built + sent


def _raw(title: str, data: Any) -> str:
    return f"<details class='raw'><summary>{escape(title)}</summary><pre>{_json(_truncated(data))}</pre></details>"


def _truncated(data: Any) -> Any:
    """Copy of `data` with strings longer than the limit cut down, for display only."""
    if isinstance(data, str) and len(data) > _TRUNCATE_AT:
        return f"{data[:_TRUNCATE_AT]}… [+{len(data) - _TRUNCATE_AT} caracteres]"
    if isinstance(data, dict):
        return {key: _truncated(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_truncated(item) for item in data]
    return data


def _cases(example: ExampleResult, bonus: bool) -> list[Case]:
    return [case for scenario in example.scenarios if scenario.bonus == bonus for case in scenario.cases]


def _calls(example: ExampleResult) -> list[Call]:
    return [call for scenario in example.scenarios for case in scenario.cases for call in case.calls]


def _tally(cases) -> tuple[int, int]:
    judged = [case for case in cases if case.passed is not None]
    return sum(1 for case in judged if case.passed), len(judged)


def _dropped(call: Call) -> int:
    extra = (call.response.usage.model_extra or {}) if call.response else {}
    dropped = extra.get("state_tokens_dropped") or 0
    return int(dropped) if dropped else (1 if extra.get("truncated") else 0)


def _pct(tally: tuple[int, int]) -> str:
    passed, judged = tally
    return f"{passed / judged:.0%}" if judged else "—"


def _meter(tally: tuple[int, int]) -> str:
    passed, judged = tally
    if not judged:
        return "<span class='muted'>—</span>"
    ratio = passed / judged
    return (f"<span class='meter' title='{passed} de {judged}'><span class='meter-track'>"
            f"<span class='meter-fill' style='width:{ratio * 100:.1f}%'></span></span>"
            f"<span class='meter-text'>{passed}/{judged}</span></span>")


def _chip(kind: str, icon: str, label: str) -> str:
    return f"<span class='chip {kind}'><span aria-hidden='true'>{icon}</span> {escape(label)}</span>"


def _details_table(details: dict[str, Any]) -> str:
    rows = []
    for key, value in details.items():
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            rows.append(f"<tr><th>{escape(str(key))}</th><td>{_records(value)}</td></tr>")
        else:
            rows.append(f"<tr><th>{escape(str(key))}</th><td>{_value(value)}</td></tr>")
    return "<div class='scroll'><table class='kv'>" + "".join(rows) + "</table></div>"


def _records(records: list[dict]) -> str:
    columns = list(dict.fromkeys(column for record in records for column in record))
    head = "".join(f"<th>{escape(str(column))}</th>" for column in columns)
    body = "".join("<tr>" + "".join(f"<td>{_value(record.get(column, ''))}</td>" for column in columns) + "</tr>"
                   for record in records)
    return f"<div class='scroll'><table class='grid compact'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, (int, float)):
        return _num(value)
    if isinstance(value, dict):
        return " · ".join(f"{escape(str(key))}: {_value(item)}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(_value(item) for item in value)
    return escape(str(value))


def _num(value: float | int) -> str:
    if isinstance(value, int) or float(value).is_integer() and abs(value) >= 1000:
        return f"{int(value):,}".replace(",", ".")
    text = f"{value:,.3f}".rstrip("0").rstrip(".") if abs(value) < 100 else f"{value:,.0f}"
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


def _compact(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f} mi".replace(".", ",")
    if value >= 10_000:
        return f"{value / 1000:.1f} mil".replace(".", ",")
    return _num(value)


def _json(data: Any) -> str:
    return escape(json.dumps(data, ensure_ascii=False, indent=2, default=str))


_CSS = """
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink-2:#52514e;--muted:#898781;
--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);--accent:#2a78d6;--accent-soft:#cde2fb;--accent-dim:#86b6ef;
--good:#0ca30c;--good-ink:#006300;--warning:#fab219;--serious:#ec835a;--critical:#d03b3b;--code:#f0efec}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--page:#0d0d0d;
--surface:#1a1a19;--ink:#f0efec;--ink-2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);
--accent:#3987e5;--accent-soft:#184f95;--accent-dim:#256abf;--good-ink:#0ca30c;--code:#262624}}
:root[data-theme="dark"]{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink-2:#c3c2b7;
--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--accent:#3987e5;--accent-soft:#184f95;
--accent-dim:#256abf;--good-ink:#0ca30c;--code:#262624}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
.page{max-width:1180px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:28px;line-height:1.2;margin:4px 0 8px;font-weight:650}
h2{font-size:20px;margin:0 0 8px;font-weight:650}
h3{font-size:16px;margin:24px 0 4px;font-weight:600;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
h4{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:16px 0 6px}
a{color:var(--accent)}code{font:12px ui-monospace,SFMono-Regular,Menlo,monospace}
.eyebrow{margin:0;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.meta,.lead{color:var(--ink-2);margin:0 0 8px}.muted{color:var(--muted);font-weight:400}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:24px 0}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:14px 16px}
.tile-label{margin:0;color:var(--ink-2);font-size:13px}.tile-value{margin:2px 0;font-size:30px;font-weight:600}
.tile-sub{margin:0;color:var(--muted);font-size:12px}
.toolbar{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;display:flex;flex-wrap:wrap;gap:8px;
justify-content:space-between;padding:10px 0;background:var(--page)}
.seg{display:flex;flex-wrap:wrap;gap:4px}
.seg button{font:inherit;font-size:13px;color:var(--ink);background:var(--surface);border:1px solid var(--ring);
border-radius:999px;padding:5px 12px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--ink);color:var(--page);border-color:var(--ink)}
.block,.example{background:var(--surface);border:1px solid var(--ring);border-radius:14px;padding:20px;margin:16px 0}
.example{scroll-margin-top:64px}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%}
.grid th,.grid td{padding:8px 10px;border-bottom:1px solid var(--grid);text-align:left;vertical-align:top}
.grid th{font-size:12px;color:var(--muted);font-weight:500;white-space:nowrap}
.grid.compact th,.grid.compact td{padding:4px 8px;font-size:12px}
.grid.wide{min-width:760px}
.num{text-align:right!important;font-variant-numeric:tabular-nums;white-space:nowrap}
.kv th{width:30%;text-align:left;color:var(--ink-2);font-weight:500;padding:4px 12px 4px 0;vertical-align:top;font-size:13px}
.kv td{padding:4px 0;font-size:13px;font-variant-numeric:tabular-nums}
.meter{display:inline-flex;align-items:center;gap:8px;min-width:130px}
.meter-track{flex:1;height:8px;border-radius:4px;background:var(--accent-soft);overflow:hidden;min-width:70px}
.meter-fill{display:block;height:100%;background:var(--accent);border-radius:4px}
.meter-text{font-variant-numeric:tabular-nums;font-size:12px;color:var(--ink-2)}
.badge{font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--ink);
border:1px solid var(--serious);border-radius:999px;padding:1px 8px}
.stress{margin:4px 0 8px;color:var(--ink-2)}
.metrics{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 12px}
.metrics div{background:var(--page);border:1px solid var(--ring);border-radius:8px;padding:6px 10px}
.metrics dt{font-size:11px;color:var(--muted)}.metrics dd{margin:0;font-size:13px;font-weight:500}
.chip{display:inline-flex;gap:4px;align-items:center;font-size:12px;font-weight:600;border-radius:999px;
padding:1px 8px;border:1px solid currentColor;white-space:nowrap}
.chip.good{color:var(--good-ink)}.chip.critical{color:var(--critical)}.chip.serious{color:var(--serious)}
.chip.neutral{color:var(--muted)}
.warn{color:var(--ink-2);font-weight:500}.warn::first-letter{color:var(--warning)}
.case{border:1px solid var(--ring);border-radius:10px;margin:8px 0;background:var(--surface)}
.case>summary{display:grid;grid-template-columns:110px minmax(140px,1.1fr) minmax(160px,1.6fr) minmax(120px,1fr);
gap:12px;align-items:start;padding:10px 12px;cursor:pointer;list-style:none}
.case>summary::-webkit-details-marker{display:none}
.case[open]>summary{border-bottom:1px solid var(--grid)}
.case-label{font-weight:500}.case-meta{color:var(--muted);font-size:12px;text-align:right}
.case-body{padding:4px 16px 16px}
.input{white-space:pre-wrap;background:var(--page);border-radius:8px;padding:10px 12px;margin:0;color:var(--ink-2)}
.call{border-left:2px solid var(--grid);padding:4px 0 4px 12px;margin:8px 0}
.call>summary{cursor:pointer}
.answers{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin:8px 0}
.answer p{margin:0 0 6px;font-size:13px}
.bars{display:grid;gap:3px}
.bar{display:grid;grid-template-columns:minmax(90px,1.4fr) 2fr 48px;gap:8px;align-items:center;font-size:12px}
.bar-label{color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar.chosen .bar-label{color:var(--ink);font-weight:600}
.bar-track{height:8px;background:var(--accent-soft);border-radius:4px;overflow:hidden}
.bar-fill{display:block;height:100%;background:var(--accent-dim);border-radius:4px}
.bar.chosen .bar-fill{background:var(--accent)}
.bar-value{text-align:right;font-variant-numeric:tabular-nums;color:var(--ink-2)}
.raw summary{cursor:pointer;color:var(--muted);font-size:12px;margin-top:4px}
pre{background:var(--code);border-radius:8px;padding:10px 12px;overflow-x:auto;font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;
max-height:420px;margin:6px 0}
.alert{border:1px solid var(--critical);border-radius:8px;padding:8px 12px;margin:8px 0}
.hidden-by-filter{display:none!important}
@media (max-width:720px){.case>summary{grid-template-columns:1fr}.case-meta{text-align:left}.kv th{width:40%}}
"""

_JS = """
(function(){
  var buttons = document.querySelectorAll('[data-filter]');
  function apply(filter){
    buttons.forEach(function(b){ b.setAttribute('aria-pressed', String(b.dataset.filter === filter)); });
    document.querySelectorAll('.case').forEach(function(c){
      var show = filter === 'all' || (filter === 'failed' && c.dataset.state === 'failed')
        || (filter === 'bonus' && c.dataset.bonus === 'true');
      c.classList.toggle('hidden-by-filter', !show);
    });
    document.querySelectorAll('.scenario').forEach(function(s){
      s.classList.toggle('hidden-by-filter', !s.querySelector('.case:not(.hidden-by-filter)'));
    });
    document.querySelectorAll('.example').forEach(function(e){
      e.classList.toggle('hidden-by-filter', filter !== 'all' && !e.querySelector('.scenario:not(.hidden-by-filter)'));
    });
  }
  buttons.forEach(function(b){ b.addEventListener('click', function(){ apply(b.dataset.filter); }); });
  document.querySelectorAll('[data-expand]').forEach(function(b){
    b.addEventListener('click', function(){
      var open = b.dataset.expand === 'open';
      document.querySelectorAll('.case:not(.hidden-by-filter)').forEach(function(c){ c.open = open; });
    });
  });
})();
"""

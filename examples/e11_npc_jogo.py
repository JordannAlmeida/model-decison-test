"""11. Tomada de decisão em jogos (lógica de NPCs).

A cada turno, o modelo de decisão recebe o estado da partida e escolhe a próxima ação do NPC
entre opções fixas (Choice). Uma partida é simulada em rodadas: a ação escolhida altera o
estado da rodada seguinte. O gabarito de cada turno vem de uma árvore de comportamento simples,
como a que um game designer escreveria à mão.
"""

import copy

from examples.base import Example, ranked
from execution.results import Case, Scenario
from modelDecision.scheme import ChoiceQuestion, Type

MAX_ROUNDS = 8

QUESTIONS = {
    "acao": ChoiceQuestion(
        type=Type.CHOICE,
        instructions={
            "pergunta": "Qual deve ser a próxima ação do `npc` neste turno?",
            "foco": "Considere a vida, a munição, os kits médicos e a cobertura do `npc`, a situação do "
                    "`jogador` e a `personalidade` do NPC, se houver.",
        },
        criteria={
            "atacar": "Atirar no jogador: faz sentido com vida e munição suficientes, ou quando o jogador está "
                      "muito fraco",
            "recuar": "Fugir para longe do jogador: faz sentido sem munição, ou em grande desvantagem sem como se curar",
            "buscar_cobertura": "Correr para trás de uma cobertura: faz sentido quando está ferido, sob fogo e "
                                "fora da cobertura",
            "curar_se": "Usar um kit médico: faz sentido com vida baixa, tendo kit, estando protegido ou fora de perigo",
        },
    ),
}


def reference_action(state: dict) -> str:
    """Hand-written behaviour tree used as the expected answer."""
    npc, player = state["npc"], state["jogador"]
    if player["vida_pct"] <= 15 and npc["municao"] > 0:
        return "atacar"
    if npc["vida_pct"] <= 30:
        if player["atirando"] and not npc["em_cobertura"]:
            return "buscar_cobertura"
        return "curar_se" if npc["kits_medicos"] > 0 else "recuar"
    if npc["municao"] == 0:
        return "recuar"
    if player["atirando"] and not npc["em_cobertura"] and npc["vida_pct"] <= 60:
        return "buscar_cobertura"
    return "atacar"


def _state(npc_life: int, ammo: int, kits: int, in_cover: bool, player_life: int, distance: int,
           shooting: bool, events: list[str] | None = None, personality: str | None = None) -> dict:
    npc = {"vida_pct": npc_life, "municao": ammo, "kits_medicos": kits, "em_cobertura": in_cover}
    if personality:
        npc["personalidade"] = personality
    return {
        "npc": npc,
        "jogador": {"vida_pct": player_life, "distancia_m": distance, "atirando": shooting, "arma": "fuzil"},
        "ambiente": {"cobertura_proxima": True, "distancia_ate_cobertura_m": 3},
        "eventos_recentes": events or [],
    }


SNAPSHOTS = [
    ("Saudável, jogador exposto", _state(100, 6, 1, False, 100, 15, False)),
    ("Ferido e sob fogo, fora da cobertura", _state(20, 4, 1, False, 90, 12, True)),
    ("Ferido, protegido, jogador recarregando", _state(25, 4, 1, True, 80, 20, False)),
    ("Sem munição", _state(70, 0, 0, False, 90, 10, True)),
    ("Jogador quase morto", _state(90, 6, 1, False, 10, 8, True)),
]

SITUATION = dict(npc_life=20, ammo=4, kits=0, in_cover=False, player_life=60, distance=10, shooting=True)
PERSONALITY_CASES = [
    ("Personalidade covarde", _state(**SITUATION, personality="covarde: prioriza sobreviver acima de tudo"),
     {"recuar", "buscar_cobertura"}),
    ("Personalidade kamikaze", _state(**SITUATION, personality="kamikaze: ataca sempre, mesmo à beira da morte"),
     {"atacar"}),
    ("Quase morto contra jogador quase morto", _state(15, 3, 0, False, 5, 2, False,
                                                      ["Jogador ficou sem munição"]), {"atacar"}),
    ("Sem munição, sem kits, sob fogo", _state(10, 0, 0, False, 100, 10, True), {"recuar", "buscar_cobertura"}),
]

SCENE_ITEMS = ["caixa de madeira", "barril explosivo", "carro abandonado", "poste", "árvore", "muro baixo",
               "aliado ferido", "inimigo patrulhando", "porta trancada", "janela quebrada"]


class NpcDecisionExample(Example):
    number = 11
    slug = "npc-jogo"
    title = "Tomada de decisão em jogos (lógica de NPCs)"
    summary = ("Serve como motor de decisão de um NPC num jogo de ação: a cada turno, lê o estado da partida e "
               "escolhe entre atacar, recuar, buscar cobertura ou curar-se.")

    def scenarios(self) -> list[Scenario]:
        snapshots = [self._decide(label, state, {reference_action(state)}) for label, state in SNAPSHOTS]
        match = self._match()
        npc_life = match[-1].details.get("vida do NPC depois do turno") if match else None
        return [
            Scenario(
                title="Situações isoladas",
                description="Estados de jogo com uma ação claramente melhor segundo a árvore de comportamento.",
                cases=snapshots,
                metrics=_agreement(snapshots),
            ),
            Scenario(
                title=f"Partida simulada em até {MAX_ROUNDS} rodadas",
                description="A ação escolhida pelo modelo muda o estado do turno seguinte; o jogador atira em dois "
                            "de cada três turnos.",
                cases=match,
                metrics={**_agreement(match), "rodadas jogadas": len(match), "vida final do NPC": npc_life},
            ),
        ]

    def bonus_scenarios(self) -> list[Scenario]:
        personality = [self._decide(label, state, accepted) for label, state, accepted in PERSONALITY_CASES]
        critical = _state(15, 4, 1, False, 90, 12, True, ["Jogador acertou o NPC duas vezes seguidas"])
        scene = [{"id": index, "objeto": SCENE_ITEMS[index % len(SCENE_ITEMS)],
                  "posicao": {"x": (index * 37) % 100, "y": (index * 53) % 100}, "visivel": index % 3 != 0}
                 for index in range(60)]
        crowded = [
            self._decide("Cena com 60 objetos antes do estado do NPC", {"cena": scene, **critical},
                         {reference_action(critical)}),
            self._decide("Mesmo estado, com o NPC antes da cena", {**critical, "cena": scene},
                         {reference_action(critical)}),
        ]
        return [
            Scenario(
                title="Personalidade e conflitos de prioridade",
                description="A mesma situação com personalidades opostas e situações em que duas regras competem.",
                bonus=True,
                stress="Usar um campo de contexto (personalidade) para mudar a decisão em um estado idêntico.",
                cases=personality,
                metrics=_agreement(personality, reference="o gabarito por personalidade"),
            ),
            Scenario(
                title="Cena lotada",
                description="O estado do NPC (vida 15%, sob fogo, fora da cobertura) acompanhado de 60 objetos de "
                            "cenário, antes e depois deles.",
                bonus=True,
                stress="State grande: a informação crítica pode ficar fora do contexto conforme a ordem dos campos.",
                cases=crowded,
                metrics=_agreement(crowded),
            ),
        ]

    def _decide(self, label: str, state: dict, accepted: set[str]) -> Case:
        expected = " ou ".join(sorted(accepted))
        npc, player = state["npc"], state["jogador"]
        summary = (f"NPC: vida {npc['vida_pct']}%, munição {npc['municao']}, kits {npc['kits_medicos']}, "
                   f"{'em cobertura' if npc['em_cobertura'] else 'exposto'}"
                   f"{', ' + npc['personalidade'] if 'personalidade' in npc else ''} · "
                   f"Jogador: vida {player['vida_pct']}%, a {player['distancia_m']} m, "
                   f"{'atirando' if player['atirando'] else 'sem atirar'}")
        call = self._ask(state, QUESTIONS, label)
        if call.failed:
            return Case.from_failure(label, [call], expected, summary)
        options = ranked(call.choice("acao"))
        action = options[0][0]
        return Case(
            label=label,
            input_summary=summary,
            calls=[call],
            outcome=action,
            expected=expected,
            passed=action in accepted,
            details={"probabilidades": ", ".join(f"{option} {p:.2f}" for option, p in options)},
        )

    def _match(self) -> list[Case]:
        state = _state(100, 5, 1, False, 100, 18, True, ["O jogador apareceu no fim do corredor e abriu fogo"])
        cases = []
        for round_number in range(1, MAX_ROUNDS + 1):
            case = self._decide(f"Rodada {round_number}", copy.deepcopy(state), {reference_action(state)})
            cases.append(case)
            if case.error:
                break
            state = _apply(state, case.outcome, round_number)
            case.details["vida do NPC depois do turno"] = state["npc"]["vida_pct"]
            case.details["vida do jogador depois do turno"] = state["jogador"]["vida_pct"]
            case.details["eventos do turno"] = " · ".join(state["eventos_recentes"])
            if state["npc"]["vida_pct"] == 0 or state["jogador"]["vida_pct"] == 0:
                break
        return cases


def _apply(state: dict, action: str, round_number: int) -> dict:
    """Deterministic game rules: the NPC acts, then the player (who reloads every third turn)."""
    state = copy.deepcopy(state)
    npc, player = state["npc"], state["jogador"]
    events = []
    if action == "atacar":
        if npc["municao"] > 0:
            npc["municao"] -= 1
            player["vida_pct"] = max(0, player["vida_pct"] - 20)
            events.append("NPC atirou e acertou o jogador (-20)")
        else:
            events.append("NPC tentou atirar sem munição")
    elif action == "recuar":
        player["distancia_m"] += 15
        npc["em_cobertura"] = False
        events.append("NPC recuou 15 m")
    elif action == "buscar_cobertura":
        npc["em_cobertura"] = True
        events.append("NPC se protegeu atrás da cobertura")
    elif action == "curar_se":
        if npc["kits_medicos"] > 0:
            npc["kits_medicos"] -= 1
            npc["vida_pct"] = min(100, npc["vida_pct"] + 40)
            events.append("NPC usou um kit médico (+40)")
        else:
            events.append("NPC tentou se curar sem kit")

    player["atirando"] = round_number % 3 != 0
    if player["vida_pct"] > 0 and player["atirando"]:
        damage = 8 if npc["em_cobertura"] else 25
        if player["distancia_m"] > 30:
            damage //= 2
        npc["vida_pct"] = max(0, npc["vida_pct"] - damage)
        events.append(f"Jogador atirou no NPC (-{damage})")
    elif player["vida_pct"] > 0:
        events.append("Jogador está recarregando")
    state["eventos_recentes"] = events
    return state


def _agreement(cases: list[Case], reference: str = "a árvore de comportamento") -> dict:
    judged = [case for case in cases if case.passed is not None]
    if not judged:
        return {}
    agreed = sum(1 for case in judged if case.passed)
    return {f"concordância com {reference}": f"{agreed}/{len(judged)}"}

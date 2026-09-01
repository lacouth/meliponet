"""Modelo fisico das series geradas.

O simulador nao produz ruido: produz series com a forma das reais, porque e contra
elas que os graficos, as regras de alerta e as rotinas de curadoria serao ajustados. Um
gerador aleatorio validaria o encanamento e nada mais.

As formas vem da literatura citada nas propostas:

* A colonia de *Melipona* mantem a regiao de cria proxima de 30 C, com termogenese das
  crias elevando a temperatura alguns graus acima do entorno, e se comporta de modo
  heterotermico em vez de manter homeostase estrita (Roldao-Sbordoni et al., 2024).
* A temperatura externa do semiarido tem amplitude diaria larga, bem maior que a
  interna -- e desse contraste que sai o diferencial termico, a estimativa de esforco
  termorregulatorio.
* O peso sobe durante o dia com a entrada de recursos e cai em degrau nas colheitas.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime

#: Temperatura de cria alvo, em graus Celsius.
BROOD_TARGET_C = 30.0


@dataclass(slots=True)
class HiveSimulator:
    """Estado de uma colmeia simulada."""

    node_id: str
    name: str
    species: str
    #: Peso base, em kg. Cresce lentamente com a colonia.
    weight_kg: float = 12.0
    #: Deslocamento individual da temperatura de cria: colonias nao sao identicas.
    brood_offset_c: float = 0.0
    seq: int = 0
    battery_v: float = 4.1
    rng: random.Random | None = None

    def __post_init__(self) -> None:
        if self.rng is None:
            # Semente derivada do node_id: a mesma colmeia gera sempre a mesma serie,
            # o que torna um bug reproduzivel em vez de intermitente.
            self.rng = random.Random(self.node_id)
        if self.brood_offset_c == 0.0:
            self.brood_offset_c = self.rng.uniform(-0.8, 0.8)

    def _hour(self, when: datetime) -> float:
        return when.hour + when.minute / 60 + when.second / 3600

    def outside_temp_c(self, when: datetime) -> float:
        """Ciclo diario do semiarido: minimo por volta das 5h, maximo por volta das 15h."""
        hour = self._hour(when)
        mean, amplitude = 28.0, 7.0
        return mean + amplitude * math.sin((hour - 9.0) * math.pi / 12) + self.rng.gauss(0, 0.3)

    def outside_rh_pct(self, when: datetime) -> float:
        """Umidade externa e aproximadamente o espelho da temperatura."""
        hour = self._hour(when)
        value = 62.0 - 22.0 * math.sin((hour - 9.0) * math.pi / 12) + self.rng.gauss(0, 1.5)
        return min(100.0, max(5.0, value))

    def inside_temp_c(self, when: datetime, outside: float) -> float:
        """Cria termorregulada, com acoplamento parcial ao ambiente.

        O acoplamento nao e zero: a colonia e heterotermica, nao um termostato. Quando
        o ambiente esquenta muito, parte disso atravessa -- e e exatamente esse
        vazamento que o monitoramento continuo se propoe a medir.
        """
        target = BROOD_TARGET_C + self.brood_offset_c
        coupling = 0.12 if outside < target else 0.22
        return target + coupling * (outside - target) + self.rng.gauss(0, 0.15)

    def inside_rh_pct(self, when: datetime) -> float:
        hour = self._hour(when)
        value = 70.0 + 4.0 * math.sin((hour - 3.0) * math.pi / 12) + self.rng.gauss(0, 0.8)
        return min(100.0, max(5.0, value))

    def step_weight_kg(self, when: datetime) -> float:
        """Ganho durante o forrageio diurno, perda leve a noite, e degraus de colheita."""
        hour = self._hour(when)
        if 6 <= hour <= 17:
            self.weight_kg += self.rng.uniform(0.0005, 0.0035)
        else:
            self.weight_kg -= self.rng.uniform(0.0, 0.0008)

        # Colheita ocasional: um degrau abrupto para baixo, que e o padrao que a regra
        # de alerta de "queda abrupta de peso" precisa distinguir de uma enxameacao.
        if self.rng.random() < 0.0006:
            self.weight_kg = max(8.0, self.weight_kg - self.rng.uniform(0.8, 2.0))

        return self.weight_kg

    def step_battery_v(self, when: datetime) -> float:
        """Descarga lenta com recarga solar durante o dia."""
        hour = self._hour(when)
        if 8 <= hour <= 16:
            self.battery_v = min(4.15, self.battery_v + 0.004)
        else:
            self.battery_v -= 0.002
        self.battery_v = max(3.2, self.battery_v)
        return self.battery_v

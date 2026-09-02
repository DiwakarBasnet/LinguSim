import json
import logging
from functools import lru_cache
from pathlib import Path

from app.models.scenario import Scenario

logger = logging.getLogger(__name__)

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "data" / "scenarios"


class ScenarioNotFoundError(KeyError):
    pass


class ScenarioLoader:
    """Loads scenario definitions from JSON files. Scenarios are data, not hard-coded prompts."""

    def __init__(self, scenarios_dir: Path = SCENARIOS_DIR):
        self._scenarios_dir = scenarios_dir
        self._scenarios: dict[str, Scenario] | None = None

    def _load(self) -> dict[str, Scenario]:
        scenarios: dict[str, Scenario] = {}
        for path in sorted(self._scenarios_dir.glob("*.json")):
            data = json.loads(path.read_text())
            scenario = Scenario.model_validate(data)
            if scenario.id in scenarios:
                raise ValueError(f"Duplicate scenario id '{scenario.id}' in {path}")
            scenarios[scenario.id] = scenario
        logger.info("loaded_scenarios", extra={"context": {"count": len(scenarios)}})
        return scenarios

    @property
    def scenarios(self) -> dict[str, Scenario]:
        if self._scenarios is None:
            self._scenarios = self._load()
        return self._scenarios

    def list(self) -> list[Scenario]:
        return list(self.scenarios.values())

    def get(self, scenario_id: str) -> Scenario:
        try:
            return self.scenarios[scenario_id]
        except KeyError:
            raise ScenarioNotFoundError(scenario_id) from None


@lru_cache
def get_scenario_loader() -> ScenarioLoader:
    return ScenarioLoader()

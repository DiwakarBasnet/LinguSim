from fastapi import APIRouter, Depends, HTTPException

from app.models.scenario import Scenario
from app.services.scenario_loader import ScenarioLoader, ScenarioNotFoundError, get_scenario_loader

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=list[Scenario])
async def list_scenarios(loader: ScenarioLoader = Depends(get_scenario_loader)) -> list[Scenario]:
    return loader.list()


@router.get("/{scenario_id}", response_model=Scenario)
async def get_scenario(
    scenario_id: str, loader: ScenarioLoader = Depends(get_scenario_loader)
) -> Scenario:
    try:
        return loader.get(scenario_id)
    except ScenarioNotFoundError:
        raise HTTPException(status_code=404, detail=f"Unknown scenario_id '{scenario_id}'") from None

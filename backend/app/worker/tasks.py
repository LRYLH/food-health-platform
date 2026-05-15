from ..services.analyze_service import run_development_analysis


def analyze_food_package(task_id: str) -> None:
    run_development_analysis(task_id)

from pathlib import Path

import yaml


CONFIG_PATH = (
    Path(__file__).resolve().parent.parent
    / "config"
    / "semantic_layer.yaml"
)


class SemanticLayerService:

    def __init__(self):
        with open(CONFIG_PATH, "r", encoding="utf-8") as file:
            self.config = yaml.safe_load(file)

    def get_domain(self) -> dict:
        return self.config["domain"]

    def get_data_availability(self) -> dict:
        return self.config["data_availability"]

    def get_tables(self) -> dict:
        return self.config["tables"]

    def get_metrics(self) -> dict:
        return self.config["metrics"]

    def get_dimensions(self) -> dict:
        return self.config["dimensions"]

    def get_relationships(self) -> dict:
        return self.config["relationships"]

    def get_metric(self, metric_name: str) -> dict | None:
        return self.config["metrics"].get(metric_name)

    def get_dimension(self, dimension_name: str) -> dict | None:
        return self.config["dimensions"].get(dimension_name)


semantic_layer_service = SemanticLayerService()
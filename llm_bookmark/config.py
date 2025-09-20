import yaml
from pathlib import Path
import logging

LOGGER = logging.getLogger(__name__)


class Config:
    def __init__(self, conf_path):
        with open(conf_path, 'rt', encoding='utf-8') as f:
            self.conf = yaml.safe_load(f)

    def get_conf(self):
        return self.conf


conf_path = Path(__file__).parent.parent / "conf.yaml"
conf = Config(conf_path)
LOGGER.info("load conf, conf_path: %s, values: %s", conf_path, conf)
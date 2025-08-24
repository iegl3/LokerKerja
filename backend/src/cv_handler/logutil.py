import json, logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
def jlog(**kv): logging.info(json.dumps(kv, ensure_ascii=False))
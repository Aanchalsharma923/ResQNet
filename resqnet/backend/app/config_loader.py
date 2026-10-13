import os
import re
import json
from typing import Dict, Tuple, Any

def expand_env_vars(text: str) -> str:
    """
    Expands environment variables in text supporting ${VAR:-default}, ${VAR}, and $VAR syntax.
    Falls back to default if variable is not set or empty.
    """
    def replacer(match):
        var_name = match.group(1) or match.group(3)
        default_val = match.group(2) if match.group(2) is not None else ""
        val = os.environ.get(var_name)
        return val if val else default_val

    pattern = re.compile(r'\$\{([A-Za-z0-9_]+)(?::-?([^}]*))?\}|\$([A-Za-z0-9_]+)')
    return pattern.sub(replacer, text)

def load_node_endpoints(config_path: str) -> Dict[str, Tuple[str, int]]:
    """
    Loads node endpoints from a JSON configuration file, expanding environment variables.
    Returns mapping: {node_id: (host, port)}
    """
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    expanded = expand_env_vars(content)
    raw = json.loads(expanded)
    nodes = raw.get("nodes", raw)
    return {
        k: (v["host"], int(v["port"]))
        for k, v in nodes.items()
        if isinstance(v, dict) and "host" in v and "port" in v
    }

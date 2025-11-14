import os
import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: str = "src/config/settings.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Replace env vars in config
    api_key_env = config['gemini']['api_key_env']
    config['gemini']['api_key'] = os.getenv(api_key_env, "")
    
    if not config['gemini']['api_key']:
        raise ValueError(f"Missing environment variable: {api_key_env}")
    
    return config

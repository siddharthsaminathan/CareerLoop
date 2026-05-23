import os
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger("careerloop.session.user_registry")

class UserRegistry:
    def __init__(self, registry_path: Optional[str] = None):
        self.registry_path = registry_path or "/Users/siddharthsaminathan/projects/CareerLoop/careerloop/data/user_registry.json"
        
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        
        self.mappings = self._load_mappings()

    def _load_mappings(self) -> Dict[str, Dict[str, str]]:
        if not os.path.exists(self.registry_path):
            # Create an empty registry if missing
            self._save_mappings({})
            return {}
        
        try:
            with open(self.registry_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read user registry file: {e}")
            return {}

    def _save_mappings(self, data: Dict[str, Dict[str, str]]):
        try:
            with open(self.registry_path, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to write user registry file: {e}")

    def register_user(self, user_id: str, person_id: str, cv_path: str) -> bool:
        """Saves a mapping from user_id (Telegram ID) to persona details."""
        try:
            self.mappings[user_id] = {
                "person_id": person_id,
                "cv_path": cv_path
            }
            self._save_mappings(self.mappings)
            logger.info(f"Registered user {user_id} with person_id {person_id} and CV {cv_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to register user {user_id}: {e}")
            return False

    def get_user_mapping(self, user_id: str) -> Optional[Dict[str, str]]:
        """Returns the mapping for a user: {'person_id': ..., 'cv_path': ...} or None."""
        return self.mappings.get(user_id)

    def is_registered(self, user_id: str) -> bool:
        return user_id in self.mappings

    def get_all_users(self) -> Dict[str, Dict[str, str]]:
        return self.mappings

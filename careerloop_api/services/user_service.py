"""User service — profile + preferences."""

from careerloop_api.core.envelope import APIError
from careerloop_api.repositories.users_repo import UsersRepo
from careerloop_api.services import serializers


class UserService:
    def __init__(self, db):
        self.db = db
        self.repo = UsersRepo(db)

    def me(self, user_id: str) -> dict:
        row = self.repo.get_by_id(user_id)
        if not row:
            # If the row is not found, it means provisioning failed or was skipped.
            # Raise an APIError so that the client doesn't load a broken stub session.
            raise APIError(
                "User profile not found. Please try logging in again.",
                status_code=404,
                code="not_found",
            )
        return serializers.user_public(row)

    def preferences(self, user_id: str) -> dict:
        return self.repo.get_preferences(user_id)

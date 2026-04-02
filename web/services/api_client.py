from __future__ import annotations

import json
from typing import Any

import requests

from config import API_BASE_URL
from project_config import SETTINGS


class ApiClient:
    def __init__(
        self,
        base_url: str = API_BASE_URL,
        timeout: int | None = None,
        chat_timeout: int | None = None,
        upload_timeout: int | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout or getattr(SETTINGS, "request_timeout_seconds", 30)
        self.chat_timeout = chat_timeout or getattr(SETTINGS, "chat_timeout_seconds", 300)
        self.upload_timeout = upload_timeout or getattr(SETTINGS, "upload_timeout_seconds", 120)

    def register(self, username: str, email: str, password: str) -> dict[str, Any]:
        return self._post(
            "/auth/register",
            {"username": username, "email": email, "password": password},
        )

    def login(self, username: str, password: str) -> dict[str, Any]:
        return self._post("/auth/login", {"username": username, "password": password})

    def get_profile(self) -> dict[str, Any]:
        return self._get("/auth/profile", auth=True)

    def change_password(
        self,
        username: str,
        old_password: str,
        new_password: str,
        confirm_password: str,
    ) -> dict[str, Any]:
        return self._post(
            "/auth/change-password",
            {
                "username": username,
                "old_password": old_password,
                "new_password": new_password,
                "confirm_password": confirm_password,
            },
            auth=True,
        )

    def upload_document(self, file_name: str, file_bytes: bytes) -> dict[str, Any]:
        files = {"file": (file_name, file_bytes)}
        return self._post(
            "/vector-store/upload",
            files=files,
            auth=True,
            timeout=self.upload_timeout,
        )

    def list_documents(self) -> list[dict[str, Any]]:
        return self._get("/vector-store/documents", auth=True)

    def chat(
        self,
        question: str,
        top_k: int,
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._post(
            "/chat/completion",
            {
                "question": question,
                "top_k": top_k,
                "history": history,
            },
            auth=True,
            timeout=self.chat_timeout,
        )

    def chat_stream(
        self,
        question: str,
        top_k: int,
        history: list[dict[str, Any]],
    ):
        try:
            response = requests.post(
                f"{self.base_url}/chat/completion/stream",
                json={
                    "question": question,
                    "top_k": top_k,
                    "history": history,
                },
                timeout=self.chat_timeout,
                headers=self._build_headers(auth=True),
                stream=True,
            )
        except requests.exceptions.ReadTimeout as exc:
            raise RuntimeError("Request timed out. Please retry or increase timeout.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError("Cannot connect to the backend service. Please confirm the API server is running and reachable.") from exc
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Request failed: {exc}") from exc

        if not response.ok:
            try:
                payload = response.json()
            except ValueError as exc:
                raise RuntimeError("Server response is not valid JSON") from exc
            detail = payload.get("detail", "Request failed")
            raise RuntimeError(str(detail))

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield payload

    def _get(self, path: str, auth: bool = False, timeout: int | None = None) -> Any:
        try:
            response = requests.get(
                f"{self.base_url}{path}",
                timeout=timeout or self.timeout,
                headers=self._build_headers(auth=auth),
            )
        except requests.exceptions.ReadTimeout as exc:
            raise RuntimeError("Request timed out. Please retry or increase timeout.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError("Cannot connect to the backend service. Please confirm the API server is running and reachable.") from exc
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Request failed: {exc}") from exc
        return self._handle_response(response)

    def _post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        auth: bool = False,
        timeout: int | None = None,
    ) -> Any:
        try:
            response = requests.post(
                f"{self.base_url}{path}",
                json=json,
                data=data,
                files=files,
                timeout=timeout or self.timeout,
                headers=self._build_headers(auth=auth),
            )
        except requests.exceptions.ReadTimeout as exc:
            raise RuntimeError("Request timed out. Please retry or increase timeout.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError("Cannot connect to the backend service. Please confirm the API server is running and reachable.") from exc
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Request failed: {exc}") from exc
        return self._handle_response(response)

    @staticmethod
    def _handle_response(response: requests.Response) -> Any:
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("Server response is not valid JSON") from exc

        if not response.ok:
            detail = payload.get("detail", "Request failed")
            if isinstance(detail, list):
                normalized_parts: list[str] = []
                for item in detail:
                    if isinstance(item, dict):
                        message = str(item.get("msg", "")).strip()
                        location = item.get("loc")
                        if isinstance(location, list) and location:
                            message = f"{'/'.join(str(part) for part in location)}: {message}" if message else '/'.join(str(part) for part in location)
                        if message:
                            normalized_parts.append(message)
                    elif item:
                        normalized_parts.append(str(item))
                detail = '; '.join(normalized_parts) or "Request failed"
            elif isinstance(detail, dict):
                detail = json.dumps(detail, ensure_ascii=False)
            raise RuntimeError(str(detail))
        return payload

    @staticmethod
    def _build_headers(auth: bool = False) -> dict[str, str]:
        if not auth:
            return {}

        try:
            import streamlit as st
        except ImportError:
            return {}

        token = st.session_state.get("token", "")
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}


api_client = ApiClient()

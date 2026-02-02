from abc import ABC, abstractmethod
from typing import Any

from backend.app.domains.generation.section_output_schemas import (
    LLMInvocationRequest,
    LLMInvocationResult,
)


class BaseLLMClient(ABC):
    @abstractmethod
    async def invoke(self, request: LLMInvocationRequest) -> LLMInvocationResult:
        pass


class MockLLMClient(BaseLLMClient):
    def __init__(
        self,
        default_response: str | None = None,
        failure_sections: list[int] | None = None,
        response_map: dict[int, str] | None = None,
    ):
        self._default_response = default_response or "Generated content for section."
        self._failure_sections = failure_sections or []
        self._response_map = response_map or {}
        self._invocation_count = 0
        self._invocations: list[LLMInvocationRequest] = []

    async def invoke(self, request: LLMInvocationRequest) -> LLMInvocationResult:
        self._invocation_count += 1
        self._invocations.append(request)

        if request.section_id in self._failure_sections:
            return LLMInvocationResult(
                generation_input_id=request.generation_input_id,
                section_id=request.section_id,
                raw_output="",
                is_successful=False,
                error_message=f"Simulated LLM failure for section {request.section_id}",
                invocation_metadata={
                    "invocation_number": self._invocation_count,
                    "simulated": True,
                },
            )

        response_text = self._response_map.get(request.section_id, self._default_response)

        return LLMInvocationResult(
            generation_input_id=request.generation_input_id,
            section_id=request.section_id,
            raw_output=response_text,
            is_successful=True,
            invocation_metadata={
                "invocation_number": self._invocation_count,
                "simulated": True,
                "prompt_length": len(request.prompt_text),
            },
        )

    @property
    def invocation_count(self) -> int:
        return self._invocation_count

    @property
    def invocations(self) -> list[LLMInvocationRequest]:
        return self._invocations.copy()

    def reset(self) -> None:
        self._invocation_count = 0
        self._invocations = []


class DeterministicLLMClient(BaseLLMClient):
    def __init__(self, response_generator: Any = None):
        self._response_generator = response_generator

    async def invoke(self, request: LLMInvocationRequest) -> LLMInvocationResult:
        if self._response_generator:
            response_text = self._response_generator(request)
        else:
            response_text = f"Deterministic content for section {request.section_id}"

        return LLMInvocationResult(
            generation_input_id=request.generation_input_id,
            section_id=request.section_id,
            raw_output=response_text,
            is_successful=True,
            invocation_metadata={"deterministic": True},
        )

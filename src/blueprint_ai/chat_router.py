from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict

from blueprint_ai.auth import User, require_chat_user
from blueprint_ai.forwarder import ChatForwarder, UpstreamUnavailableError
from blueprint_ai.upstreams import UpstreamRegistry

router = APIRouter(prefix="/api/v1")


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    stream: Literal[False] = False


def get_registry(request: Request) -> UpstreamRegistry:
    return request.app.state.registry


def get_forwarder(request: Request) -> ChatForwarder:
    return request.app.state.forwarder


@router.post("/providers/{provider_id}/chat/completions")
async def complete(
    provider_id: str,
    completion: ChatCompletionRequest,
    _: Annotated[User, Depends(require_chat_user)],
    registry: Annotated[UpstreamRegistry, Depends(get_registry)],
    forwarder: Annotated[ChatForwarder, Depends(get_forwarder)],
) -> Response:
    upstream = registry.find(provider_id)
    if upstream is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown provider '{provider_id}'.")
    if not upstream.allows(completion.model):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Model '{completion.model}' is not allowed for provider '{provider_id}'.",
        )
    try:
        reply = await forwarder.complete(upstream, completion.model_dump())
    except UpstreamUnavailableError as error:
        raise HTTPException(error.status_code, str(error)) from error
    return Response(content=reply.body, status_code=reply.status_code, media_type=reply.content_type)

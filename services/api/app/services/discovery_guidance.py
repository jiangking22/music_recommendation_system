import asyncio
import logging

import httpx

from app.agent.providers import LLMProvider
from app.agent.schemas import Answer
from app.api.schemas import DiscoveryRequest, DiscoveryResponse
from app.observability.events import emit


def local_guidance(result: DiscoveryResponse, language: str) -> str:
    if result.requires_confirmation:
        return ("请先确认模型建议的歌手；若不是你要找的歌手，可以自行填写。确认后再推荐。" if language == "zh" else
                "Confirm the suggested artist before recommendations, or provide a different artist.")
    if result.seed_status == "ambiguous":
        return ("找到多个同名版本，请先确认歌手，再推荐相关歌曲。" if language == "zh" else
                "Several artists have this title. Choose the artist to discover related tracks.")
    if result.seed_track is not None:
        return (f"以这首歌为起点，按歌手、风格和已有偏好找到 {len(result.items)} 首相关歌曲；不重复推荐同名版本。"
                if language == "zh" else
                f"Found {len(result.items)} related tracks using the seed artist, musical attributes and your feedback. "
                "Other versions of the seed are excluded.")
    if not result.items:
        return ("暂未找到可靠的起点歌曲，请补充歌手或换一个输入。" if language == "zh" else
                "A reliable seed recording was not found. Add the artist or try another input.")
    return (f"根据输入和已有偏好推荐 {len(result.items)} 首歌曲，顺序由推荐器确定。" if language == "zh" else
            f"Found {len(result.items)} tracks using your input and feedback, in recommender order.")


async def add_guidance(result: DiscoveryResponse, request: DiscoveryRequest,
                       provider: LLMProvider) -> DiscoveryResponse:
    result.guidance = local_guidance(result, request.language)
    # Ambiguous/empty results require user input rather than model speculation.
    if provider.name == "local" or not result.items:
        return result
    context = {"task": "discovery_guidance", "language": request.language,
               "message": request.seed, "seed_status": result.seed_status,
               "seed_track": {"title": result.seed_track.title[:200],
                              "artist": result.seed_track.artist.name[:200]}
               if result.seed_track else None}
    items = [{"title": item.title[:200], "artist": item.artist[:200],
              "score": item.score, "score_breakdown": item.score_breakdown,
              "explanation": item.explanation[:500]} for item in result.items]
    try:
        async with asyncio.timeout(8):
            answer = Answer.model_validate(await provider.answer(context, [
                {"name": "recommend_tracks", "output": {"items": items}}]))
        result.guidance = answer.answer
        result.guidance_provider = "openai_compatible"
    except (TimeoutError, httpx.HTTPError, ValueError, TypeError, KeyError):
        # Optional prose cannot take away valid canonical recommendations.
        result.guidance_status = "unavailable"
        emit("discovery_guidance", status="error", code="llm_unavailable", level=logging.WARNING)
    return result

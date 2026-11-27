from fastapi import FastAPI

from app import __version__
from app.api import analyses, applications, health, jobs, resumes
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="채용공고 요구조건과 이력서 근거를 대조해, LLM이 제시한 근거가 실제로 맞는지 검증하는 분석 API",
    )
    for module in (health, resumes, jobs, analyses, applications):
        app.include_router(module.router)
    return app


app = create_app()

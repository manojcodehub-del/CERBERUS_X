"""Root router for all API modules."""

from fastapi import APIRouter

from app.api.analytics import router as analytics_router
from app.api.claims import router as claims_router
from app.api.contradictions import router as contradictions_router
from app.api.documents import router as documents_router
from app.api.intelligence import router as intelligence_router
from app.api.investigations import router as investigations_router
from app.api.knowledge_graph import router as knowledge_graph_router
from app.api.reliability import router as reliability_router
from app.api.system import router as system_router
from app.api.verification import router as verification_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(documents_router)
api_router.include_router(analytics_router)
api_router.include_router(intelligence_router)
api_router.include_router(claims_router)
api_router.include_router(contradictions_router)
api_router.include_router(reliability_router)
api_router.include_router(knowledge_graph_router)
api_router.include_router(verification_router)
api_router.include_router(investigations_router)

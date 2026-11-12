from fastapi import APIRouter
from sk_common.people.router import router as people_router

from app.modules.auth import router as auth_router
from app.modules.directory.router import router as directory_router
from app.modules.responses.router import preview_router
from app.modules.responses.router import router as public_router
from app.modules.results.router import router as results_router
from app.modules.surveys.router import router as surveys_router
from app.modules.system.router import router as system_router

api_router = APIRouter(prefix='/api')
api_router.include_router(system_router)
api_router.include_router(auth_router)
api_router.include_router(people_router)
api_router.include_router(directory_router)
api_router.include_router(surveys_router)
api_router.include_router(results_router)
api_router.include_router(public_router)
api_router.include_router(preview_router)

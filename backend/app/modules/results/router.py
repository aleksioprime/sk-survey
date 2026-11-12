from urllib.parse import quote

from fastapi import APIRouter, Query
from fastapi.responses import Response
from sk_common.audit import record
from sk_common.deps import CurrentUser, Db

from app.modules.results import service
from app.modules.results.schemas import IndividualResponses, PublishingResults
from app.modules.surveys.permissions import viewable_publishing

router = APIRouter(prefix='/v1/publishings', tags=['results'])

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


@router.get('/{publishing_id}/results', response_model=PublishingResults, summary='Сводка по вопросам')
async def results(
    publishing_id: int, db: Db, user: CurrentUser, include_in_progress: bool = False
) -> PublishingResults:
    publishing, _ = await viewable_publishing(db, publishing_id, user)
    return service.summarize(await service.load(db, publishing, include_in_progress))


@router.get('/{publishing_id}/responses', response_model=IndividualResponses, summary='Отдельные ответы')
async def individual_responses(
    publishing_id: int, db: Db, user: CurrentUser, include_in_progress: bool = False, page: int = Query(1, ge=1)
) -> IndividualResponses:
    publishing, _ = await viewable_publishing(db, publishing_id, user)
    return await service.individual_responses(db, publishing, include_in_progress, page)


@router.get('/{publishing_id}/export.xlsx', summary='Ответы в Excel')
async def export(publishing_id: int, db: Db, user: CurrentUser, include_in_progress: bool = False) -> Response:
    publishing, _ = await viewable_publishing(db, publishing_id, user)
    content = service.export_xlsx(await service.load(db, publishing, include_in_progress))
    record(db, 'publishing.export', 'publishing', publishing.id, user.id)
    await db.commit()
    filename = quote(f'{publishing.title[:80]}.xlsx')
    return Response(
        content, media_type=XLSX, headers={'Content-Disposition': f"attachment; filename*=UTF-8''{filename}"}
    )

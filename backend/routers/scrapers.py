from fastapi import APIRouter, HTTPException

from backend.models.job import ScraperJob
from backend.services.scrapers import list_scraper_jobs, trigger_scraper_job

router = APIRouter(prefix="/scrapers", tags=["scrapers"])


@router.get("", response_model=list[ScraperJob])
async def get_scrapers():
    return list_scraper_jobs()


@router.post("/{job_id}/run")
async def run_scraper(job_id: int):
    try:
        result = trigger_scraper_job(job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result

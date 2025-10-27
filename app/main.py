import logging
from typing import List

from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from pydantic_ai import BinaryContent
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from fastapi import FastAPI, Request, HTTPException, Form, File, UploadFile, BackgroundTasks, Depends, Response
from fastapi.responses import JSONResponse

from app.models.Request import CreateAnalysisRequest
from app.models.Response import AnalysisResponse

app = FastAPI()


origins = ['*']
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    error_details = [
        {
            "field": ".".join(str(loc_part) for loc_part in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]

    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": error_details,
            "error": "Validation Error",
            "path": request.url.path,
        }
    )


logger = logging.getLogger('uvicorn')

def validade_request_input_raising_http_exception(
        skin_data: str,
        images: List[UploadFile],
):
    try:
        form_data = CreateAnalysisRequest.model_validate(skin_data)
    except Exception as e:
        logger.error(f"Erro na validação dos dados do formulário: {e}")
        raise HTTPException(status_code=400, detail=f"Erro na validação dos dados do formulário: {e}")

    if not images:
        logging.warning("Nenhuma imagem fornecida.")
        raise HTTPException(status_code=400, detail="Pelo menos uma imagem é necessária.")

async def process_images(images: List[UploadFile]) -> List[BinaryContent]:
    try:
        binary_images = []
        for image in images:
            binary_images.append(BinaryContent(
                data=await image.read(),
                media_type=image.content_type,
                identifier=image.filename
            ))
        return binary_images
    except Exception as e:
        logging.error(f"Erro ao processar as imagens: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar as imagens.")

@app.post('/analyze', summary='Creates a new skin analysis', response_model=AnalysisResponse)
async def get_analysis(
        skin_data: str = Form(..., alias="skinData"),
        images: List[UploadFile] = File(...),
):
    validade_request_input_raising_http_exception(skin_data, images)

    binary_images = await process_images(images)
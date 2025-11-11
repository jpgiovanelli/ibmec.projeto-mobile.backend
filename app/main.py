import logging
from typing import List
from io import BytesIO

from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from pydantic_ai import BinaryContent
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from fastapi import FastAPI, Request, HTTPException, Form, File, UploadFile, Depends
from fastapi.responses import JSONResponse

from PIL import Image
import pillow_heif

from app.ai.AiServices import analyze_skin
from app.models.Request import SkinProfileRequest, AIRequest
from app.models.Response import AnalysisResponse

# Registrar plugin HEIF para Pillow
pillow_heif.register_heif_opener()

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


def get_skin_profile(skinData: str = Form(...)) -> SkinProfileRequest:
    try:
        return SkinProfileRequest.model_validate_json(skinData)
    except ValidationError as e:
        logger.error(f"Erro na validação dos dados do formulário: {e}")
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Erro na validação dos dados do formulário: {e}")


async def process_images(images: List[UploadFile]) -> List[BinaryContent]:
    if not images:
        logging.warning("Nenhuma imagem fornecida.")
        raise HTTPException(status_code=400, detail="Pelo menos uma imagem é necessária.")
    try:
        binary_images = []
        for image in images:
            image_data = await image.read()
            content_type = image.content_type or "application/octet-stream"
            filename = image.filename or "image"
            
            # Verificar se é HEIC ou formato não suportado
            if content_type in ["image/heic", "image/heif", "application/octet-stream"] or \
               filename.lower().endswith(('.heic', '.heif')):
                try:
                    # Converter HEIC para JPEG
                    pil_image = Image.open(BytesIO(image_data))
                    
                    # Converter para RGB se necessário (HEIC pode ter outros modos)
                    if pil_image.mode in ("RGBA", "LA", "P"):
                        pil_image = pil_image.convert("RGB")
                    
                    # Salvar como JPEG em memória
                    jpeg_buffer = BytesIO()
                    pil_image.save(jpeg_buffer, format="JPEG", quality=95)
                    jpeg_buffer.seek(0)
                    
                    image_data = jpeg_buffer.read()
                    content_type = "image/jpeg"
                    filename = filename.rsplit('.', 1)[0] + '.jpg'
                    
                    logging.info(f"Imagem HEIC convertida para JPEG: {filename}")
                except Exception as e:
                    logging.error(f"Erro ao converter HEIC: {e}")
                    raise HTTPException(status_code=400, detail=f"Erro ao processar imagem HEIC: {str(e)}")
            
            binary_images.append(BinaryContent(
                data=image_data,
                media_type=content_type,
                identifier=filename
            ))
        return binary_images
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Erro ao processar as imagens: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar as imagens.")


@app.post('/analyze', summary='Creates a new skin analysis', response_model=AnalysisResponse)
async def get_analysis(
        skin_profile: SkinProfileRequest = Depends(get_skin_profile),
        images: List[UploadFile] = File(...),
):
    try:
        images = await process_images(images)

        ai_request = AIRequest(
            skin_profile=skin_profile,
            images=images
        )

        return await analyze_skin(ai_request)
    except Exception as e:
        logger.error(f"Erro ao processar análise: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao processar análise: {str(e)}")

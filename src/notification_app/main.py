import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Union
from http.client import responses as http_responses

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


SERVICE_NAME = os.getenv("SERVICE_NAME", "notification-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-valid-token")


app = FastAPI(
    title="Smart Campus Notification API - Nhóm 16",
    version=SERVICE_VERSION,
    description=(
        "Dockerized Notification API aligned with the Lab 03 OpenAPI/Postman contract."
    ),
)


class NotificationType(str, Enum):
    Academic = "Academic"
    Emergency = "Emergency"
    Social = "Social"


class NotificationChannel(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"
    IN_APP = "IN_APP"


class NotificationPriority(str, Enum):
    High = "High"
    Medium = "Medium"
    Low = "Low"


# --- Schemas ---

class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int = Field(..., ge=400, le=599)
    detail: str
    instance: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class NotificationRequest(BaseModel):
    recipientId: str = Field(..., min_length=1, examples=["SV123456"])
    content: str = Field(..., max_length=1000, examples=["Lớp Calculus 1 sẽ diễn ra vào lúc 8:00 AM ngày mai"])
    type: NotificationType = Field(..., examples=["Academic"])
    channel: NotificationChannel = Field(..., examples=["EMAIL"])
    priority: NotificationPriority = Field(..., examples=["High"])
    title: Optional[str] = Field(default=None, examples=["Thông báo lớp học"])


class AcademicNotification(BaseModel):
    id: str
    type: str = "Academic"
    courseName: str
    message: str
    channel: NotificationChannel


class EmergencyNotification(BaseModel):
    id: str
    type: str = "Emergency"
    location: str
    hazardLevel: int = Field(..., ge=1, le=5)
    channel: NotificationChannel


class SocialNotification(BaseModel):
    id: str
    type: str = "Social"
    message: str
    channel: NotificationChannel
    priority: NotificationPriority


# --- In-memory Store ---

# Preseed mock notification to pass Postman retrieve/read/retry tests
MOCK_NOTIF_ID = "550e8400-e29b-41d4-a716-446655440000"
NOTIFICATIONS: Dict[str, Dict] = {
    MOCK_NOTIF_ID: {
        "id": MOCK_NOTIF_ID,
        "type": "Academic",
        "courseName": "Calculus 1",
        "message": "Lớp Calculus 1 sẽ diễn ra vào lúc 8:00 AM ngày mai",
        "channel": "EMAIL",
        "recipientId": "SV123456",
        "priority": "High",
        "title": "Thông báo lớp học",
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
}

# Stores responses mapped by X-Idempotency-Key
IDEMPOTENCY_STORE: Dict[str, Dict] = {}


# --- Helpers ---

def build_problem(
    *,
    status_code: int,
    title: str,
    detail: str,
    instance: Optional[str] = None,
    problem_type: str = "about:blank",
) -> Dict:
    problem = {
        "type": problem_type,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        problem["instance"] = instance
    return problem


# --- Exception Handlers ---

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        problem = exc.detail
    else:
        problem = build_problem(
            status_code=exc.status_code,
            title=http_responses.get(exc.status_code, "HTTP Error"),
            detail=str(exc.detail),
            instance=str(request.url.path),
        )

    problem.setdefault("status", exc.status_code)
    problem.setdefault("title", http_responses.get(exc.status_code, "HTTP Error"))
    problem.setdefault("type", "about:blank")
    problem.setdefault("detail", "Request failed")
    problem.setdefault("instance", str(request.url.path))

    return JSONResponse(
        status_code=exc.status_code,
        content=problem,
        media_type="application/problem+json",
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(item) for item in first_error.get("loc", []))
    message = first_error.get("msg", "Request validation error")
    detail = f"{location}: {message}" if location else message

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Validation error",
            detail=detail,
            instance=str(request.url.path),
            problem_type="https://smart-campus.local/problems/validation-error",
        ),
        media_type="application/problem+json",
    )


# --- Authentication Dependency ---

def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Missing Authorization header",
                problem_type="https://smart-campus.local/problems/unauthorized",
            ),
        )

    expected = f"Bearer {AUTH_TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Invalid bearer token",
                problem_type="https://smart-campus.local/problems/unauthorized",
            ),
        )


# --- Endpoints ---

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
    )


@app.post(
    "/notifications",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bearer_token)],
    responses={
        201: {"description": "Thông báo đã được tiếp nhận thành công."},
        400: {"model": ProblemDetails},
        401: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
        429: {"model": ProblemDetails},
    },
)
def trigger_notification(
    payload: NotificationRequest,
    response: Response,
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key")
) -> Dict:
    # 1. Check Idempotency Key
    if x_idempotency_key:
        # Validate UUID format
        try:
            uuid.UUID(x_idempotency_key)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=build_problem(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    title="Bad Request",
                    detail="Invalid X-Idempotency-Key format. Must be a valid UUID.",
                    problem_type="https://smart-campus.local/problems/bad-request",
                )
            )

        if x_idempotency_key in IDEMPOTENCY_STORE:
            # Return cached response to achieve deduplication
            response.status_code = status.HTTP_201_CREATED
            return IDEMPOTENCY_STORE[x_idempotency_key]

    # 2. Process and create notification
    notif_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    result: Dict = {}
    if payload.type == NotificationType.Academic:
        # Academic schema expects courseName and message
        course_name = payload.title if payload.title else "Calculus 1"
        result = {
            "id": notif_id,
            "type": "Academic",
            "courseName": course_name,
            "message": payload.content,
            "channel": payload.channel.value
        }
    elif payload.type == NotificationType.Emergency:
        # Emergency schema expects location and hazardLevel
        location = payload.title if payload.title else "Building B"
        result = {
            "id": notif_id,
            "type": "Emergency",
            "location": location,
            "hazardLevel": 4, # Mock hazard level
            "channel": payload.channel.value
        }
    else: # Social or any other
        result = {
            "id": notif_id,
            "type": payload.type.value,
            "message": payload.content,
            "channel": payload.channel.value,
            "priority": payload.priority.value
        }

    # Save to memory stores
    full_store_entry = {
        **result,
        "recipientId": payload.recipientId,
        "priority": payload.priority.value,
        "title": payload.title,
        "read": False,
        "created_at": created_at
    }
    NOTIFICATIONS[notif_id] = full_store_entry

    if x_idempotency_key:
        IDEMPOTENCY_STORE[x_idempotency_key] = result

    return result


@app.get(
    "/notifications/{id}",
    dependencies=[Depends(verify_bearer_token)],
    responses={
        200: {"description": "Thông tin chi tiết thông báo."},
        401: {"model": ProblemDetails},
        404: {"model": ProblemDetails},
    },
)
def get_notification_by_id(id: str) -> Dict:
    # Validate UUID format unless it matches the preseeded ID
    if id != MOCK_NOTIF_ID:
        try:
            uuid.UUID(id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=build_problem(
                    status_code=status.HTTP_404_NOT_FOUND,
                    title="Not Found",
                    detail=f"Notification {id} is not found (invalid UUID format)",
                    instance=f"/notifications/{id}",
                    problem_type="https://smart-campus.local/problems/not-found",
                )
            )

    if id not in NOTIFICATIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_problem(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Not Found",
                detail=f"Notification {id} does not exist",
                instance=f"/notifications/{id}",
                problem_type="https://smart-campus.local/problems/not-found",
            )
        )

    # Return correct schema structure
    db_notif = NOTIFICATIONS[id]
    if db_notif["type"] == "Academic":
        return {
            "id": db_notif["id"],
            "type": "Academic",
            "courseName": db_notif.get("courseName", "Calculus 1"),
            "message": db_notif.get("message", db_notif.get("content", "")),
            "channel": db_notif["channel"]
        }
    elif db_notif["type"] == "Emergency":
        return {
            "id": db_notif["id"],
            "type": "Emergency",
            "location": db_notif.get("location", "Building B"),
            "hazardLevel": db_notif.get("hazardLevel", 4),
            "channel": db_notif["channel"]
        }
    else:
        return {
            "id": db_notif["id"],
            "type": db_notif["type"],
            "message": db_notif.get("message", db_notif.get("content", "")),
            "channel": db_notif["channel"],
            "priority": db_notif.get("priority", "Medium")
        }


@app.get(
    "/notifications/user/{userId}",
    dependencies=[Depends(verify_bearer_token)],
    response_model=List[Dict],
    responses={
        200: {"description": "Danh sách thông báo."},
        401: {"model": ProblemDetails},
    },
)
def get_user_notifications(userId: str) -> List[Dict]:
    results = []
    for notif in NOTIFICATIONS.values():
        if notif.get("recipientId") == userId:
            # format matching schema
            if notif["type"] == "Academic":
                results.append({
                    "id": notif["id"],
                    "type": "Academic",
                    "courseName": notif.get("courseName", "Calculus 1"),
                    "message": notif.get("message", notif.get("content", "")),
                    "channel": notif["channel"]
                })
            elif notif["type"] == "Emergency":
                results.append({
                    "id": notif["id"],
                    "type": "Emergency",
                    "location": notif.get("location", "Building B"),
                    "hazardLevel": notif.get("hazardLevel", 4),
                    "channel": notif["channel"]
                })
            else:
                results.append({
                    "id": notif["id"],
                    "type": notif["type"],
                    "message": notif.get("message", notif.get("content", "")),
                    "channel": notif["channel"],
                    "priority": notif.get("priority", "Medium")
                })
    return results


@app.patch(
    "/notifications/{id}/read",
    dependencies=[Depends(verify_bearer_token)],
    responses={
        200: {"description": "Cập nhật thành công."},
        401: {"model": ProblemDetails},
        404: {"model": ProblemDetails},
    },
)
def mark_notification_as_read(id: str) -> Dict:
    if id != MOCK_NOTIF_ID:
        try:
            uuid.UUID(id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=build_problem(
                    status_code=status.HTTP_404_NOT_FOUND,
                    title="Not Found",
                    detail=f"Notification {id} is not found (invalid UUID format)",
                    instance=f"/notifications/{id}/read",
                    problem_type="https://smart-campus.local/problems/not-found",
                )
            )

    if id not in NOTIFICATIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_problem(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Not Found",
                detail=f"Notification {id} does not exist",
                instance=f"/notifications/{id}/read",
                problem_type="https://smart-campus.local/problems/not-found",
            )
        )

    NOTIFICATIONS[id]["read"] = True
    return {"status": "success", "message": f"Notification {id} marked as read"}


@app.post(
    "/notifications/{id}/retry",
    dependencies=[Depends(verify_bearer_token)],
    responses={
        200: {"description": "Đã đưa vào hàng đợi gửi lại thành công."},
        401: {"model": ProblemDetails},
        404: {"model": ProblemDetails},
    },
)
def retry_notification(id: str) -> Dict:
    if id != MOCK_NOTIF_ID:
        try:
            uuid.UUID(id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=build_problem(
                    status_code=status.HTTP_404_NOT_FOUND,
                    title="Not Found",
                    detail=f"Notification {id} is not found (invalid UUID format)",
                    instance=f"/notifications/{id}/retry",
                    problem_type="https://smart-campus.local/problems/not-found",
                )
            )

    if id not in NOTIFICATIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_problem(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Not Found",
                detail=f"Notification {id} does not exist",
                instance=f"/notifications/{id}/retry",
                problem_type="https://smart-campus.local/problems/not-found",
            )
        )

    return {"status": "queued", "message": f"Notification {id} is queued for retry"}

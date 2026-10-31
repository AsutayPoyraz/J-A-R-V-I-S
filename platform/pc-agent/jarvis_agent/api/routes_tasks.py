"""Görev & proje yöneticisi uçları (Özellik 6).

Misafir: store katmanı zaten yazmayı engeller (boş liste döner);
misafir arayüzü oturumluk yerel state kullanır (mega prompt 6.7).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import security
from ..store import v11

router = APIRouter()


class ProjectBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#22d3ee", max_length=16)


class TaskBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    project: str = Field(default="", max_length=80)
    project_id: Optional[int] = None
    priority: str = Field(default="medium", max_length=12)
    due_date: str = Field(default="", max_length=32)
    description: str = Field(default="", max_length=2000)


class TaskPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    priority: Optional[str] = Field(default=None, max_length=12)
    status: Optional[str] = Field(default=None, max_length=12)
    due_date: Optional[str] = Field(default=None, max_length=32)


class SubtaskBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    done: Optional[bool] = None


@router.get("/api/tasks/projects")
def get_projects(request: Request) -> dict:
    return {"projects": v11.list_projects(security.request_owner(request))}


@router.post("/api/tasks/projects")
def post_project(payload: ProjectBody, request: Request) -> dict:
    project = v11.create_project(
        security.request_owner(request), payload.name, payload.color
    )
    if project is None:
        raise HTTPException(status_code=409, detail="Proje oluşturulamadı (misafir veya mevcut).")
    return {"project": project}


@router.put("/api/tasks/projects/{project_id}")
def put_project(project_id: int, payload: ProjectBody, request: Request) -> dict:
    owner = security.request_owner(request)
    if v11.delete_project(owner, project_id):
        created = v11.create_project(owner, payload.name, payload.color)
        if created:
            return {"project": created}
    raise HTTPException(status_code=404, detail="Proje bulunamadı.")


@router.delete("/api/tasks/projects/{project_id}")
def remove_project(project_id: int, request: Request) -> dict:
    ok = v11.delete_project(security.request_owner(request), project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")
    return {"ok": True}


@router.get("/api/tasks/projects/{project_id}/tasks")
def get_project_tasks(project_id: int, request: Request) -> dict:
    return {
        "tasks": v11.list_tasks(security.request_owner(request), project_id=project_id)
    }


@router.post("/api/tasks/projects/{project_id}/tasks")
def post_project_task(project_id: int, payload: TaskBody, request: Request) -> dict:
    owner = security.request_owner(request)
    project = v11.get_project(owner, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Proje bulunamadı.")
    task = v11.create_task(
        owner, payload.title, project=project["name"], priority=payload.priority,
        due_date=payload.due_date, description=payload.description,
    )
    if task is None:
        raise HTTPException(status_code=422, detail="Görev oluşturulamadı.")
    return {"task": task}


@router.get("/api/tasks")
def get_tasks(request: Request, status: str = "", project_id: int = 0) -> dict:
    owner = security.request_owner(request)
    return {
        "tasks": v11.list_tasks(
            owner,
            project_id=project_id or None,
            status=status or None,
        )
    }


@router.post("/api/tasks")
def post_task(payload: TaskBody, request: Request) -> dict:
    task = v11.create_task(
        security.request_owner(request),
        payload.title,
        project=payload.project,
        priority=payload.priority,
        due_date=payload.due_date,
        description=payload.description,
    )
    if task is None:
        raise HTTPException(status_code=422, detail="Görev oluşturulamadı (misafir?).")
    return {"task": task}


@router.put("/api/tasks/{task_id}")
def put_task(task_id: int, payload: TaskPatch, request: Request) -> dict:
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    task = v11.update_task(security.request_owner(request), task_id, patch)
    if task is None:
        raise HTTPException(status_code=404, detail="Görev bulunamadı.")
    return {"task": task}


@router.delete("/api/tasks/{task_id}")
def remove_task(task_id: int, request: Request) -> dict:
    if not v11.delete_task(security.request_owner(request), task_id):
        raise HTTPException(status_code=404, detail="Görev bulunamadı.")
    return {"ok": True}


@router.post("/api/tasks/{task_id}/subtasks")
def post_subtask(task_id: int, payload: SubtaskBody, request: Request) -> dict:
    sub = v11.add_subtask(security.request_owner(request), task_id, payload.title)
    if sub is None:
        raise HTTPException(status_code=404, detail="Görev bulunamadı.")
    return {"subtask": sub}


@router.put("/api/tasks/subtasks/{subtask_id}")
def put_subtask(subtask_id: int, payload: SubtaskBody, request: Request) -> dict:
    ok = v11.update_subtask(
        security.request_owner(request), subtask_id, done=payload.done
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Alt görev bulunamadı.")
    return {"ok": True}


@router.delete("/api/tasks/subtasks/{subtask_id}")
def remove_subtask(subtask_id: int, request: Request) -> dict:
    if not v11.delete_subtask(security.request_owner(request), subtask_id):
        raise HTTPException(status_code=404, detail="Alt görev bulunamadı.")
    return {"ok": True}

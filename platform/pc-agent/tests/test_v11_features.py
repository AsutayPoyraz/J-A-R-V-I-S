"""Özellik 6 + 8 + 9 + 10 testleri: görevler, RAG, makrolar, alışkanlıklar."""
from __future__ import annotations

import asyncio

from jarvis_agent.store import v11


# ══ Özellik 6: görevler + LLM araçları ═══════════════════════════════════════

def test_tasks_crud_and_llm_tools(rig):
    client, _ = rig
    created = client.post(
        "/api/tasks",
        json={"title": "Raporu bitir", "project": "İş", "priority": "high",
              "due_date": "2099-01-01"},
    )
    assert created.status_code == 200
    task = created.json()["task"]
    assert task["priority"] == "high" and task["status"] == "todo"
    assert task["project_name"] == "İş"
    listing = client.get("/api/tasks").json()["tasks"]
    assert any(t["id"] == task["id"] for t in listing)
    done = client.put(f"/api/tasks/{task['id']}", json={"status": "done"})
    assert done.json()["task"]["status"] == "done"
    sub = client.post(f"/api/tasks/{task['id']}/subtasks", json={"title": "Giriş yaz"})
    assert sub.status_code == 200
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 200
    # LLM araçları ("yarına kadar X'i bitir" → otomatik görev)
    from jarvis_agent.core import context as ctx
    from jarvis_agent.llm import tools

    ctx.set_owner("local")
    result = asyncio.run(
        tools.execute_tool("create_task", {"title": "LLM görevi", "priority": "urgent"})
    )
    assert result["created"] is True and result["task"]["priority"] == "urgent"
    listed = asyncio.run(tools.execute_tool("list_tasks", {"status": "todo"}))
    assert any(t["title"] == "LLM görevi" for t in listed["tasks"])
    completed = asyncio.run(
        tools.execute_tool("complete_task", {"task_id": result["task"]["id"]})
    )
    assert completed["completed"] is True


def test_tasks_guest_noop(rig):
    assert v11.create_task("guest:anon", "Görev") is None
    assert v11.list_tasks("guest:anon") == []
    assert v11.complete_task("guest:anon", 1) is None


# ══ Özellik 8: bilgi tabanı RAG ══════════════════════════════════════════════

def test_knowledge_ingest_search_delete(rig):
    client, _ = rig
    doc = client.post(
        "/api/knowledge/upload",
        files={
            "file": (
                "notlar.txt",
                b"JARVIS v11 gizli proje kodu: ATLAS-X. Clio Renault markasidir.",
                "text/plain",
            )
        },
    )
    assert doc.status_code == 200
    doc_id = doc.json()["document_id"]
    listing = client.get("/api/knowledge/documents").json()["documents"]
    assert listing and listing[0]["status"] == "ready"
    hits = client.get(
        "/api/knowledge/search", params={"q": "gizli proje kodu"}
    ).json()["results"]
    assert hits and "ATLAS-X" in hits[0]["content"]
    assert client.delete(f"/api/knowledge/{doc_id}").status_code == 200


def test_knowledge_docx_and_chunking():
    import io
    import zipfile

    from jarvis_agent.knowledge.ingestion import chunk_text, extract_text

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0"?><w:document '
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>Merhaba dünya belgesi</w:t></w:r></w:p></w:body>"
            "</w:document>",
        )
    text = extract_text("test.docx", buf.getvalue())
    assert "Merhaba dünya" in text
    chunks = chunk_text("kelime " * 300)
    assert len(chunks) > 1  # ~500 token sınırına örtüşmeli bölünür


# ══ Özellik 9: command-macros ════════════════════════════════════════════════

def test_command_macros_crud_and_trigger(rig):
    client, _ = rig
    created = client.post(
        "/api/command-macros",
        json={
            "name": "Sabah Rutini",
            "trigger_phrase": "sabah rutinini başlat",
            "steps": [
                {"type": "chat", "params": {"message": "selam"}},
                {"type": "delay", "params": {"seconds": 0.1}},
            ],
        },
    )
    assert created.status_code == 200
    macro = created.json()["macro"]
    found = v11.find_macro_by_trigger("local", "jarvis sabah rutinini başlat")
    assert found is not None and found["id"] == macro["id"]
    run = client.post(f"/api/command-macros/{macro['id']}/run")
    assert run.status_code == 200
    outputs = run.json()["outputs"]
    assert any(o.get("type") == "chat" for o in outputs)
    # Eski section_f /api/macros HÂLÂ çalışmalı (çakışma yok)
    legacy = client.post(
        "/api/macros",
        json={"name": "kısayol", "steps": [{"action": "open", "target": "chrome"}]},
    )
    assert legacy.status_code == 200 and legacy.json()["id"] > 0
    assert client.delete(f"/api/command-macros/{macro['id']}").status_code == 200


# ══ Özellik 10: alışkanlıklar + üretkenlik ═══════════════════════════════════

def test_habits_streak_and_stats(rig):
    client, _ = rig
    created = client.post("/api/habits", json={"name": "Su iç", "icon": "drop"})
    assert created.status_code == 200
    habit = created.json()["habit"]
    assert client.post(
        f"/api/habits/{habit['id']}/log", json={"completed": True}
    ).status_code == 200
    stats = client.get("/api/habits/stats").json()
    assert stats["total"] == 1 and stats["best_streak"] == 1
    session = client.post(
        "/api/productivity/session", json={"focus_minutes": 45, "mood": 4}
    )
    assert session.status_code == 200
    insights = client.get("/api/productivity/insights").json()
    assert insights["insight"]

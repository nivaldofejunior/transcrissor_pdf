# tests/test_flow_async.py
import io
import pytest
from pathlib import Path
from bson import ObjectId

from app.core.paths import audio_path

pytestmark = pytest.mark.asyncio

def _fake_pdf_bytes() -> bytes:
    # PDF mínimo o bastante para os testes
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

async def test_full_flow_async(client, auth_headers, db, test_user_id_str):
    # 1) Criar matéria
    resp = await client.post("/materias/", json={"titulo": "Banco de Dados"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    materia = resp.json()
    materia_id = materia["id"]
    assert materia["titulo"] == "Banco de Dados"

    # 2) Criar aula
    resp = await client.post(
        "/aulas/",
        json={"titulo": "Índices e Normalização", "descricao": "Aula 01", "materia_id": materia_id},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    aula = resp.json()
    aula_id = aula["id"]

    # 3) Upload PDF
    pdf_bytes = _fake_pdf_bytes()
    files = {"file": ("aula01.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    resp = await client.post(f"/aulas/{aula_id}/pdfs/", files=files, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    pdf_doc = resp.json()
    pdf_id = pdf_doc["id"]

    # Confere arquivo físico
    path_pdf = Path(pdf_doc["caminho"])
    assert path_pdf.exists()
    assert path_pdf.read_bytes().startswith(b"%PDF")

    # 4) Simular conclusão da task -> criar áudio no caminho padronizado e atualizar no Mongo
    dest_audio = audio_path(test_user_id_str, aula_id, pdf_id, ext="mp3")
    dest_audio.parent.mkdir(parents=True, exist_ok=True)
    dest_audio.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x21")  # mp3 dummy

    await db.pdfs.update_one({"_id": ObjectId(pdf_id)}, {"$set": {"audio_path": str(dest_audio)}})

    # 5) Tocar áudio
    resp = await client.get(f"/pdfs/{pdf_id}/audio", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/mpeg")

    # 6) Listar PDFs da aula
    resp = await client.get(f"/aulas/{aula_id}/pdfs", headers=auth_headers)
    assert resp.status_code == 200
    lst = resp.json()
    assert any(item["id"] == pdf_id for item in lst)

    # 7) Excluir PDF (remove banco + arquivos)
    resp = await client.delete(f"/pdfs/{pdf_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert not path_pdf.exists()
    assert not dest_audio.exists()

    # 8) Excluir aula
    resp = await client.delete(f"/aulas/{aula_id}", headers=auth_headers)
    assert resp.status_code == 200

    # 9) Excluir matéria
    resp = await client.delete(f"/materias/{materia_id}", headers=auth_headers)
    assert resp.status_code == 200

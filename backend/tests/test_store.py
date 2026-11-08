from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.store import Store, public_document


class StorePersistTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.data_dir = Path(self.tmp.name)
        self.store = Store(self.data_dir)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_documents_projects_and_pdfs_survive_reopen(self) -> None:
        pdf = b"%PDF-1.1 test"
        self.store.save_pdf("doc-1", pdf)
        self.store.put_document(
            {
                "id": "doc-1",
                "filename": "vectors.pdf",
                "page_count": 1,
                "status": "ready",
                "error": None,
                "text": "vector retrieval",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        )
        self.store.put_project(
            {
                "id": "proj-1",
                "name": "Project 1",
                "document_ids": ["doc-1"],
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        )
        self.store.append_messages(
            "proj-1",
            [
                {
                    "id": "msg-1",
                    "role": "user",
                    "content": "What is retrieval?",
                    "citations": [],
                    "created_at": "2026-01-01T00:00:01+00:00",
                }
            ],
        )

        reopened = Store(self.data_dir)
        listed = reopened.list_documents()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["filename"], "vectors.pdf")
        self.assertNotIn("text", public_document(listed[0]))
        self.assertEqual(reopened.read_pdf("doc-1"), pdf)
        self.assertTrue(reopened.pdf_path("doc-1").is_file())

        project = reopened.get_project("proj-1")
        assert project is not None
        self.assertEqual(project["document_ids"], ["doc-1"])
        self.assertEqual(project["messages"][0]["content"], "What is retrieval?")

    def test_same_pdf_bytes_are_detected_as_duplicate(self) -> None:
        from app.store import pdf_content_hash

        pdf = b"%PDF-1.1 same-bytes"
        digest = pdf_content_hash(pdf)
        self.store.save_pdf("doc-1", pdf)
        self.store.put_document(
            {
                "id": "doc-1",
                "filename": "original.pdf",
                "page_count": 1,
                "status": "ready",
                "error": None,
                "text": "same",
                "content_hash": digest,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        )
        found = self.store.find_by_content_hash(digest)
        assert found is not None
        self.assertEqual(found["filename"], "original.pdf")
        self.assertEqual(pdf_content_hash(pdf), digest)


if __name__ == "__main__":
    unittest.main()

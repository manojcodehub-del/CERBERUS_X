def test_system_status_reports_real_local_dependencies(client, test_app) -> None:
    import shutil
    from pathlib import Path

    status = client.get("/api/system/status")

    assert status.status_code == 200
    body = status.json()
    assert body['status'] == 'ok'
    assert body['application'] == 'CERBERUS-X'
    assert body['environment'] == 'development'
    assert body['database'] == 'connected'
    assert body['upload_storage'] == 'ready'
    assert body['document_processing'] == 'available'
    assert body['ocr_engine'] == (
        'available'
        if (test_app.state.settings.tesseract_cmd and Path(test_app.state.settings.tesseract_cmd).is_file())
        or shutil.which('tesseract')
        else 'unavailable'
    )
    assert body['storage_free_bytes'] is None or body['storage_free_bytes'] >= 0
    assert body['offline_readiness'] == 'not_verified'
    assert test_app.state.settings.resolved_upload_dir.is_dir()


def test_analytics_are_database_counts_not_sample_values(client) -> None:
    analytics = client.get("/api/analytics")

    assert analytics.status_code == 200
    assert analytics.json() == {
        "total_documents": 0,
        "uploaded_documents": 0,
        "processing_documents": 0,
        "processed_documents": 0,
        "failed_documents": 0,
        "total_evidence": 0,
        "total_contradictions": 0,
        "active_jobs": 0,
    }



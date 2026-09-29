from django.urls import path

from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("evidence/search/", views.search_evidence, name="search_evidence"),
    path("evidence/inspect/", views.inspect_evidence, name="inspect_evidence"),
    path("evidence/upload/", views.upload_documents, name="upload_documents"),
    path("draft/", views.generate_draft, name="generate_draft"),
    path("draft/save/", views.save_text, name="save_text"),
    path("settings/", views.save_settings, name="save_settings"),
    path("governance/", views.run_governance, name="run_governance"),
    path("workflow/advance/", views.advance_workflow, name="advance_workflow"),
    path("workflow/rollback/", views.rollback_workflow, name="rollback_workflow"),
    path("workflow/export/", views.export_workflow, name="export_workflow"),
]

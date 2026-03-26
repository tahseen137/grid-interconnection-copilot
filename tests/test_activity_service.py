from sqlalchemy.orm import Session

from app.activity_service import list_activity_events, record_activity
from app.user_service import create_user


def test_record_and_list_activity_events(session: Session) -> None:
    user = create_user(
        session,
        username="audit.admin",
        password="audit-password",
        role="admin",
        full_name="Audit Admin",
    )

    record_activity(
        session,
        action="project.created",
        entity_type="project",
        entity_id="project-123",
        actor_user=user,
        project_id="project-123",
        description="Audit Admin created a project.",
        details={"name": "Project 123"},
    )

    events = list_activity_events(session)

    assert len(events) == 1
    assert events[0].actor_username == "audit.admin"
    assert events[0].action == "project.created"
    assert events[0].details["name"] == "Project 123"

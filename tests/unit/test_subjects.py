"""Subject model (resources.security): reading a subject of Superset 7.0. Pure logic, no HTTP; the repository is
checked against the real server in tests/integration/test_subjects.py."""
from supersetapiplus import Subject, SubjectType


def test_a_subject_read_from_superset_tells_what_it_stands_for():
    subject = Subject.from_json({"id": 7, "uuid": "1b4e28ba-2fa1-11d2-883f-0016d3cca427", "label": "Gamma", "type": 2,
                                 "active": True, "user_id": None, "role_id": 4, "group_id": None,
                                 "role": {"id": 4, "name": "Gamma"}})
    assert subject.type == SubjectType.ROLE and subject.role_id == 4 and subject.label == "Gamma"
    assert subject.to_json()["role"] == {"id": 4, "name": "Gamma"}  # detail kept as read

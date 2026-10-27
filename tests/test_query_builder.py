from datetime import datetime, timedelta

from motadata_helpdesk.enums import StatusEnum
from motadata_helpdesk.query_builder import QueryBuilder


def test_where_property():
    qb = QueryBuilder()
    qb.where_property("request.statusId", "in", [1, 2, 3])
    res = qb.build()

    assert res["qualDetails"]["type"] == "FlatQualificationRest"
    quals = res["qualDetails"]["quals"]
    assert len(quals) == 1
    assert quals[0]["operator"] == "in"
    assert quals[0]["leftOperand"]["key"] == "request.statusId"
    assert quals[0]["rightOperand"]["value"]["value"] == [1, 2, 3]


def test_where_property_single_value_and_enum():
    qb = QueryBuilder()
    qb.where_property("request.statusId", "equal", StatusEnum.CLOSED)
    res = qb.build()

    quals = res["qualDetails"]["quals"]
    assert len(quals) == 1
    assert quals[0]["rightOperand"]["value"]["value"] == [13]


def test_where_variable():
    qb = QueryBuilder()
    qb.where_variable("categoryId", "in", [10, 20])
    res = qb.build()

    quals = res["qualDetails"]["quals"]
    assert len(quals) == 1
    assert quals[0]["leftOperand"]["value"] == "categoryId"
    assert quals[0]["rightOperand"]["value"]["value"] == [10, 20]


def test_where_not_closed():
    qb = QueryBuilder().where_not_closed()
    res = qb.build()

    quals = res["qualDetails"]["quals"]
    assert len(quals) == 1
    assert quals[0]["operator"] == "not_in"
    assert quals[0]["leftOperand"]["key"] == "request.statusId"
    assert quals[0]["rightOperand"]["value"]["value"] == [StatusEnum.CLOSED]


def test_where_not_categorized():
    qb = QueryBuilder().where_not_categorized()
    res = qb.build()

    quals = res["qualDetails"]["quals"]
    assert len(quals) == 1
    assert quals[0]["leftOperand"]["value"] == "categoryId"
    assert quals[0]["rightOperand"]["value"]["value"] == [0]


def test_where_created_after_datetime():
    qb = QueryBuilder()
    target_dt = datetime.now() - timedelta(hours=1)
    qb.where_created_after(target_dt)
    res = qb.build()

    quals = res["qualDetails"]["quals"]
    assert len(quals) == 1
    assert quals[0]["leftOperand"]["key"] == "request.createdTime"
    assert quals[0]["operator"] == "within_last"
    ms_val = quals[0]["rightOperand"]["value"]["value"]
    # Roughly 3600 * 1000 = 3,600,000 ms (check range between 3,500,000 and 3,700,000)
    assert 3500000 <= ms_val <= 3700000


def test_where_string_and_enum_properties():
    qb = QueryBuilder()
    qb.where_string_property(".name", "contains", "Network")
    qb.where_enum_property(".conversation.conversationState", "equal", "published")
    res = qb.build()

    quals = res["qualDetails"]["quals"]
    assert len(quals) == 2
    assert quals[0]["rightOperand"]["value"]["type"] == "StringValueRest"
    assert quals[0]["rightOperand"]["value"]["value"] == "Network"
    assert quals[1]["rightOperand"]["value"]["type"] == "EnumValueRest"
    assert quals[1]["rightOperand"]["value"]["value"] == "published"


def test_builder_clear_and_to_dict():
    qb = QueryBuilder().where_not_closed()
    assert len(qb.quals) == 1
    qb.clear()
    assert len(qb.quals) == 0
    assert qb.to_dict() == {"qualDetails": {"type": "FlatQualificationRest", "quals": []}}

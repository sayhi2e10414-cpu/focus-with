from app.services.plan_import import parse_markdown_plan


def test_parses_chinese_gpt_plan_and_separates_breaks():
    result = parse_markdown_plan("""
1. **快速通读总流程**｜20分钟
2. **搭建“审判—执行”主框架**｜50分钟
3. **整理判决前的量刑制度**｜50分钟
4. **休息**｜10分钟
5. **整理判决后的执行制度**｜50分钟
""")

    assert [item["title"] for item in result["tasks"]] == [
        "快速通读总流程",
        "搭建“审判—执行”主框架",
        "整理判决前的量刑制度",
        "整理判决后的执行制度",
    ]
    assert result["breaks"] == [{"title": "休息", "estimated_minutes": 10}]

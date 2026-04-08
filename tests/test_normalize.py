# Core assertion: supported chat-export formats normalize into non-empty transcript text.

import json

from cloudmem.normalize import normalize


def test_normalize_claude_code_jsonl(tmp_path):
    p = tmp_path / "claude_code.jsonl"
    p.write_text(
        "\n".join(
            [
                json.dumps({"type": "human", "message": {"content": "hello"}}),
                json.dumps({"type": "assistant", "message": {"content": "world"}}),
            ]
        )
    )

    out = normalize(str(p))

    assert out.strip()
    assert "> hello" in out
    assert "world" in out


def test_normalize_claude_json_messages(tmp_path):
    p = tmp_path / "claude.json"
    payload = {
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
    }
    p.write_text(json.dumps(payload))

    out = normalize(str(p))

    assert out.strip()
    assert "> hello" in out
    assert "world" in out


def test_normalize_chatgpt_mapping_json(tmp_path):
    p = tmp_path / "chatgpt.json"
    payload = {
        "mapping": {
            "root": {"id": "root", "parent": None, "message": None, "children": ["u1"]},
            "u1": {
                "id": "u1",
                "parent": "root",
                "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["hello"]},
                },
                "children": ["a1"],
            },
            "a1": {
                "id": "a1",
                "parent": "u1",
                "message": {
                    "author": {"role": "assistant"},
                    "content": {"parts": ["world"]},
                },
                "children": [],
            },
        }
    }
    p.write_text(json.dumps(payload))

    out = normalize(str(p))

    assert out.strip()
    assert "> hello" in out
    assert "world" in out

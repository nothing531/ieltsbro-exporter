#!/usr/bin/env python3
"""Export a user's IELTSBro (雅思哥) learning records through its existing API.

This tool is intentionally read-only. It only calls endpoints used by the official
PC client's record and analysis pages and never stores the bearer token.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Iterator


DEFAULT_API = "https://hcp-server.ieltsbro.com"
CLIENT_SOURCE = "3"
CLIENT_VERSION = "3.2.0"
TOOL_VERSION = "0.2.1"
PART_NAMES = {1: "listening", 2: "speaking", 3: "reading", 4: "writing"}


class ExportError(RuntimeError):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")


def html_to_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(value)
        text = "".join(parser.parts)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text).replace("\u00a0", " ")
    return re.sub(r"[ \t]+", " ", re.sub(r"\r?\n\s*", "\n", text)).strip()


def clean_token(value: str) -> str:
    token = value.strip().strip('"')
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        raise ExportError("登录令牌为空。")
    return token


def token_from_chromium_profile(profile: Path) -> str:
    """Read the latest token value from IELTSBro's Chromium Local Storage.

    The token is returned in memory only. This function never logs or writes it.
    """
    leveldb = profile / "Local Storage" / "leveldb"
    if not leveldb.is_dir():
        raise ExportError(f"未找到雅思哥 Local Storage：{leveldb}")
    decoder = json.JSONDecoder()
    candidates: list[tuple[int, int, str]] = []
    files = [path for path in leveldb.iterdir() if path.suffix.lower() in {".log", ".ldb"}]
    for file_path in files:
        try:
            text = file_path.read_bytes().decode("utf-8", "ignore")
        except OSError:
            continue
        position = 0
        while True:
            start = text.find('{"token"', position)
            if start < 0:
                break
            try:
                value, _ = decoder.raw_decode(text[start:])
                token = value.get("token") if isinstance(value, dict) else None
                if isinstance(token, str) and token.strip():
                    candidates.append((file_path.stat().st_mtime_ns, start, token))
            except (ValueError, TypeError, OSError):
                pass
            position = start + 1
    if not candidates:
        raise ExportError("雅思哥 Local Storage 中没有找到登录令牌；请先在 PC 客户端登录。")
    candidates.sort(key=lambda item: (item[0], item[1]))
    return clean_token(candidates[-1][2])


@dataclass
class ApiClient:
    token: str
    base_url: str = DEFAULT_API
    timeout: int = 30
    pause_seconds: float = 0.08

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        url = self.base_url.rstrip("/") + "/hcp" + path
        if params:
            query = urllib.parse.urlencode(
                {key: value for key, value in params.items() if value is not None}
            )
            url += "?" + query

        body = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "source": CLIENT_SOURCE,
            "version": CLIENT_VERSION,
            "User-Agent": f"IELTSBro-ReadOnly-Exporter/{TOOL_VERSION}",
        }
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if payload.get("status") != 0:
                    status = payload.get("status")
                    message = payload.get("showMessage") or payload.get("message") or "未知错误"
                    if status in {10020, 10032, 10033, 10034, 10039, 10040, 10041}:
                        raise ExportError(f"登录已失效或令牌无效（{status}）：{message}")
                    raise ExportError(f"雅思哥接口返回错误（{status}）：{message}")
                time.sleep(self.pause_seconds)
                return payload.get("content")
            except ExportError:
                raise
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == 2:
                    break
            time.sleep(0.5 * (attempt + 1))
        raise ExportError(f"请求失败：{method} {path}（{last_error}）")

    def get(self, path: str, **params: Any) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, data: dict[str, Any] | None = None) -> Any:
        return self.request("POST", path, data=data or {})


def find_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    page_data = payload.get("pageData")
    if isinstance(page_data, dict):
        return find_list(page_data)
    for key in ("list", "records", "rows", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def find_total(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return len(payload) if isinstance(payload, list) else None
    page_data = payload.get("pageData")
    if isinstance(page_data, dict):
        return find_total(page_data)
    for key in ("total", "totalCount", "count"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def fetch_pages(
    fetch_page: Any,
    *,
    page_size_hint: int,
    max_pages: int,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        payload = fetch_page(page)
        items = find_list(payload)
        total = find_total(payload)
        output.extend(items)
        if not items or (total is not None and len(output) >= total) or len(items) < page_size_hint:
            break
    else:
        raise ExportError(f"分页超过安全上限 {max_pages} 页，请提高 --max-pages 后重试。")
    return output


def first_value(record: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def record_id(record: dict[str, Any], kind: str) -> str | None:
    keys = (
        ("exerciseIdStr", "exerciseId", "id")
        if kind == "practice"
        else ("examInfoId", "examId", "id")
    )
    value = first_value(record, keys)
    return str(value) if value not in (None, "") else None


def paper_id(record: dict[str, Any]) -> str | None:
    value = first_value(record, ("paperId", "testPaperId", "paperCode", "testPaperCode"))
    return str(value) if value not in (None, "") else None


def deep_items(value: Any, path: str = "$") -> Iterator[tuple[str, Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from deep_items(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from deep_items(child, f"{path}[{index}]")


USER_ANSWER_KEYS = (
    "userAnswer",
    "userAnwser",
    "userAnswers",
    "myAnswer",
    "studentAnswer",
    "inputAnswer",
)
RIGHT_ANSWER_KEYS = (
    "correctAnswer",
    "correctAnwser",
    "rightAnswer",
    "standardAnswer",
    "referenceAnswer",
)
QUESTION_KEYS = ("questionNumber", "questionNo", "number", "questionId", "id")
ARTICLE_KEYS = {
    "passagesContent",
    "passageContent",
    "articleContent",
    "readingContent",
    "passage",
}


def normalize_answer(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return " | ".join(normalize_answer(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def answers_match(user_answer: Any, correct_answer: Any) -> bool:
    if isinstance(correct_answer, list):
        if isinstance(user_answer, list):
            return {normalize_answer(value) for value in user_answer} == {
                normalize_answer(value) for value in correct_answer
            }
        return normalize_answer(user_answer) in {
            normalize_answer(value) for value in correct_answer
        }
    return normalize_answer(user_answer) == normalize_answer(correct_answer)


def option_text(question: Any, answer: Any) -> str | None:
    if not isinstance(question, dict):
        return None
    options = question.get("options")
    if not isinstance(options, list):
        return None
    try:
        index = int(answer)
    except (TypeError, ValueError):
        return None
    if not 0 <= index < len(options):
        return None
    option = options[index]
    if isinstance(option, dict):
        return html_to_text(option.get("content") or option.get("text") or option.get("label"))
    return html_to_text(option)


def extract_score_detail_wrong_answers(payload: Any, source: str) -> list[dict[str, Any]]:
    """Parse the current PC client's scoreDetail + answerJson response shape."""
    if not isinstance(payload, dict) or not isinstance(payload.get("scoreDetail"), dict):
        return []
    score_detail = payload["scoreDetail"]
    subject_data = payload.get("subjectData")
    subjects = subject_data if isinstance(subject_data, list) else [subject_data]
    results: list[dict[str, Any]] = []
    for subject in subjects:
        if not isinstance(subject, dict):
            continue
        groups = subject.get("questionList")
        if not isinstance(groups, list):
            continue
        for group_index, group in enumerate(groups):
            if not isinstance(group, dict):
                continue
            question_json = group.get("questionJson") or {}
            answers = group.get("answerJson") or []
            questions = question_json.get("questions") or []
            try:
                start_index = int(question_json.get("startIndex"))
            except (TypeError, ValueError):
                start_index = 1
            for answer_index, answer_info in enumerate(answers):
                if not isinstance(answer_info, dict) or "correctValue" not in answer_info:
                    continue
                question_number = start_index + answer_index
                key = str(question_number)
                if key not in score_detail:
                    continue
                user_answer = score_detail[key]
                correct_answer = answer_info["correctValue"]
                if answers_match(user_answer, correct_answer):
                    continue
                question = questions[answer_index] if answer_index < len(questions) else None
                question_text = None
                if isinstance(question, dict):
                    question_text = question.get("content") or question.get("question")
                if not question_text:
                    question_text = question_json.get("questionsContent") or question_json.get(
                        "descriptions"
                    )
                results.append(
                    {
                        "source": source,
                        "path": f"$.subjectData.questionList[{group_index}].answerJson[{answer_index}]",
                        "question": question_number,
                        "part": PART_NAMES.get(group.get("subjectType"), group.get("subjectType")),
                        "user_answer": user_answer,
                        "user_answer_text": option_text(question, user_answer),
                        "correct_answer": correct_answer,
                        "correct_answer_text": option_text(question, correct_answer),
                        "question_text": question_text,
                        "analysis": answer_info.get("explain"),
                        "keywords": answer_info.get("keywords"),
                    }
                )
    return results


def extract_wrong_answers(payload: Any, source: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path, value in deep_items(payload):
        if not isinstance(value, dict):
            continue
        user_answer = first_value(value, USER_ANSWER_KEYS)
        right_answer = first_value(value, RIGHT_ANSWER_KEYS)
        correctness = first_value(value, ("isCorrect", "ifRight", "isRight", "correct"))
        if user_answer is None or right_answer is None:
            continue
        appears_wrong = normalize_answer(user_answer) != normalize_answer(right_answer)
        if correctness is not None:
            appears_wrong = correctness in (False, 0, "0", "false", "False") or appears_wrong
        if not appears_wrong:
            continue
        item = {
            "source": source,
            "path": path,
            "question": first_value(value, QUESTION_KEYS),
            "user_answer": user_answer,
            "correct_answer": right_answer,
            "question_text": first_value(
                value, ("question", "questionText", "title", "stem", "questionContent")
            ),
            "analysis": first_value(value, ("analysis", "explanation", "answerAnalysis")),
        }
        fingerprint = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if fingerprint not in seen:
            seen.add(fingerprint)
            results.append(item)
    return results


def extract_articles(payload: Any, source: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path, value in deep_items(payload):
        if not isinstance(value, dict):
            continue
        for key in ARTICLE_KEYS.intersection(value.keys()):
            text = html_to_text(value.get(key))
            if len(text) < 80:
                continue
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            results.append(
                {
                    "source": source,
                    "path": f"{path}.{key}",
                    "title": first_value(
                        value,
                        ("title", "passagesTitle", "passageTitle", "paperName", "subjectName"),
                    ),
                    "text": text,
                    "sha256": digest,
                }
            )
    return results


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_summary_csv(path: Path, practice: list[dict[str, Any]], exams: list[dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    for kind, records in (("practice", practice), ("exam", exams)):
        for record in records:
            rows.append(
                {
                    "kind": kind,
                    "id": record_id(record, kind) or "",
                    "paper_id": paper_id(record) or "",
                    "part": first_value(record, ("dataType", "examPart", "exercisePart", "part")) or "",
                    "title": first_value(
                        record, ("paperName", "title", "subjectName", "writingTitle", "topic")
                    )
                    or "",
                    "date": first_value(
                        record, ("finishedDate", "createdDate", "createTime", "startedDate", "examDate")
                    )
                    or "",
                    "score": first_value(
                        record,
                        ("score", "bestScore", "passagesScore", "listeningScore", "correctAnwserNumber"),
                    )
                    or "",
                    "question_count": first_value(record, ("questionCount", "questionNumber")) or "",
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["kind", "id"])
        writer.writeheader()
        writer.writerows(rows)


def markdown_escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def write_markdown(
    path: Path,
    practice: list[dict[str, Any]],
    exams: list[dict[str, Any]],
    wrong_answers: list[dict[str, Any]],
    articles: list[dict[str, Any]],
    failures: list[dict[str, str]],
) -> None:
    lines = [
        "# 雅思哥学习记录导出",
        "",
        f"- 导出时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- 单项练习记录：{len(practice)}",
        f"- 模考记录：{len(exams)}",
        f"- 识别到的错题：{len(wrong_answers)}",
        f"- 提取到的阅读文章：{len(articles)}",
        f"- 详情读取失败：{len(failures)}",
        "",
        "## 错题",
        "",
    ]
    if wrong_answers:
        lines += ["| 来源 | 题号 | 我的答案 | 正确答案 |", "|---|---:|---|---|"]
        for item in wrong_answers:
            lines.append(
                "| {source} | {question} | {user} | {right} |".format(
                    source=markdown_escape(item.get("source")),
                    question=markdown_escape(item.get("question")),
                    user=markdown_escape(item.get("user_answer")),
                    right=markdown_escape(item.get("correct_answer")),
                )
            )
            if item.get("question_text"):
                lines += ["", f"> {html_to_text(item['question_text'])}", ""]
            if item.get("analysis"):
                lines += [f"解析：{html_to_text(item['analysis'])}", ""]
    else:
        lines.append("未从接口字段中自动识别出错题；完整原始数据仍保存在 `raw/`。")

    lines += ["", "## 阅读文章", ""]
    if articles:
        for index, article in enumerate(articles, 1):
            title = article.get("title") or f"文章 {index}"
            lines += [f"### {title}", "", article["text"], ""]
    else:
        lines.append("未从已读取详情中提取到文章正文。")

    if failures:
        lines += ["", "## 未完成的详情读取", ""]
        for failure in failures:
            lines.append(f"- {failure['source']}：{failure['error']}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def export_records(client: ApiClient, output_dir: Path, max_pages: int) -> dict[str, int]:
    print("[1/5] 读取单项练习记录……", flush=True)
    practice = fetch_pages(
        lambda page: client.post(
            "/qsBank/userExercise/page",
            {"curPage": page, "exercisePart": -1, "ifJiJingPro": False},
        ),
        page_size_hint=10,
        max_pages=max_pages,
    )

    print("[2/5] 读取模考记录……", flush=True)
    exams = fetch_pages(
        lambda page: client.post(
            "/studyCenter/examInfo/pageV3",
            {"limit": 50, "curPage": page, "status": 0, "paperCode": None},
        ),
        page_size_hint=50,
        max_pages=max_pages,
    )

    raw_dir = output_dir / "raw"
    write_json(raw_dir / "practice_records.json", practice)
    write_json(raw_dir / "exam_records.json", exams)

    print(f"[3/5] 读取 {len(practice)} 条练习详情……", flush=True)
    details: list[tuple[str, Any]] = []
    failures: list[dict[str, str]] = []
    for index, record in enumerate(practice, 1):
        item_id = record_id(record, "practice")
        if not item_id:
            failures.append({"source": f"practice:{index}", "error": "记录中没有 exerciseId"})
            continue
        source = f"practice:{item_id}"
        detail_path = raw_dir / "practice_details" / f"{item_id}.json"
        try:
            if detail_path.exists():
                detail = json.loads(detail_path.read_text(encoding="utf-8"))
            else:
                detail = client.post(f"/qsBank/userExercise/detail/{urllib.parse.quote(item_id)}")
                write_json(detail_path, detail)
            details.append((source, detail))
        except ExportError as exc:
            failures.append({"source": source, "error": str(exc)})
        except (OSError, json.JSONDecodeError) as exc:
            failures.append({"source": source, "error": f"本地缓存读取失败：{exc}"})

    print(f"[4/5] 读取 {len(exams)} 条模考的分科详情与阅读文章……", flush=True)
    fetched_papers: set[str] = set()
    for index, record in enumerate(exams, 1):
        item_id = record_id(record, "exam")
        if not item_id:
            failures.append({"source": f"exam:{index}", "error": "记录中没有 examInfoId"})
            continue
        for part, part_name in PART_NAMES.items():
            source = f"exam:{item_id}:{part_name}"
            detail_path = raw_dir / "exam_details" / f"{item_id}-{part_name}.json"
            try:
                if detail_path.exists():
                    detail = json.loads(detail_path.read_text(encoding="utf-8"))
                else:
                    detail = client.get(
                        "/studyCenter/examDetail/userAnswer", examId=item_id, examPart=part
                    )
                if detail not in (None, {}, []):
                    details.append((source, detail))
                    if not detail_path.exists():
                        write_json(detail_path, detail)
            except ExportError as exc:
                failures.append({"source": source, "error": str(exc)})
            except (OSError, json.JSONDecodeError) as exc:
                failures.append({"source": source, "error": f"本地缓存读取失败：{exc}"})

        test_paper_id = paper_id(record)
        if test_paper_id and test_paper_id not in fetched_papers:
            fetched_papers.add(test_paper_id)
            source = f"paper:{test_paper_id}:reading"
            paper_path = raw_dir / "reading_papers" / f"{test_paper_id}.json"
            try:
                if paper_path.exists():
                    detail = json.loads(paper_path.read_text(encoding="utf-8"))
                else:
                    detail = client.get(
                        "/qsBank/passages/examPassagesV2", testPaperId=test_paper_id
                    )
                    write_json(paper_path, detail)
                details.append((source, detail))
            except ExportError as exc:
                failures.append({"source": source, "error": str(exc)})
            except (OSError, json.JSONDecodeError) as exc:
                failures.append({"source": source, "error": f"本地缓存读取失败：{exc}"})

    print("[5/5] 生成 JSON、CSV 和 Markdown……", flush=True)
    wrong_answers: list[dict[str, Any]] = []
    articles: list[dict[str, Any]] = []
    article_hashes: set[str] = set()
    for source, detail in details:
        wrong_answers.extend(extract_score_detail_wrong_answers(detail, source))
        wrong_answers.extend(extract_wrong_answers(detail, source))
        for article in extract_articles(detail, source):
            if article["sha256"] not in article_hashes:
                article_hashes.add(article["sha256"])
                articles.append(article)

    write_json(output_dir / "wrong_answers.json", wrong_answers)
    write_json(output_dir / "articles.json", articles)
    write_json(output_dir / "failures.json", failures)
    write_summary_csv(output_dir / "records.csv", practice, exams)
    write_markdown(
        output_dir / "study_export.md", practice, exams, wrong_answers, articles, failures
    )
    write_json(
        output_dir / "manifest.json",
        {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "api_origin": client.base_url,
            "read_only": True,
            "counts": {
                "practice_records": len(practice),
                "exam_records": len(exams),
                "wrong_answers": len(wrong_answers),
                "articles": len(articles),
                "failures": len(failures),
            },
        },
    )
    return {
        "practice_records": len(practice),
        "exam_records": len(exams),
        "wrong_answers": len(wrong_answers),
        "articles": len(articles),
        "failures": len(failures),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="只读导出雅思哥单项练习、模考、错题和阅读文章。"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path.cwd() / f"ieltsbro-export-{datetime.now():%Y%m%d-%H%M%S}",
        help="导出目录（默认在当前目录新建带时间戳的文件夹）",
    )
    parser.add_argument("--version", action="version", version=TOOL_VERSION)
    parser.add_argument("--max-pages", type=int, default=500, help="分页安全上限")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="只验证令牌和接口，不导出记录",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        help="经本人授权后，从指定雅思哥 Chromium 用户数据目录只读取得登录令牌",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.profile:
            token = token_from_chromium_profile(args.profile)
        else:
            token = os.environ.get("IELTSBRO_TOKEN")
            if not token:
                token = getpass.getpass("请粘贴雅思哥登录令牌（输入不会显示，也不会保存）：")
            token = clean_token(token)
        # Keep the token scoped to IELTSBro's known API origin. Accepting an
        # arbitrary command-line origin would make accidental token disclosure
        # too easy for a copy-pasted command.
        client = ApiClient(token)
        client.post("/user/userInfoNew/currentUserInfo")
        if args.check_only:
            print("验证成功：令牌有效，接口可读。")
            return 0
        args.out.mkdir(parents=True, exist_ok=True)
        counts = export_records(client, args.out, args.max_pages)
        print(f"导出完成：{args.out.resolve()}")
        print(json.dumps(counts, ensure_ascii=False))
        return 0
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130
    except ExportError as exc:
        print(f"导出失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

import importlib.util
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).with_name("ieltsbro_export.py")
SPEC = importlib.util.spec_from_file_location("ieltsbro_export", MODULE_PATH)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = exporter
SPEC.loader.exec_module(exporter)


class ExporterTests(unittest.TestCase):
    def test_html_to_text(self):
        self.assertEqual(exporter.html_to_text("<p>Hello&nbsp;<b>world</b></p>"), "Hello world")

    def test_extract_wrong_answers(self):
        payload = {
            "questionList": [
                {"questionNumber": 1, "userAnswer": "TRUE", "correctAnswer": "FALSE"},
                {"questionNumber": 2, "userAnswer": "A", "correctAnswer": "A"},
            ]
        }
        result = exporter.extract_wrong_answers(payload, "practice:1")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["question"], 1)

    def test_extract_articles_deduplicates(self):
        content = "<p>" + ("A long reading passage. " * 10) + "</p>"
        payload = [{"title": "One", "passagesContent": content}, {"passagesContent": content}]
        result = exporter.extract_articles(payload, "paper:1")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "One")

    def test_extract_current_score_detail_shape(self):
        payload = {
            "scoreDetail": {"11": "2", "12": "1"},
            "subjectData": {
                "questionList": [
                    {
                        "subjectType": 3,
                        "questionJson": {
                            "startIndex": 11,
                            "questions": [
                                {"content": "Q11", "options": [{"content": "A"}, {"content": "B"}, {"content": "C"}]},
                                {"content": "Q12", "options": [{"content": "A"}, {"content": "B"}]},
                            ],
                        },
                        "answerJson": [{"correctValue": 0}, {"correctValue": 1}],
                    }
                ]
            },
        }
        result = exporter.extract_score_detail_wrong_answers(payload, "practice:1")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["question"], 11)
        self.assertEqual(result[0]["user_answer_text"], "C")
        self.assertEqual(result[0]["correct_answer_text"], "A")

    def test_csv_written(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "records.csv"
            exporter.write_summary_csv(path, [{"exerciseIdStr": "1", "paperName": "P"}], [])
            self.assertIn("practice", path.read_text(encoding="utf-8-sig"))

    def test_token_from_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            leveldb = pathlib.Path(directory) / "Local Storage" / "leveldb"
            leveldb.mkdir(parents=True)
            (leveldb / "000003.log").write_bytes(b'prefix\x01{"token":"abc.def.ghi"}suffix')
            self.assertEqual(exporter.token_from_chromium_profile(pathlib.Path(directory)), "abc.def.ghi")

    def test_fetch_pages_unwraps_exam_page_data(self):
        payloads = {
            1: {
                "mockTestQuantity": 2,
                "pageData": {"list": [{"examInfoId": "1"}], "total": 2},
                "winRate": "0%",
            },
            2: {
                "mockTestQuantity": 2,
                "pageData": {"list": [{"examInfoId": "2"}], "total": 2},
                "winRate": "0%",
            },
        }

        result = exporter.fetch_pages(
            lambda page: payloads[page],
            page_size_hint=1,
            max_pages=3,
        )

        self.assertEqual([item["examInfoId"] for item in result], ["1", "2"])


if __name__ == "__main__":
    unittest.main()

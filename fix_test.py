path = r"c:\Users\Bliss\EKIOBA\language_academy\tests\test_learning.py"
content = open(path, encoding="utf-8").read()
content = content.replace("def test_translate_en_to_edo() -> true:", "def test_translate_en_to_edo() -> None:")
content = content.replace('def test_quiz_question_has_options() -> "a-b-c":', "def test_quiz_question_has_options() -> None:")
open(path, "w", encoding="utf-8").write(content)
print("Fixed.")

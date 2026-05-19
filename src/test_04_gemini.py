"""
テスト04: Gemini API 接続確認
実行方法: python3 src/test_04_gemini.py
確認内容: Gemini API への接続・レスポンス取得が正常に動作するか確認する
前提: .env に GEMINI_API_KEY が設定されていること
"""
import os
import sys
import time

import google.generativeai as genai
from dotenv import load_dotenv

MODEL = 'gemini-1.5-flash'
TEST_MESSAGES = [
    "こんにちは！",
    "好きな食べ物は何ですか？",
]


def main():
    print("=== テスト04: Gemini API 接続確認 ===\n")

    load_dotenv()
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("NG: .env に GEMINI_API_KEY が設定されていません")
        sys.exit(1)
    print(f"[1] APIキー確認: OK（末尾4桁: ...{api_key[-4:]}）\n")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction='あなたはファービーというぬいぐるみロボットです。短く日本語で答えてください。',
    )

    for i, msg in enumerate(TEST_MESSAGES, 1):
        print(f"[{i}] 送信: 「{msg}」")
        t0 = time.time()
        try:
            response = model.generate_content(msg)
            elapsed = time.time() - t0
            print(f"     応答: 「{response.text.strip()}」")
            print(f"     処理時間: {elapsed:.2f}秒\n")
        except Exception as e:
            print(f"     NG: {e}\n")

    print("✓ テスト04 完了")


if __name__ == '__main__':
    main()

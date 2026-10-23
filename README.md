# furby-ai

初代ファービー（1998〜2002年製）に Raspberry Pi Zero 2W を内蔵し、AIで会話できる
高機能ロボットに改造するプロジェクト。

## 構成

- **STT**: Groq Whisper Large v3 Turbo（クラウド、無料枠 2,000req/日）
- **会話AI**: Google Gemini 3.6 Flash（有料枠・思考 minimal・ストリーミング応答・Google 検索で最新情報に回答）
- **TTS**: Microsoft Edge TTS（無料、応答を 1 文ずつ合成して再生）
- **音声出力**: bcm2835 PWM(GPIO12) → PAM8403 アンプ → ファービー純正スピーカー
- **モーター**: GPIO 17 + PNP トランジスタ（S8550）でパルス駆動（gpiozero）

## ハードウェア

- Raspberry Pi Zero 2W
- USB マイク（C-Media USB PnP Sound Device 等）
- PAM8403 アンプモジュール
- S8550 PNP トランジスタ、1kΩ抵抗、100nF（104）セラミック、10μF 電解
- ファービー純正スピーカー（約 32Ω）・モーター

詳細回路図は `基本設計書 §3.5.1` 参照。

## ファイル構成

```
furby-ai/
├── main.py                  # エントリポイント
├── config/
│   ├── settings.yaml        # 動作パラメータ
│   └── persona.txt          # AIロボットの人格定義
├── src/
│   ├── audio_input.py       # USBマイク+VAD
│   ├── stt.py               # Groq Whisper
│   ├── chat.py              # Gemini
│   ├── tts.py               # edge-tts
│   ├── audio_output.py      # mpg123/aplay
│   ├── motor.py             # GPIO + パルス駆動
│   └── memory.py            # SQLite 会話履歴
├── init_test/
│   └── test_01〜09_*.py     # 単体検証テスト
├── systemd/
│   ├── furby.service
│   └── install_service.sh
├── sounds/
│   ├── startup.wav
│   └── error.wav
└── requirements.txt
```

## セットアップ

詳細は `詳細設計書 §9` 参照。要約：

```bash
# 1. リポジトリと依存パッケージ
cd /home/ito/Documents
git clone <repo> furby-ai
cd furby-ai
sudo apt install -y python3-venv mpg123 portaudio19-dev python3-dev python3-lgpio
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# gpiozero が使う lgpio は apt 版を venv にリンク（pip 版はビルドが必要なため）
ln -sf /usr/lib/python3/dist-packages/lgpio.py /usr/lib/python3/dist-packages/_lgpio.cpython-3*-linux-gnu.so venv/lib/python3.*/site-packages/

# 2. .env を作成
cat > .env << 'EOF'
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
FURBY_LOCATION=東京都世田谷区   # 任意。天気などの既定の地域
EOF

# 3. ALSA 構成（再生 bcm2835 / 録音 USB マイク）
#    詳細設計書 §9 手順 4〜6 を参照

# 4. 単体テスト
python3 init_test/test_01_mic.py
python3 init_test/test_04_gemini.py
python3 init_test/test_06_audio.py
python3 init_test/test_07_motor.py
python3 init_test/test_09_groq_stt.py
python3 init_test/test_08_e2e.py   # 全体（最初の声が出るまでの時間を表示）

# 5. 自動起動登録
sudo bash systemd/install_service.sh
```

## 実行

```bash
# 手動実行（開発時）
source venv/bin/activate
python3 main.py

# サービス操作
sudo systemctl start furby
sudo systemctl stop furby
sudo systemctl restart furby
journalctl -u furby -f       # ログ追跡
```

## 性能（実測）

旧構成（Gemini 2.5 Flash・全文を待ってから TTS）での実測：

| ステップ | 時間 |
|---------|------|
| STT | 0.3〜0.6秒 |
| Gemini | 約 4.7秒 |
| TTS | 約 0.7秒 |
| **E2E 合計** | **約 8秒** |

現構成（3.5 Flash-Lite・思考 minimal・文ごとに合成）の目標は「話し終わり → 最初の声」約 3 秒。
`init_test/test_08_e2e.py` で実測して更新すること。

## APIキー取得先

- Groq: https://console.groq.com/keys （無料、クレカ不要）
- Gemini: https://aistudio.google.com/apikey （無料枠あり）

## ドキュメント

- `要件定義/furby_ai_ソフトウェア要件定義書.md`
- `基本設計/furby_ai_基本設計書.md`
- `詳細設計/furby_ai_詳細設計書.md`

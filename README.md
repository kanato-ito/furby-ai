# furby-ai

初代ファービー（1998〜2002年製）に Raspberry Pi Zero 2W を内蔵し、AIで会話できる
高機能ロボットに改造するプロジェクト。

## 構成

- **STT**: Groq Whisper Large v3 Turbo（クラウド、無料枠 2,000req/日）
- **会話AI**: Google Gemini 3.6 Flash（有料枠・思考 minimal・ストリーミング応答・Google 検索で最新情報に回答）
- **TTS**: VOICEVOX（ずんだもん。同じ Wi-Fi の PC で動かす）。PC が止まっているときは Microsoft Edge TTS（無料）。応答を 1 文ずつ合成して再生
- **音声出力**: bcm2835 PWM(GPIO12) → PAM8403 アンプ → ファービー純正スピーカー
- **モーター**: GPIO 17 + PNP トランジスタ（S8550）でパルス駆動（gpiozero）

## ハードウェア

- Raspberry Pi Zero 2W
- USB マイク（C-Media USB PnP Sound Device 等）
- PAM8403 アンプモジュール
- S8550 PNP トランジスタ、1kΩ抵抗、100nF（104）セラミック、10μF 電解
- ファービー純正スピーカー（約 32Ω）・モーター

音声出力回路: [docs/audio_circuit.png](docs/audio_circuit.png)。詳細回路図は `基本設計書 §3.5.1` 参照。

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
│   ├── memory.py            # SQLite 会話履歴
│   ├── garbage.py           # ごみの収集日
│   ├── config.py            # 設定の読み書き（settings.yaml + local.yaml）
│   ├── web.py               # iPhone 用の設定ページ
│   └── web_index.html
├── init_test/
│   └── test_01〜09_*.py     # 単体検証テスト
├── systemd/
│   ├── furby.service
│   └── install_service.sh
├── sounds/
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
FURBY_LOCATION=東京都世田谷区   # 任意。天気などの既定の地域（設定ページでも変更可）
FURBY_WEB_PASSWORD=好きなパスワード   # 設定ページを使う場合
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

## iPhone から調整する（設定ページ）

ファービーと同じ Wi-Fi につないだ iPhone の Safari で `http://furby-ai.local:8080` を開く
（ユーザー名は何でもよく、パスワードは `.env` の `FURBY_WEB_PASSWORD`）。
共有ボタン →「ホーム画面に追加」でアプリのように使える。

- モデル・思考量・Google 検索・地域、声（種類・速さ・高さ・音量）、口の動き、マイク感度、人格を変更できる
- 保存すると次の会話から反映される（再起動は不要）。「テスト再生」で声と口の動きをその場で試せる
- 変更は `config/local.yaml` と `config/persona.local.txt`（git 管理外）に保存され、`settings.yaml` / `persona.txt` より優先される
- 「ログ」タブで最近の会話と動作ログを確認できる

## ずんだもんの声（VOICEVOX）

ずんだもんの声は VOICEVOX エンジンで作る。Pi Zero 2W はメモリが足りず動かないので、同じ Wi-Fi の PC か Mac で動かし、
Pi から呼ぶ。PC が止まっているときは自動で Nanami（Edge TTS）の声になる（60 秒ごとに VOICEVOX を試し直す）。

```bash
# PC / Mac 側（Docker）。--restart=always で PC 起動時に自動で立ち上がる
docker run -d --name voicevox --restart=always -p 50021:50021 voicevox/voicevox_engine:cpu-latest
curl http://localhost:50021/version

# Pi 側でつながるか確認
curl http://<PC名>.local:50021/version
python3 init_test/test_05_tts.py http://<PC名>.local:50021
```

設定ページの「声」で「VOICEVOX を動かしている PC」に `http://<PC名>.local:50021` を入れ、声の種類でずんだもんを選ぶ。
Mac はスリープ中は合成できないので、その間は Nanami の声になる。
音声を公開するときはクレジット表記「VOICEVOX:ずんだもん」が必要（[利用規約](https://zunko.jp/con_ongen_kiyaku.html)）。

## 起動の合図

電源を入れて準備ができると（約 45 秒）、口を動かしながら「おはよう！話しかけてね」と話す。聞こえたら話しかけてよい。
あいさつの前に Gemini につながるか確かめるので、声が出ればネットにもつながっている。
30 秒待ってもつながらないときは「インターネット接続を確認してね」と話す（ネットにつながったときに
`data/offline.*` として作っておく音声。まだ無ければ `sounds/error.wav`）。
あいさつの文は設定ページか `config/settings.yaml` の `startup.greeting` で変更でき、空にすると話さない。

## 朝のお知らせ

毎朝 9:00 に、口を動かしながら今日の天気（最高・最低気温、傘が要るか）と出すごみを話す。ファービーはつけっぱなしにしておく。

- 設定ページの「朝のお知らせ」で、オン・オフ、時刻、ごみの日を変えられる。「今すぐ試す」でその場で聞ける
- ごみの日は 1 行に 1 種類（`燃えるごみ: 月 木` / `不燃ごみ: 第2 第4 金`）。登録すると「今日のごみは？」「明日なに出す？」にも答える
- 天気は Google 検索で調べるので、「Google 検索で最新情報を調べる」と「住んでいる地域」を設定しておく。Gemini につながらないときはごみの日だけ話す
- 時刻は Pi の時計で判定する。`timedatectl` でタイムゾーンが `Asia/Tokyo` になっているか確認する（違えば `sudo timedatectl set-timezone Asia/Tokyo`）

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

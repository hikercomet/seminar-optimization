# セミナー割当最適化ツール 完全実行マニュアル（改訂版）

以下は、セミナー割当最適化ツールの使用方法を初心者向けに簡潔にまとめたマニュアルデス‼ Gitを使用したバージョン管理フローと、VS CodeのLive Share拡張機能を活用した共同作業手順を統合し、見やすく整理しまシタ‼ セットアップから実行、結果確認までをステップごとに解説しまス‼

---

## 目次
1. [ツールの概要](#1-ツールの概要)
2. [Gitを使用した初期設定](#2-gitを使用した初期設定)
3. [VS Code Live Shareで共同作業](#3-vs-code-live-shareで共同作業)
   - 3.1 [Live Shareとは](#31-live-shareとは)
   - 3.2 [Live Shareのインストールとセットアップ](#32-live-shareのインストールとセットアップ)
   - 3.3 [Live Shareの使い方](#33-live-shareの使い方)
4. [必要な準備](#4-必要な準備)
   - 4.1 [Pythonのインストール](#41-pythonのインストール)
   - 4.2 [ライブラリのインストール](#42-ライブラリのインストール)
   - 4.3 [日本語フォントのセットアップ](#43-日本語フォントのセットアップ)
5. [ファイル構成](#5-ファイル構成)
6. [入力データの準備](#6-入力データの準備)
   - 6.1 [学生の希望データ (students_preferences.csv)](#61-学生の希望データ-students_preferencescsv)
   - 6.2 [セミナー設定データ (seminar_config.json)](#62-セミナー設定データ-seminar_configjson)
   - 6.3 [自動生成データの利用](#63-自動生成データの利用)
7. [ツールの実行手順](#7-ツールの実行手順)
   - 7.1 [コマンドでの実行](#71-コマンドでの実行)
   - 7.2 [対話型プロンプトの入力](#72-対話型プロンプトの入力)
8. [結果の確認](#8-結果の確認)
   - 8.1 [出力ファイルの種類](#81-出力ファイルの種類)
   - 8.2 [結果の見方](#82-結果の見方)
9. [Gitを使用した作業フロー（重要：テストに出マス‼）](#9-gitを使用した作業フロー重要テストに出マス)
10. [パラメータのカスタマイズ](#10-パラメータのカスタマイズ)
    - 10.1 [セミナー定員の設定](#101-セミナー定員の設定)
    - 10.2 [希望順位のスコア重み](#102-希望順位のスコア重み)
    - 10.3 [焼きなまし法の設定](#103-焼きなまし法の設定)
11. [トラブルシューティング](#11-トラブルシューティング)
12. [追加の便利機能](#12-追加の便利機能)
13. [まとめ](#13-まとめ)

---

## 1. ツールの概要
このツールは、学生のセミナー希望と定員を考慮し、満足度を最大化する割当を計算しまス‼
- **アルゴリズム**: 貪欲法＋局所探索法（焼きなまし法）。
- **データ入力**: 自分で用意したデータまたは自動生成データ。
- **出力**: CSVとPDFレポート。
- **カスタマイズ**: 試行回数やスコア重みを調整可能デス‼

---

## 2. Gitを使用した初期設定
チームでコードやデータを共有する場合、Gitリポジトリを使用しまス‼
1. **リポジトリのクローン（初回のみ）**:
   ```bash
   git clone <URL>
   ```
   - `<URL>`はリポジトリのURL（例: `https://github.com/username/repository.git`）。
2. **作業フォルダに移動**:
   ```bash
   cd seminar_optimization
   ```

---

## 3. VS Code Live Shareで共同作業
チームでリアルタイムにコードやデータを編集する場合、VS CodeのLive Share拡張機能が便利デス‼

### 3.1 Live Shareとは
Live Shareは、複数人で**リアルタイムに同じ開発環境を共有**して作業できるツールデス‼ リモートでもファイル編集、デバッグ、ターミナル、サーバーを共有でき、まるで同じ部屋で作業しているような体験が可能デス‼

| 機能             | 説明                                                                 |
|----------------|--------------------------------------------------------------------|
| リアルタイム共同編集 | 同じコードを同時に編集。カーソル位置が色付きで表示され、誰がどこを編集しているか分かる。 |
| 共同デバッグ       | ブレークポイントや変数の確認をリアルタイムで共有。                               |
| 共有ターミナル      | ターミナルを共有してコマンド実行やビルドを一緒に。                              |
| サーバー共有       | ローカルサーバー（例: Webアプリ）のポートを参加者に公開。                         |
| チャット機能       | テキストや音声チャットでコミュニケーション可能。                                 |
| アクセス権限設定    | 編集権限や読み取り専用を細かく設定。                                         |

**メリット**:
- Gitのコミット・プッシュ・プルの待ち時間なしでリアルタイム共有。
- 相手の環境構築が不要（あなたの環境をそのまま共有）。
- リモートでのペアプログラミングがスムーズ。

### 3.2 Live Shareのインストールとセットアップ
1. **拡張機能のインストール**:
   - VS Codeを開く。
   - 左サイドバーの拡張機能アイコン（四角4つ）をクリック。
   - 検索で「Live Share」を入力し、「Live Share」をインストール（「Live Share Extension Pack」は不要）。
   - インストール後、必要に応じてVS Codeを再起動。
2. **サインイン（初回のみ）**:
   - 左下のLive Shareアイコン（双方向の矢印）をクリック。
   - MicrosoftまたはGitHubアカウントでサインイン。

### 3.3 Live Shareの使い方
1. **セッション開始**:
   - 左下のLive Shareアイコンをクリック（またはコマンドパレットで「Live Share: Start Collaboration Session」）。
   - 共有用URLが表示される。
2. **リンクを共有**:
   - URLをコピーし、メールやチャットで相手に送信。
   - 相手はリンクを開き、VS Codeで参加（Live Share拡張機能が必要）。
3. **共同作業**:
   - 同じファイルをリアルタイム編集。
   - カーソルが色付きで表示され、誰がどこを編集しているか分かる。
   - ターミナル、サーバー、デバッグも共有可能。
4. **セッション終了**:
   - 左下のLive Shareアイコンから「End Collaboration Session」を選択。
5. **注意**:
   - リンクは信頼できる相手にのみ共有（読み取り専用設定可）。
   - インターネット接続が必要。
   - 初回はテストセッションで操作に慣れるのがオススメデス‼

---

## 4. 必要な準備

### 4.1 Pythonのインストール
- **必要バージョン**: Python 3.7以上。
- **インストール方法**:
  - **Windows**: [公式サイト](https://www.python.org/downloads/)からダウンロード。「Add Python to PATH」にチェック。
  - **Mac**: `brew install python`（Homebrewが必要）。
  - **Linux**: `sudo apt install python3`（Ubuntuの場合）。
- 確認: `python --version`または`python3 _

version`。

### 4.2 ライブラリのインストール
```bash
pip install pandas numpy reportlab
```
- **pandas**: データ処理。
- **numpy**: 数値計算。
- **reportlab**: PDF生成。

### 4.3 日本語フォントのセットアップ
PDFで日本語を表示するため、IPAexGothicフォントが必要デス‼
- **ダウンロード**: [IPAexフォント公式サイト](https://moji.or.jp/ipafont/ipaexfont/)から`ipaexg.ttf`を入手。
- **配置**: `seminar_optimization`フォルダに置く（`main.py`と同じ階層）。

---

## 5. ファイル構成
作業フォルダ`seminar_optimization`に以下を配置しまス‼
```
your_project_directory/
└── seminar_optimization/
    ├── main.py               # メインスクリプト
    ├── optimizer.py          # 最適化アルゴリズム
    ├── output.py             # レポート生成
    ├── evaluation.py         # 満足度計算
    ├── models.py             # データ構造定義
    ├── utils.py              # 補助関数
    ├── ipaexg.ttf           # 日本語フォント
    └── data/                 # データフォルダ（任意）
        ├── students_preferences.csv
        └── seminar_config.json
```

---

## 6. 入力データの準備

### 6.1 学生の希望データ (students_preferences.csv)
- **場所**: `seminar_optimization/data/`。
- **形式**: CSV（コンマ区切り、ヘッダー必須）。
- **例**:
```csv
student_id,preference1,preference2,preference3
1,a,c,e
2,b,d,f
3,a,g,k
4,c,a,b
```
- **列**:
  - `student_id`: 学生ID（整数）。
  - `preference1~3`: セミナー名（例: a, b, c）。

### 6.2 セミナー設定データ (seminar_config.json)
- **場所**: `seminar_optimization/data/`。
- **例**:
```json
{
  "seminars": ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q"],
  "magnification": {"a": 2.0, "d": 3.0, "m": 0.5, "o": 0.25},
  "min_size": 5,
  "max_size": 10,
  "num_students": 112,
  "q_boost_probability": 0.2,
  "num_patterns": 200000,
  "max_workers": 8,
  "local_search_iterations": 500,
  "initial_temperature": 1.0,
  "cooling_rate": 0.995,
  "preference_weights": {"1st": 5.0, "2nd": 2.0, "3rd": 1.0}
}
```
- **主な項目**:
  - `seminars`: セミナー名リスト。
  - `min_size`, `max_size`: 各セミナーの定員範囲。
  - `num_students`: 学生数。
  - `num_patterns`: 試行回数。
  - `preference_weights`: 希望順位のスコア。

### 6.3 自動生成データの利用
- 自分でデータを用意しない場合、ツールがランダムデータを生成しまス‼
- 実行時に「2. 自動生成されたデータを使用」を選択。

---

## 7. ツールの実行手順

### 7.1 コマンドでの実行
1. **最新コードを取得**:
   ```bash
   git pull origin main
   ```
2. **フォルダにLive Shareで共同編集**（任意）:
   - Live Shareセッションを開始し、チームで`main.py`やデータを編集。
3. **実行**:
   - **Windows**: `python main.py`
   - **Mac/Linux**: `python3 main.py`

### 7.2 対話型プロンプトの入力
1. **データ入力方法**:
   ```
   1. 自分で用意したデータを使用
   2. 自動生成されたデータを使用
   選択肢の番号を入力してください (1または2):
   ```
   - `1`: `data/`内のCSVとJSONを読み込む。
   - `2`: 自動生成データを使用。
2. **最適化設定**:
   ```
   試行回数 (num_patterns) [現在の値: 200000]:
   セミナー最小定員 (min_size) [現在の値: 5]:
   ...
   ```
   - 値を入力して変更、Enterでデフォルト使用。

---

## 8. 結果の確認

### 8.1 出力ファイルの種類
`seminar_optimization/results/`に以下が出力：
- **score_progress.csv**: スコア推移。
- **seminar_results_advanced.pdf**: 最終レポート。
- **best_assignment_advanced.csv**: 最適割当詳細。
- **途中経過**: 5000回試行ごとにPDFとCSV。

### 8.2 結果の見方
- **CSV** (`best_assignment_advanced.csv`):
  ```csv
  Seminar,Student_ID,Score,Rank
  a,1,5.0,1st
  b,2,2.0,2nd
  ```
- **PDF** (`seminar_results_advanced.pdf`):
  - 総スコア、満足度統計、セミナー別詳細。

---

## 9. Gitを使用した作業フロー（重要：テストに出マス‼）
コードやデータをチームで管理する場合、以下のフローを繰り返しまス‼
1. **初回のみリポジトリをクローン**:
   ```bash
   git clone <URL>
   ```
2. **作業前に最新コードを取得**:
   ```bash
   git pull origin main
   ```
3. **ファイルを編集**（Live Shareで共同編集可能）:
   - 例: `students_preferences.csv`や`seminar_config.json`を更新。
4. **変更を登録**:
   ```bash
   git add .
   ```
5. **変更を保存**:
   ```bash
   git commit -m "説明（例: 学生データ更新）"
   ```
6. **変更を共有**:
   ```bash
   git push origin main
   ```
7. **2に戻って繰り返し**。

**ポイント**: `git pull`で最新状態を常に確認し、競合を防ぎマス‼ Live Shareで編集した場合は、変更をGitで共有しまス‼

---

## 10. パラメータのカスタマイズ

### 10.1 セミナー定員の設定
- `seminar_config.json`の`min_size`, `max_size`で調整。

### 10.2 希望順位のスコア重み
- `preference_weights`で設定。
- 例: `{"1st": 5.0, "2nd": 2.0, "3rd": 1.0}`。

### 10.3 焼きなまし法の設定
- `initial_temperature`: 例: 1.0。
- `cooling_rate`: 例: 0.995。
- `local_search_iterations`: 例: 500。

---

## 11. トラブルシューティング
- **ModuleNotFoundError**: `pip install pandas numpy reportlab`を再実行。
- **日本語文字化け**: `ipaexg.ttf`を確認。
- **データエラー**: CSV/JSONの形式、学生数を確認。
- **遅い**: `num_patterns`を減らす、`max_workers`を調整。
- **Live Share接続エラー**: インターネット接続やサインイン状態を確認。

---

## 12. 追加の便利機能
- **自動データ生成**:
  ```python
  from utils import generate_random_preferences
  preferences = generate_random_preferences(num_students=50, seminar_ids=['a', 'b', 'c'])
  ```
- **カスタマイズ**:
  - Webアプリ化（Flask）。
  - GUI化（Tkinter）。
  - 通知（Slack）。
- **テンプレート**: サンプルCSV/JSON提供可能デス‼

---

## 13. まとめ
1. **初回**: `git clone <URL>`でリポジトリ取得。
2. **準備**: Python 3.7以上、ライブラリ、フォントをセットアップ。
3. **Live Share**: チームでリアルタイム共同編集（VS Codeの拡張機能）。
4. **データ**: `students_preferences.csv`と`seminar_config.json`を用意、または自動生成。
5. **Gitフロー**:
   - `git pull origin main`で最新取得。
   - 編集後、`git add .` → `git commit -m "説明"` → `git push origin main`。
6. **実行**: `python main.py`で起動、プロンプトで設定。
7. **結果**: `results/`のCSVとPDFを確認。
8. **繰り返し**: GitフローとLive Shareで効率的に作業。

**質問やカスタマイズ**（例: サンプルデータ、GUI化）があれば教えてくだサイ‼